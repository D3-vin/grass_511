# Captcha service settings
CAPTCHA_SERVICE = "2captcha"  # Captcha solving service (available: 2captcha, capmonster, anticaptcha, cflsolver)
CAPTCHA_API_KEY = "api"  # API key for the service

# Captcha site settings
CAPTCHA_WEBSITE_KEY = "0x4AAAAAABlfL-m2jw53nwb9"
CAPTCHA_WEBSITE_URL = "https://app.grass.io/login"

CFLSOLVER_BASE_URL = "http://localhost:5000"  # URL для локального API CFLSolver

THREADS = 5  # for claim rewards mode / approve email mode
AUTH_THREADS = 2  # ограничение потоков для авторизации (login only mode)
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
TOKENS_DB_PATH = 'data/auth_tokens.db'


