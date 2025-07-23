import asyncio
import re
from typing import Optional
from capmonster_python import CapmonsterClient, TurnstileTask
from twocaptcha import TwoCaptcha
from httpx import AsyncClient
from anticaptchaofficial.turnstileproxyless import *

class ServiceCapmonster:
    def __init__(self, api_key, website_key, website_url):
        self.api_key = api_key
        self.website_key = website_key
        self.website_url = website_url
        self.client = CapmonsterClient(api_key=self.api_key)

    async def solve_captcha(self):
        task = TurnstileTask(
            websiteURL=self.website_url,
            websiteKey=self.website_key
        )
        task_id = await self.client.create_task_async(task)
        result = await self.client.join_task_result_async(task_id)
        return result

class ServiceAnticaptcha:
    def __init__(self, api_key, website_key, website_url):
        self.api_key = api_key
        self.website_key = website_key
        self.website_url = website_url
        self.solver = turnstileProxyless()
        self.solver.set_verbose(1)
        self.solver.set_key(self.api_key)
        self.solver.set_website_url(self.website_url)
        self.solver.set_website_key(self.website_key)
    
    def get_captcha_token(self):
        captcha_token = self.solver.solve_and_return_solution()
        return captcha_token

    async def get_captcha_token_async(self):
        return await asyncio.to_thread(self.get_captcha_token)

    # Add alias for compatibility
    async def solve_captcha(self):
        return await self.get_captcha_token_async()

class Service2Captcha:
    def __init__(self, api_key, website_key, website_url):
        self.solver = TwoCaptcha(api_key)
        self.website_key = website_key
        self.website_url = website_url
    def get_captcha_token(self):
        captcha_token = self.solver.turnstile(sitekey=self.website_key, url=self.website_url)

        if 'code' in captcha_token:
            captcha_token = captcha_token['code']

        return captcha_token

    async def get_captcha_token_async(self):
        return await asyncio.to_thread(self.get_captcha_token)

    # Add alias for compatibility
    async def solve_captcha(self):
        return await self.get_captcha_token_async()
