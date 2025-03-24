THREADS = 5  # for claim rewards mode / approve email mode
MIN_PROXY_SCORE = 50  # Put MIN_PROXY_SCORE = 0 not to check proxy score (if site is down)

NODE_TYPE = "1_25x"  # 1x, 1_25x, 2x

# WebSocket configuration
USE_WSS = False  # True для WSS (защищенное соединение), False для WS

STOP_ACCOUNTS_WHEN_SITE_IS_DOWN = True  # stop account for 20 minutes, to reduce proxy traffic usage
CHECK_POINTS = True  # show point for each account every nearly 10 minutes
SHOW_LOGS_RARELY = False  # not always show info about actions to decrease pc influence

# Default modes
CLAIM_REWARDS_ONLY = False
MINING_MODE = True

########################################

ACCOUNTS_FILE_PATH = 'data/accounts.txt'
PROXIES_FILE_PATH = 'data/proxies.txt'
PROXY_DB_PATH = 'data/proxies_stats.db'
