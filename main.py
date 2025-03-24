import asyncio
import ctypes
import os
import random
import sys
import traceback

import aiohttp
from art import text2art
from termcolor import colored, cprint
from fake_useragent import UserAgent

from better_proxy import Proxy

from core import Grass
from core.autoreger import AutoReger
from core.utils import logger, file_to_list
from core.utils.accounts_db import AccountsDB
from core.utils.exception import LoginException
from core.utils.file_manager import remove_duplicate_accounts, str_to_file
from data.config import ACCOUNTS_FILE_PATH, PROXIES_FILE_PATH, THREADS, \
    CLAIM_REWARDS_ONLY, MINING_MODE, \
    PROXY_DB_PATH, MIN_PROXY_SCORE, CHECK_POINTS, STOP_ACCOUNTS_WHEN_SITE_IS_DOWN, \
    SHOW_LOGS_RARELY, NODE_TYPE

ua = UserAgent(platforms=['desktop'])


def bot_info(name: str = ""):
    cprint(text2art(name), 'green')

    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleTitleW(f"{name}")

    print(
        f"{colored('Public script / Not for sale', color='light_red')}\n"
        f"{colored('Паблик скрипт / Не для продажи', color='light_red')}\n"
        f"{colored('source EnJoYeR mod by ', color='light_yellow')}{colored('@Tell_Bip', color='blue')}\n"
        f"{colored('Telegram chat: https://t.me/+b0BPbs7V1aE2NDFi', color='light_green')}"
    )


def show_menu():
    print("\n" + "=" * 50)
    print(colored("Choose mode:", "light_cyan"))
    print(colored("1) Farm 1.25x", "light_green"))
    print(colored("2) Farm 1x", "light_green"))
    print(colored("3) Claim rewards", "light_yellow"))
    print(colored("4) Exit", "light_red"))
    print("=" * 50 + "\n")

    while True:
        try:
            choice = int(input(colored("Enter the number (1-4): ", "light_cyan")))
            if 1 <= choice <= 4:
                return choice
            else:
                print(colored("Error: enter a number from 1 to 4", "light_red"))
        except ValueError:
            print(colored("Error: enter a number from 1 to 4", "light_red"))


async def worker_task(_id, account: str, proxy: str = None, db: AccountsDB = None):
    try:
        email, password = account.split(":")[:2]
    except ValueError:
        logger.error(f"{_id} | Invalid account format: {account}. Should be email:password")
        return False

    grass = None
    # local_db = None

    try:
        # Создаем локальную копию базы данных для каждого воркера
        # local_db = AccountsDB(PROXY_DB_PATH)
        # await local_db.connect()

        # user_agent = UserAgent(os=['windows', 'macos', 'linux'])
        # user_agent = user_agent.chrome

        user_agent = str(ua.chrome)

        # Получаем текущий выбранный режим из глобальных переменных
        current_node_type = NODE_TYPE

        grass = Grass(
            _id=_id,
            email=email,
            password=password,
            proxy=proxy,
            db=db,
            user_agent=user_agent,
            node_type=current_node_type  # Передаем выбранный режим
        )

        if MINING_MODE:
            await asyncio.sleep(random.uniform(1, 2) * _id)
            logger.info(f"Starting №{_id} | {email} | {password} | {proxy} | Mode: {current_node_type}")
        else:
            await asyncio.sleep(random.uniform(1, 3))
            logger.info(f"Starting №{_id} | {email} | {password} | {proxy}")

        if CLAIM_REWARDS_ONLY:
            await grass.claim_rewards()
        else:
            await grass.start()

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
    # Показываем меню выбора режима
    choice = show_menu()

    # Устанавливаем режим в зависимости от выбора
    global MINING_MODE, CLAIM_REWARDS_ONLY, NODE_TYPE

    if choice == 1:  # Farm 1.25x
        MINING_MODE = True
        CLAIM_REWARDS_ONLY = False
        NODE_TYPE = "1_25x"
        logger.info("Selected mode: Farm 1.25x")
    elif choice == 2:  # Farm 1x
        MINING_MODE = True
        CLAIM_REWARDS_ONLY = False
        NODE_TYPE = "1x"
        logger.info("Selected mode: Farm 1x")
    elif choice == 3:  # Claim rewards
        MINING_MODE = False
        CLAIM_REWARDS_ONLY = True
        logger.info("Selected mode: Claim rewards")
    elif choice == 4:  # Exit
        logger.info("Exiting program")
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

    #### delete DB if it exists to clean up
    try:
        if os.path.exists(PROXY_DB_PATH):
            os.remove(PROXY_DB_PATH)
    except PermissionError:
        logger.warning(f"Cannot remove {PROXY_DB_PATH}, file is in use")

    db = AccountsDB(PROXY_DB_PATH)
    await db.connect()

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
        static_extra=(db,)
    )

    # Удаляем временный файл, если он был создан
    if CLAIM_REWARDS_ONLY and original_count != unique_count:
        try:
            os.remove(temp_accounts_file)
        except:
            pass

    threads = THREADS

    if CLAIM_REWARDS_ONLY:
        msg = "__CLAIM__ MODE"
    else:
        msg = "__MINING__ MODE"
        threads = len(autoreger.accounts)

    logger.info(msg)

    await autoreger.start(worker_task, threads)

    await db.close_connection()


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        bot_info("GRASS   5.1.1")
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    else:
        bot_info("GRASS   5.1.1")
        asyncio.run(main())
