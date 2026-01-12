import asyncio
import ctypes
import os
import random
import sys
import traceback
import uuid

import aiohttp
from better_proxy import Proxy

from core import Grass
from core.autoreger import AutoReger
from core.utils import logger, file_to_list
from core.utils.accounts_db import AccountsDB
from core.utils.tokens_db import TokensDB
from core.utils.exception import LoginException
from core.utils.file_manager import remove_duplicate_accounts, str_to_file
from core.utils.solana_wallet import SolanaWallet, load_wallets
from core.utils.imap_client import find_wallet_confirmation_link, check_imap_login, is_domain_supported
from core.ui.menu import MenuManager
from data.config import ACCOUNTS_FILE_PATH, PROXIES_FILE_PATH, THREADS, AUTH_THREADS, \
    CLAIM_REWARDS_ONLY, MINING_MODE, \
    PROXY_DB_PATH, TOKENS_DB_PATH, MIN_PROXY_SCORE, CHECK_POINTS, STOP_ACCOUNTS_WHEN_SITE_IS_DOWN, \
    SHOW_LOGS_RARELY, WALLETS_FILE_PATH, ACCOUNTS_TO_LINK_PATH

ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'

# Global mode variables
LOGIN_ONLY_MODE = False
LINK_WALLETS_MODE = False


def bot_info(name: str = ""):
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleTitleW(f"{name}")
    
    # Create menu manager and display welcome
    menu_manager = MenuManager()
    menu_manager.display_welcome()


async def link_wallet_task(_id, email: str, password: str, imap_password: str, private_key: str, proxy: str, tokens_db: TokensDB):
    """Task for linking and verifying wallet"""
    import time
    import aiohttp
    from core.grass_sdk.website import GrassRest
    
    grass = None
    try:
        # Get wallet address from private key
        wallet = SolanaWallet(private_key)
        wallet_address = wallet.address
        
        # Check if wallet is already linked to another account
        linked_email = await tokens_db.is_wallet_linked(wallet_address)
        if linked_email and linked_email != email:
            logger.warning(f"{_id} | {email} | Wallet {wallet_address[:8]}... already linked to {linked_email}")
            return False
        
        # Create client and session
        grass = GrassRest(email=email, password=password, user_agent=ua, proxy=proxy, tokens_db=tokens_db)
        grass.session = aiohttp.ClientSession(trust_env=True, connector=aiohttp.TCPConnector(ssl=False))
        
        # Authorize
        logger.info(f"{_id} | {email} | Authorizing...")
        user_id = await grass.enter_account()
        
        if not user_id:
            logger.error(f"{_id} | {email} | Authorization failed")
            return False
        
        # Get user info
        user_info = await grass.retrieve_user()
        user_data = user_info.get('result', {}).get('data', {}) if user_info else {}
        
        server_wallet = user_data.get('walletAddress')
        is_verified = user_data.get('isWalletAddressVerified', False)
        
        # Wallet already linked and verified
        if server_wallet and is_verified:
            logger.success(f"{_id} | {email} | Wallet already verified: {server_wallet[:8]}...")
            await tokens_db.save_wallet(email, server_wallet)
            return True
        
        # Wallet linked but not verified
        if server_wallet and not is_verified:
            logger.info(f"{_id} | {email} | Wallet linked, verifying via email...")
            success = await _verify_wallet_email(grass, email, imap_password, proxy, _id)
            if success:
                await tokens_db.save_wallet(email, server_wallet)
            return success
        
        # Wallet not linked - link it
        timestamp = int(time.time())
        address, pub_key, message, signature = wallet.get_signature_data(timestamp)
        
        logger.info(f"{_id} | {email} | Linking wallet {address[:8]}...")
        
        result = await grass.approve_wallet(signature, pub_key, address, timestamp)
        
        if result and result.get('error'):
            error_msg = result['error'].get('message', str(result['error']))
            logger.error(f"{_id} | {email} | Link error: {error_msg}")
            return False
        
        logger.success(f"{_id} | {email} | Wallet linked, verifying via email...")
        
        # Verify via email
        success = await _verify_wallet_email(grass, email, imap_password, proxy, _id)
        if success:
            await tokens_db.save_wallet(email, address)
        
        return success
        
    except Exception as e:
        logger.error(f"{_id} | {email} | Error: {e}")
        return False
    finally:
        if grass and grass.session:
            await grass.session.close()


async def _verify_wallet_email(grass, email: str, imap_password: str, proxy: str, _id: int) -> bool:
    """Verify wallet via email"""
    from core.utils.imap_client import load_email_config
    
    try:
        # Check if proxy should be used for IMAP
        email_config = load_email_config()
        use_proxy = email_config.get('imap_settings', {}).get('use_proxy_for_imap', False)
        imap_proxy = proxy if use_proxy else None
        
        # Check IMAP access
        imap_ok = await check_imap_login(email, imap_password, imap_proxy)
        if not imap_ok:
            logger.error(f"{_id} | {email} | IMAP login failed, skipping verification")
            return False
        
        # Send verification email
        await grass.send_wallet_email_verification()
        logger.info(f"{_id} | {email} | Verification email sent")
        
        # Search for link in mailbox
        link = await find_wallet_confirmation_link(
            email=email,
            password=imap_password,
            proxy_url=imap_proxy,
            max_attempts=10,
            delay=5
        )
        
        if not link:
            logger.error(f"{_id} | {email} | Confirmation link not found")
            return False
        
        logger.info(f"{_id} | {email} | Link found, confirming...")
        
        # Extract token from link
        import re
        token_match = re.search(r'token=([a-zA-Z0-9\-_\.]+)', link)
        if token_match:
            token = token_match.group(1)
            await grass.confirm_wallet_address(token)
            logger.success(f"{_id} | {email} | Wallet verified!")
            return True
        
        logger.error(f"{_id} | {email} | Failed to extract token from link")
        return False
        
    except Exception as e:
        logger.error(f"{_id} | {email} | Verification error: {e}")
        return False


async def run_link_wallets(tokens_db: TokensDB, proxies: list):
    """Run wallet linking"""
    # Load accounts from file
    accounts = file_to_list(ACCOUNTS_TO_LINK_PATH)
    if not accounts:
        logger.error(f"No accounts in {ACCOUNTS_TO_LINK_PATH}")
        return
    
    wallets = load_wallets(WALLETS_FILE_PATH)
    if not wallets:
        logger.error(f"No wallets in {WALLETS_FILE_PATH}")
        return
    
    if len(wallets) < len(accounts):
        logger.warning(f"Wallets ({len(wallets)}) less than accounts ({len(accounts)})")
    
    logger.info(f"Accounts: {len(accounts)}, wallets: {len(wallets)}")
    
    # Link wallets to accounts
    tasks = []
    for i, (account, wallet) in enumerate(zip(accounts, wallets)):
        # Format: email:password:imap_password
        parts = account.split(":")
        if len(parts) < 2:
            logger.error(f"Invalid account format: {account}")
            continue
        
        email = parts[0]
        
        # Check domain support
        if not is_domain_supported(email):
            domain = email.split('@')[-1]
            logger.warning(f"Domain {domain} not found in email_config.yaml, skipping {email}")
            continue
        
        # Check token in database
        token = await tokens_db.get_token(email)
        if not token:
            logger.warning(f"No token for {email}, run login first (mode 4)")
            continue
        
        if len(parts) == 2:
            password = parts[1]
            imap_password = password
        elif len(parts) == 3:
            password = parts[1]
            imap_password = parts[2]
        else:
            password = parts[1]
            imap_password = ":".join(parts[2:])
            
        proxy = proxies[i % len(proxies)] if proxies else None
        
        task = link_wallet_task(i + 1, email, password, imap_password, wallet, proxy, tokens_db)
        tasks.append(task)
    
    if not tasks:
        logger.error("No tasks to execute")
        return
    
    # Execute with concurrency limit
    semaphore = asyncio.Semaphore(AUTH_THREADS)
    
    async def limited_task(task):
        async with semaphore:
            return await task
    
    results = await asyncio.gather(*[limited_task(t) for t in tasks], return_exceptions=True)
    
    success = sum(1 for r in results if r is True)
    logger.info(f"Linking completed: {success}/{len(tasks)} successful")


async def worker_task(_id, account: str, proxy: str = None, db: AccountsDB = None, tokens_db: TokensDB = None):
    try:
        email, password = account.split(":")[:2]
    except ValueError:
        logger.error(f"{_id} | Invalid account format: {account}. Should be email:password")
        return False

    grass = None

    try:
        user_agent = ua
        current_node_type = NODE_TYPE

        grass = Grass(
            _id=_id,
            email=email,
            password=password,
            proxy=proxy,
            db=db,
            tokens_db=tokens_db,
            user_agent=user_agent,
            node_type=current_node_type
        )

        # Login only mode
        if LOGIN_ONLY_MODE:
            await grass.login_only()
            return True

        # Get token from database for farming and claim rewards modes
        token = await tokens_db.get_token(email) if tokens_db else None
        if not token:
            logger.warning(f"{_id} | No token for {email}, skipping...")
            return False
            
        # Set token manually
        grass.website_headers['Authorization'] = token
        
        # Get user_id via retrieve_user
        user_info = await grass.retrieve_user()
        user_id = None
        
        if user_info and not user_info.get('error'):
            if user_info.get('data', {}).get('userId'):
                user_id = user_info['data']['userId']
            elif user_info.get('result', {}).get('data', {}).get('userId'):
                user_id = user_info['result']['data']['userId']
            elif user_info.get('data', {}).get('id'):
                user_id = user_info['data']['id']
            elif user_info.get('result', {}).get('data', {}).get('id'):
                user_id = user_info['result']['data']['id']
                
        if not user_id:
            logger.warning(f"{_id} | Failed to get user_id for {email}, skipping...")
            return False

        # Farming mode
        if MINING_MODE:
            await asyncio.sleep(random.uniform(1, 2) * _id)
            logger.info(f"Starting №{_id} | {email} | {proxy} | Mode: {current_node_type}")
            await grass.start(user_id)
        else:
            # Claim rewards mode - also without login
            await asyncio.sleep(random.uniform(1, 3))
            logger.info(f"Starting №{_id} | {email} | {proxy}")
            await grass.claim_rewards_only()

        return True
    except LoginException as e:
        logger.warning(f"{_id} | {e}")
    except aiohttp.ClientError as e:
        logger.warning(f"{_id} | Some connection error: {e}...")
    except Exception as e:
        logger.error(f"{_id} | not handled exception | error: {e} {traceback.format_exc()}")
    finally:
        if grass:
            await grass.session.close()


async def main():
    # Create menu manager instance
    menu_manager = MenuManager()
    choice = menu_manager.show_menu()
    global MINING_MODE, CLAIM_REWARDS_ONLY, NODE_TYPE, LOGIN_ONLY_MODE, LINK_WALLETS_MODE
    
    # Modes disabled by default
    LOGIN_ONLY_MODE = False
    LINK_WALLETS_MODE = False

    if choice == 1:  # Farm 1.25x
        MINING_MODE = True
        CLAIM_REWARDS_ONLY = False
        NODE_TYPE = "1_25x"
        menu_manager.show_mode_selected("Farm 1.25x")
    elif choice == 2:  # Farm 1x
        MINING_MODE = True
        CLAIM_REWARDS_ONLY = False
        NODE_TYPE = "1x"
        menu_manager.show_mode_selected("Farm 1x")
    elif choice == 3:  # Claim rewards
        MINING_MODE = False
        CLAIM_REWARDS_ONLY = True
        menu_manager.show_mode_selected("Claim rewards")
    elif choice == 4:  # Login only
        MINING_MODE = False
        CLAIM_REWARDS_ONLY = False
        LOGIN_ONLY_MODE = True
        menu_manager.show_mode_selected("Login only (update tokens)")
    elif choice == 5:  # Link wallets
        MINING_MODE = False
        CLAIM_REWARDS_ONLY = False
        LINK_WALLETS_MODE = True
        menu_manager.show_mode_selected("Link wallets")
    elif choice == 6:  # Exit
        menu_manager.show_exit_message()
        return

    accounts = file_to_list(ACCOUNTS_FILE_PATH)

    if not accounts and not LINK_WALLETS_MODE:
        logger.warning("No accounts found!")
        return

    # If Claim rewards mode selected, remove duplicate accounts
    if CLAIM_REWARDS_ONLY:
        original_count = len(accounts)
        accounts = remove_duplicate_accounts(accounts)
        unique_count = len(accounts)

        if original_count != unique_count:
            logger.info(
                f"Removed {original_count - unique_count} duplicate accounts. Processing {unique_count} unique accounts.")

            # Create temp file with unique accounts for AutoReger
            temp_accounts_file = ACCOUNTS_FILE_PATH + ".temp"
            with open(temp_accounts_file, 'w') as f:
                for account in accounts:
                    f.write(f"{account}\n")

            accounts_file_for_autoreger = temp_accounts_file
        else:
            accounts_file_for_autoreger = ACCOUNTS_FILE_PATH
    else:
        accounts_file_for_autoreger = ACCOUNTS_FILE_PATH

    proxies = [Proxy.from_str(proxy).as_url for proxy in file_to_list(PROXIES_FILE_PATH)]

    # Remove proxy database only if not in login mode
    if not LOGIN_ONLY_MODE:
        try:
            if os.path.exists(PROXY_DB_PATH):
                os.remove(PROXY_DB_PATH)
        except PermissionError:
            logger.warning(f"Cannot remove {PROXY_DB_PATH}, file is in use")

    db = AccountsDB(PROXY_DB_PATH)
    await db.connect()
    
    # Initialize tokens database (DO NOT delete it on each run!)
    tokens_db = TokensDB(TOKENS_DB_PATH)
    await tokens_db.connect()

    # Wallet linking mode - separate logic
    if LINK_WALLETS_MODE:
        logger.info("__LINK_WALLETS__ MODE")
        await run_link_wallets(tokens_db, proxies)
        await db.close_connection()
        await tokens_db.close_connection()
        return

    for i, account in enumerate(accounts):
        email = account.split(":")[0]
        proxy = proxies[i] if len(proxies) > i else None

        if await db.proxies_exist(proxy) or not proxy:
            continue

        await db.add_account(email, proxy)

    await db.delete_all_from_extra_proxies()
    await db.push_extra_proxies(proxies[len(accounts):])

    autoreger = AutoReger.get_accounts(
        (accounts_file_for_autoreger, PROXIES_FILE_PATH),
        with_id=True,
        static_extra=(db, tokens_db)
    )

    # Remove temp file if it was created
    if CLAIM_REWARDS_ONLY and original_count != unique_count:
        try:
            os.remove(temp_accounts_file)
        except:
            pass

    threads = THREADS

    if LOGIN_ONLY_MODE:
        msg = "__LOGIN__ MODE"
        threads = AUTH_THREADS
    elif CLAIM_REWARDS_ONLY:
        msg = "__CLAIM__ MODE"
    else:
        msg = "__MINING__ MODE"
        threads = len(autoreger.accounts)

    logger.info(f"{msg} | Threads: {threads}")

    await autoreger.start(worker_task, threads)

    await db.close_connection()
    await tokens_db.close_connection()


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        bot_info("GRASS   6.1.3")
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    else:
        bot_info("GRASS   6.1.3")
        asyncio.run(main())
