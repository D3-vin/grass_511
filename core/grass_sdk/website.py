import ast
import asyncio
import json
import random
import time

from aiohttp import ContentTypeError, ClientConnectionError
from tenacity import retry, stop_after_attempt, wait_random, retry_if_not_exception_type

from core.utils import logger
from core.utils.exception import LoginException, ProxyBlockedException, CloudFlareHtmlException, ProxyScoreNotFoundException
from core.utils.session import BaseClient
from core.utils.captcha import ServiceCapmonster, ServiceAnticaptcha, Service2Captcha, CFLSolver
from data.config import CAPTCHA_SERVICE, CAPTCHA_API_KEY, CFLSOLVER_BASE_URL

# Static captcha settings for Grass
CAPTCHA_WEBSITE_KEY = "0x4AAAAAABlfL-m2jw53nwb9"
CAPTCHA_WEBSITE_URL = "https://app.grass.io/login"
from httpx import AsyncClient


class GrassRest(BaseClient):
    def __init__(self, email: str, password: str, user_agent: str = None, proxy: str = None, db=None, tokens_db=None):
        super().__init__(user_agent, proxy)
        self.email = email
        self.password = password
        self.id = None
        self.db = db
        self.tokens_db = tokens_db  # Token database field

    async def enter_account(self):
        """Login to account with refresh token support"""
        if self.tokens_db:
            # Try to use saved access token
            token = await self.tokens_db.get_token(self.email)
            if token:
                self.website_headers['Authorization'] = token
                user_id = await self._get_user_id_from_response()
                if user_id:
                    return user_id
                
                # Access token invalid — try refresh
                user_id = await self._try_refresh_token()
                if user_id:
                    return user_id
        
        # Refresh failed or no tokens — full login
        return await self._full_login()
    
    async def _get_user_id_from_response(self):
        """Extracts user_id from retrieve_user response"""
        try:
            user_info = await self.retrieve_user()
            if not user_info:
                return None
            if user_info.get('error'):
                return None
            
            # Try different response structures
            data = user_info.get('data') or {}
            if not data:
                data = user_info.get('result', {}).get('data') or {}
            
            return data.get('userId') or data.get('id')
        except Exception as e:
            logger.debug(f"{self.email} | _get_user_id_from_response error: {e}")
            return None
    
    async def _try_refresh_token(self):
        """Tries to update access token via refresh token"""
        if not self.tokens_db:
            return None
        
        refresh_token = await self.tokens_db.get_refresh_token(self.email)
        if not refresh_token:
            return None
        
        try:
            new_tokens = await self.refresh_access_token(refresh_token)
            if new_tokens:
                access_token = new_tokens.get('accessToken')
                new_refresh = new_tokens.get('refreshToken')
                
                self.website_headers['Authorization'] = access_token
                await self.tokens_db.save_token(self.email, access_token)
                if new_refresh:
                    await self.tokens_db.save_refresh_token(self.email, new_refresh)
                
                return await self._get_user_id_from_response()
        except Exception as e:
            logger.warning(f"{self.email} | Refresh token failed: {e}")
        
        return None
    
    async def _full_login(self):
        """Full login with saving both tokens"""
        res_json = await self.handle_login()
        data = res_json['result']['data']
        
        access_token = data['accessToken']
        refresh_token = data.get('refreshToken')
        user_id = data['userId']
        
        self.website_headers['Authorization'] = access_token
        
        if self.tokens_db:
            await self.tokens_db.save_token(self.email, access_token)
            if refresh_token:
                await self.tokens_db.save_refresh_token(self.email, refresh_token)
        
        return user_id
    
    async def refresh_access_token(self, refresh_token):
        """Updates access token using refresh token"""
        url = 'https://api.grass.io/refreshToken'
        
        json_data = {'refreshToken': refresh_token}
        
        response = await self.session.post(
            url, 
            headers=self.website_headers, 
            data=json.dumps(json_data),
            proxy=self.proxy
        )
        
        if response.status != 200:
            return None
        
        res_json = await response.json()
        if res_json.get('error'):
            return None
        
        return res_json.get('result', {}).get('data')

    async def is_token_valid(self, token):
        """Checks if authorization token is valid"""
        original_token = self.website_headers.get('Authorization')
        self.website_headers['Authorization'] = token
        
        try:
            response = await self.retrieve_user()
            valid = bool(response and not response.get('error'))
        except Exception:
            valid = False
        
        # Restore original token if it existed
        if original_token:
            self.website_headers['Authorization'] = original_token
        elif valid is False:
            # Remove invalid token from headers
            self.website_headers.pop('Authorization', None)
            
        return valid

    @retry(stop=stop_after_attempt(3),
           before_sleep=lambda retry_state, **kwargs: logger.info(f"Retrying... {retry_state.outcome.exception()}"),
           reraise=True)
    async def retrieve_user(self):
        url = 'https://api.grass.io/retrieveUser'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)

        return await response.json()

    async def claim_rewards_handler(self):
        handler = retry(
            stop=stop_after_attempt(3),
            before_sleep=lambda retry_state, **kwargs: logger.info(f"{self.id} | Retrying to claim rewards... "
                                                                   f"Continue..."),
            wait=wait_random(5, 7),
            reraise=True
        )

        for _ in range(8):
            await handler(self.claim_reward_for_tier)()
            await asyncio.sleep(random.uniform(1, 3))

        return True

    async def claim_reward_for_tier(self):
        url = 'https://api.grass.io/claimReward'

        response = await self.session.post(url, headers=self.website_headers, proxy=self.proxy)

        assert (await response.json()).get("result") == {}
        return True

    async def get_points_handler(self):
        handler = retry(
            stop=stop_after_attempt(3),
            before_sleep=lambda retry_state, **kwargs: logger.info(f"{self.id} | Retrying to get points... "
                                                                   f"Continue..."),
            wait=wait_random(5, 7),
            reraise=True
        )

        return await handler(self.get_points)()

    async def get_points(self):
        url = 'https://api.grass.io/users/earnings/epochs'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)

        #logger.debug(f"{self.id} | Get Points response: {await response.text()}")

        res_json = await response.json()
        points = res_json.get('data', {}).get('epochEarnings', [{}])[0].get('totalCumulativePoints')

        if points is not None:
            return points
        elif points := res_json.get('error', {}).get('message'):
            if points == "User epoch earning not found.":
                return 0
            return points
        else:
            return "Can't get points."

    async def get_airdrop_stats_handler(self):
        handler = retry(
            stop=stop_after_attempt(3),
            before_sleep=lambda retry_state, **kwargs: logger.info(
                f"{self.id} | Retrying to get airdrop allocation... Continue..."
            ),
            wait=wait_random(5, 7),
            reraise=True
        )

        return await handler(self.get_airdrop_allocation)()

    async def get_airdrop_allocation(self):
        url = 'https://api.grass.io/airdropStats'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)
        res_json = await response.json()

        stats = res_json.get('result', {}).get('data', {}).get('stats', {}) if isinstance(res_json, dict) else {}
        allocation = stats.get('allocation')

        if allocation is not None:
            return allocation

        err_msg = res_json.get('error', {}).get('message') if isinstance(res_json, dict) else None
        return err_msg or "Can't get airdrop allocation."

    async def handle_login(self):
        handler = retry(
            stop=stop_after_attempt(12),
            retry=retry_if_not_exception_type((LoginException, ProxyBlockedException)),
            before_sleep=lambda retry_state, **kwargs: logger.info(f"{self.id} | Login retrying... "
                                                                   f"{retry_state.outcome.exception()}"),
            wait=wait_random(8, 12),
            reraise=True
        )

        return await handler(self.login)()

    async def login(self):
        url = 'https://api.grass.io/login'

        # Get captcha token according to settings
        if CAPTCHA_SERVICE == "capmonster":
            cap_service = ServiceCapmonster(api_key=CAPTCHA_API_KEY, website_key=CAPTCHA_WEBSITE_KEY, website_url=CAPTCHA_WEBSITE_URL)
            token = await cap_service.solve_captcha()
        elif CAPTCHA_SERVICE == "anticaptcha":
            cap_service = ServiceAnticaptcha(api_key=CAPTCHA_API_KEY, website_key=CAPTCHA_WEBSITE_KEY, website_url=CAPTCHA_WEBSITE_URL)
            token = await cap_service.solve_captcha()
        elif CAPTCHA_SERVICE == "2captcha":
            cap_service = Service2Captcha(api_key=CAPTCHA_API_KEY, website_key=CAPTCHA_WEBSITE_KEY, website_url=CAPTCHA_WEBSITE_URL)
            token = await cap_service.solve_captcha()
        elif CAPTCHA_SERVICE == "cflsolver":
            cap_service = CFLSolver(
                api_key=CAPTCHA_API_KEY, 
                base_url=CFLSOLVER_BASE_URL,
                website_key=CAPTCHA_WEBSITE_KEY, 
                website_url=CAPTCHA_WEBSITE_URL
            )
            token = await cap_service.solve_captcha_auto()
        else:
            raise Exception(f"Unknown CAPTCHA_SERVICE: {CAPTCHA_SERVICE}")
        
        if not token:
            raise LoginException(f"{self.email} | Captcha token is empty (service={CAPTCHA_SERVICE})")

        json_data = {
            'password': self.password,
            'username': self.email,
            "recaptchaToken": token,
        }

        response = await self.session.post(url, headers=self.website_headers, data=json.dumps(json_data),
                                           proxy=self.proxy)
        try:
            res_json = await response.json()
            if res_json.get("error") is not None:
                raise LoginException(f"{self.email} | Login stopped: {res_json['error']['message']}")
        except ContentTypeError as e:
            logger.info(f"{self.id} | Login response: Could not parse response as JSON. '{e}'")

        #resp_text = await response.text()

        if response.status == 429:
            # Handle rate limiting
            retry_after = response.headers.get("Retry-After")
            retry_after = int(retry_after) if retry_after and retry_after.isdigit() else 5  # 5 seconds default
            logger.warning(f"{self.id} | Detected Cloudflare Rate limited. Retrying after {retry_after} seconds...")
            await asyncio.sleep(retry_after)
        # Check if the response is HTML
        #if "doctype html" in resp_text.lower():
        #    raise CloudFlareHtmlException(f"{self.id} | Detected Cloudflare HTML response: {resp_text}")

        if response.status == 403:
            raise ProxyBlockedException(f"Login response: {response.status}")
        if response.status != 200:
            raise ClientConnectionError(f"Login response: | {response.status}")

        return await response.json()

    async def get_browser_id(self):
        res_json = await self.get_user_info()
        return res_json['data']['devices'][0]['device_id']

    async def get_user_info(self):
        url = 'https://api.grass.io/users/dash'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)
        return await response.json()

    async def get_devices_info(self):
        url = 'https://api.grass.io/activeIps'  # /extension/user-score /activeDevices

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)
        return await response.json()

    async def get_device_info(self, device_id: str):
        url = f"https://api.grass.io/retrieveDevice?input=%7B%22deviceId%22:%22{device_id}%22%7D"
        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)
        return await response.json()

    async def get_proxy_score_by_device_handler(self, browser_id: str):
        handler = retry(
            stop=stop_after_attempt(3),
            before_sleep=lambda retry_state, **kwargs: logger.info(f"{self.id} | Retrying to get proxy score... "
                                                                   f"Continue..."),
            reraise=True
        )

        return await handler(lambda: self.get_proxy_score_via_device(browser_id))()

    async def get_proxy_score_via_device(self, device_id: str):
        res_json = await self.get_device_info(device_id)
        return res_json.get("result", {}).get("data", {}).get("ipScore", None)

    async def get_proxy_score_via_devices_by_device_handler(self):
        handler = retry(
            stop=stop_after_attempt(3),
            before_sleep=lambda retry_state, **kwargs: logger.info(f"{self.id} | Retrying to get proxy score... "
                                                                   f"Continue..."),
            reraise=True
        )

        return await handler(self.get_proxy_score_via_devices_v1)()

    async def get_proxy_score_via_devices_v1(self):
        res_json = await self.get_devices_info()

        if not (isinstance(res_json, dict) and res_json.get("result", {}).get("data") is not None):
            return

        devices = res_json['result']['data']
        await self.update_ip()

        return next((device['ipScore'] for device in devices
                     if device['ipAddress'] == self.ip), None)

    async def get_proxy_score_via_devices(self):
        url = 'https://api.grass.io/users/devices'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)

        if response.status != 200:
            raise ProxyScoreNotFoundException(f"Get proxy score response: {await response.status}")

        return await response.json()

    async def update_ip(self):
        return await self.get_ip()

    async def get_ip(self):
        url = 'https://api.grass.io/ip'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)

        return await response.json()

    # === Wallet methods ===
    
    async def approve_wallet(self, signed_message, public_key, wallet_address, timestamp):
        """Confirms wallet linking with signed message"""
        url = 'https://api.grass.io/verifySignedMessage'
        
        json_data = {
            'signedMessage': signed_message,
            'publicKey': public_key,
            'walletAddress': wallet_address,
            'timestamp': timestamp,
            'isLedger': False,
            'isAfterCountdown': True
        }
        
        response = await self.session.post(
            url, 
            headers=self.website_headers, 
            data=json.dumps(json_data),
            proxy=self.proxy
        )
        return await response.json()
    
    async def send_wallet_email_verification(self):
        """Sends email for wallet linking verification"""
        url = 'https://api.grass.io/sendWalletAddressEmailVerification'
        
        response = await self.session.post(
            url, 
            headers=self.website_headers,
            proxy=self.proxy
        )
        return await response.json()
    
    async def confirm_wallet_address(self, verification_token):
        """Confirms wallet address with token from email"""
        url = 'https://api.grass.io/confirmWalletAddress'
        
        headers = self.website_headers.copy()
        headers['Authorization'] = verification_token
        
        response = await self.session.post(url, headers=headers, proxy=self.proxy)
        return await response.json()
    
    async def get_linked_wallet(self):
        """Gets linked wallet from user data"""
        user_info = await self.retrieve_user()
        if user_info and not user_info.get('error'):
            data = user_info.get('result', {}).get('data', {})
            return data.get('walletAddress')
        return None