# Captcha service settings
CAPTCHA_SERVICE = "capmonster"  # Captcha solving service (available: 2captcha, capmonster, anticaptcha, cflsolver)
CAPTCHA_API_KEY = "api"  # API key for the service

CFLSOLVER_BASE_URL = "http://localhost"  # URL for local CFLSolver API

DEBUG_LOGS = False

THREADS = 5  # for claim rewards mode / approve email mode
AUTH_THREADS = 2  # thread limit for authorization (login only mode)
MIN_PROXY_SCORE = 50  # Put MIN_PROXY_SCORE = 0 not to check proxy score (if site is down)

NODE_TYPE = "1_25x"  # default value, overwritten by menu selection

# WebSocket configuration
USE_WSS = False  # True for WSS (secure connection), False for WS

STOP_ACCOUNTS_WHEN_SITE_IS_DOWN = True  # stop account for 20 minutes, to reduce proxy traffic usage
CHECK_POINTS = True  # show point for each account every nearly 10 minutes
SHOW_LOGS_RARELY = False  # not always show info about actions to decrease pc influence

# Default modes
CLAIM_REWARDS_ONLY = False
MINING_MODE = True

########################################

ACCOUNTS_FILE_PATH = 'data/accounts.txt'
PROXIES_FILE_PATH = 'data/proxies.txt'
WALLETS_FILE_PATH = 'data/wallets.txt'
ACCOUNTS_TO_LINK_PATH = 'data/acc_to_link_wallet.txt'
PROXY_DB_PATH = 'data/proxies_stats.db'
TOKENS_DB_PATH = 'data/auth_tokens.db'


