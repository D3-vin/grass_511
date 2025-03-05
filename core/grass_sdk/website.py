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


class GrassRest(BaseClient):
    def __init__(self, email: str, password: str, user_agent: str = None, proxy: str = None):
        super().__init__(user_agent, proxy)
        self.email = email
        self.password = password
        self.id = None

    async def enter_account(self):
        res_json = await self.handle_login()
        self.website_headers['Authorization'] = res_json['result']['data']['accessToken']

        return res_json['result']['data']['userId']

    @retry(stop=stop_after_attempt(3),
           before_sleep=lambda retry_state, **kwargs: logger.info(f"Retrying... {retry_state.outcome.exception()}"),
           reraise=True)
    async def retrieve_user(self):
        url = 'https://api.getgrass.io/retrieveUser'

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
        url = 'https://api.getgrass.io/claimReward'

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
        url = 'https://api.getgrass.io/users/earnings/epochs'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)

        logger.debug(f"{self.id} | Get Points response: {await response.text()}")

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
        url = 'https://api.getgrass.io/login'

        json_data = {
            'password': self.password,
            'username': self.email,
        }

        response = await self.session.post(url, headers=self.website_headers, data=json.dumps(json_data),
                                           proxy=self.proxy)
        try:
            res_json = await response.json()
            if res_json.get("error") is not None:
                raise LoginException(f"{self.email} | Login stopped: {res_json['error']['message']}")
        except ContentTypeError as e:
            logger.info(f"{self.id} | Login response: Could not parse response as JSON. '{e}'")

        resp_text = await response.text()

        # Check if the response is HTML
        if "doctype html" in resp_text.lower():
            raise CloudFlareHtmlException(f"{self.id} | Detected Cloudflare HTML response: {resp_text}")

        if response.status == 403:
            raise ProxyBlockedException(f"Login response: {resp_text}")
        if response.status != 200:
            raise ClientConnectionError(f"Login response: | {resp_text}")

        return await response.json()

    async def get_browser_id(self):
        res_json = await self.get_user_info()
        return res_json['data']['devices'][0]['device_id']

    async def get_user_info(self):
        url = 'https://api.getgrass.io/users/dash'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)
        return await response.json()

    async def get_devices_info(self):
        url = 'https://api.getgrass.io/activeIps'  # /extension/user-score /activeDevices

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)
        return await response.json()

    async def get_device_info(self, device_id: str):
        url = f"https://api.getgrass.io/retrieveDevice?input=%7B%22deviceId%22:%22{device_id}%22%7D"
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
        url = 'https://api.getgrass.io/users/devices'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)

        if response.status != 200:
            raise ProxyScoreNotFoundException(f"Get proxy score response: {await response.text()}")

        return await response.json()

    async def update_ip(self):
        return await self.get_ip()

    async def get_ip(self):
        url = 'https://api.getgrass.io/ip'

        response = await self.session.get(url, headers=self.website_headers, proxy=self.proxy)

        return await response.json()