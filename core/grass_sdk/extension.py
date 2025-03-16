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
from data.config import ACCOUNTS_FILE_PATH, PROXIES_FILE_PATH, THREADS, \
    CLAIM_REWARDS_ONLY, MINING_MODE, \
    PROXY_DB_PATH, MIN_PROXY_SCORE, CHECK_POINTS, STOP_ACCOUNTS_WHEN_SITE_IS_DOWN, \
    SHOW_LOGS_RARELY, NODE_TYPE

ua = UserAgent(platforms=['desktop'])


def bot_info(name: str = ""):
    cprint(text2art(name), 'green')

    # if sys.platform == 'win32':
    # ctypes.windll.kernel32.SetConsoleTitleW(f"{name}")

    print(
        f"{colored('Public script / Not for sale', color='light_red')}\n"
        f"{colored('Паблик скрипт / Не для продажи', color='light_red')}\n"
        f"{colored('sourse EnJoYeR mod by TellBip', color='light_yellow')} "
        f"{colored('https://t.me/+b0BPbs7V1aE2NDFi', color='light_green')}"
    )


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

        grass = Grass(
            _id=_id,
            email=email,
            password=password,
            proxy=proxy,
            db=db,
            user_agent=user_agent
        )

        if MINING_MODE:
            await asyncio.sleep(random.uniform(1, 2) * _id)
            logger.info(f"Starting №{_id} | {email} | {password} | {proxy}")
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
    accounts = file_to_list(ACCOUNTS_FILE_PATH)

    if not accounts:
        logger.warning("No accounts found!")
        return

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
        (ACCOUNTS_FILE_PATH, PROXIES_FILE_PATH),
        with_id=True,
        static_extra=(db,)
    )

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
        bot_info("GRASS 5.1.1")
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    else:
        bot_info("GRASS 5.1.1")
        asyncio.run(main())
