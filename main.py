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
from core.ui.menu import MenuManager
from data.config import ACCOUNTS_FILE_PATH, PROXIES_FILE_PATH, THREADS, AUTH_THREADS, \
    CLAIM_REWARDS_ONLY, MINING_MODE, \
    PROXY_DB_PATH, TOKENS_DB_PATH, MIN_PROXY_SCORE, CHECK_POINTS, STOP_ACCOUNTS_WHEN_SITE_IS_DOWN, \
    SHOW_LOGS_RARELY, NODE_TYPE

ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'


def bot_info(name: str = ""):
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleTitleW(f"{name}")
    
    # Создаем экземпляр менеджера меню и отображаем приветствие
    menu_manager = MenuManager()
    menu_manager.display_welcome()


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

        # Режим только логина
        if LOGIN_ONLY_MODE:
            await grass.login_only()
            return True

        # Получаем токен из базы для режимов фарминга и claim rewards
        token = await tokens_db.get_token(email) if tokens_db else None
        if not token:
            logger.warning(f"{_id} | Нет токена для {email}, пропуск...")
            return False
            
        # Устанавливаем токен вручную
        grass.website_headers['Authorization'] = token
        
        # Получаем user_id через retrieve_user
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
            logger.warning(f"{_id} | Не удалось получить user_id для {email}, пропуск...")
            return False

        # Режим фарминга
        if MINING_MODE:
            await asyncio.sleep(random.uniform(1, 2) * _id)
            logger.info(f"Starting №{_id} | {email} | {proxy} | Mode: {current_node_type}")
            await grass.start(user_id)
        else:
            # Режим claim rewards - тоже без логина
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
    # Создаем экземпляр менеджера меню
    menu_manager = MenuManager()
    choice = menu_manager.show_menu()
    global MINING_MODE, CLAIM_REWARDS_ONLY, NODE_TYPE, LOGIN_ONLY_MODE
    
    # По умолчанию режим логина выключен
    LOGIN_ONLY_MODE = False

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
    elif choice == 5:  # Exit
        menu_manager.show_exit_message()
        return

    accounts = file_to_list(ACCOUNTS_FILE_PATH)

    if not accounts:
        logger.warning("No accounts found!")
        return

    # Если выбран режим Claim rewards, удаляем дубликаты аккаунтов
    if CLAIM_REWARDS_ONLY:
        original_count = len(accounts)
        accounts = remove_duplicate_accounts(accounts)
        unique_count = len(accounts)

        if original_count != unique_count:
            logger.info(
                f"Removed {original_count - unique_count} duplicate accounts. Processing {unique_count} unique accounts.")

            # Создаем временный файл с уникальными аккаунтами для AutoReger
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

    # Удаляем базу прокси только если это не режим логина
    if not LOGIN_ONLY_MODE:
        try:
            if os.path.exists(PROXY_DB_PATH):
                os.remove(PROXY_DB_PATH)
        except PermissionError:
            logger.warning(f"Cannot remove {PROXY_DB_PATH}, file is in use")

    db = AccountsDB(PROXY_DB_PATH)
    await db.connect()
    
    # Инициализируем базу данных токенов (НЕ удаляем ее при каждом запуске!)
    tokens_db = TokensDB(TOKENS_DB_PATH)
    await tokens_db.connect()

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

    # Удаляем временный файл, если он был создан
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
        bot_info("GRASS   5.5.1")
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    else:
        bot_info("GRASS   5.5.1")
        asyncio.run(main())
