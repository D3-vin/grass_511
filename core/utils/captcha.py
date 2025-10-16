import asyncio
import re
from typing import Optional
from capmonster_python import RecaptchaV2Task
from twocaptcha import TwoCaptcha
from httpx import AsyncClient
from curl_cffi.requests import AsyncSession
from data.config import CFLSOLVER_BASE_URL
from anticaptchaofficial.recaptchav2proxyless import *

class ServiceCapmonster:
    def __init__(self, api_key, website_key, website_url):
        self.api_key = api_key
        self.website_key = website_key
        self.website_url = website_url
        self.client = RecaptchaV2Task(client_key=self.api_key)

    async def solve_captcha(self):
        task_id = self.client.create_task(
            website_url=self.website_url,
            website_key=self.website_key
        )
        result = await self.client.join_task_result_async(task_id)
        return result

class ServiceAnticaptcha:
    def __init__(self, api_key, website_key, website_url):
        self.api_key = api_key
        self.website_key = website_key
        self.website_url = website_url
        self.solver = recaptchaV2Proxyless()
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
        captcha_token = self.solver.recaptcha(sitekey=self.website_key, url=self.website_url)

        if 'code' in captcha_token:
            captcha_token = captcha_token['code']

        return captcha_token

    async def get_captcha_token_async(self):
        return await asyncio.to_thread(self.get_captcha_token)

    # Add alias for compatibility
    async def solve_captcha(self):
        return await self.get_captcha_token_async()

class CFLSolver:
    def __init__(
            self,
            api_key: str,
            base_url: str,
            website_key: str,
            website_url: str,
            action: Optional[str] = None,
            cdata: Optional[str] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.website_key = website_key
        self.website_url = website_url
        self.action = action
        self.cdata = cdata

    async def create_session(self) -> AsyncSession:
        """Создает сессию для прямого подключения"""
        from curl_cffi.requests import AsyncSession
        return AsyncSession()

    async def create_turnstile_task(self, session: AsyncSession, sitekey: str, pageurl: str, action: Optional[str] = None, cdata: Optional[str] = None) -> Optional[str]:
        """Создает задачу для решения Turnstile капчи с использованием CapMonster API"""
        import json
        
        # Данные для запроса к CapMonster
        json_data = {
            "clientKey": self.api_key,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": pageurl,
                "websiteKey": sitekey
            }
        }
        
        # Добавляем дополнительные параметры если они есть
        if action:
            json_data["task"]["action"] = action
        if cdata:
            json_data["task"]["cdata"] = cdata

        try:
            response = await session.post(
                f"{self.base_url}/createTask",
                json=json_data,
                timeout=60
            )
            
            if response.status_code != 200:
                return None
                
            try:
                result = response.json()
            except ValueError:
                return None

            # Проверяем что result не None
            if result is None:
                return None

            # Проверяем на ошибки API
            if result.get("errorId") != 0:
                return None
                
            if "taskId" in result:
                task_id = str(result["taskId"])
                return task_id

            return None

        except Exception:
            return None

    async def get_task_result(self, session: AsyncSession, task_id: str) -> Optional[str]:
        """Получает результат решения капчи с CapMonster API"""
        import json
        
        max_attempts = 60  # Увеличиваем время ожидания до 60 попыток
        
        json_data = {
            "clientKey": self.api_key,
            "taskId": task_id
        }
        
        for attempt in range(max_attempts):
            try:
                response = await session.post(
                    f"{self.base_url}/getTaskResult",
                    json=json_data,
                    timeout=120,
                )

                if response.status_code != 200:
                    await asyncio.sleep(2)
                    continue

                try:
                    result = response.json()
                except ValueError:
                    await asyncio.sleep(2)
                    continue

                # Проверяем что result не None
                if result is None:
                    await asyncio.sleep(2)
                    continue

                # Проверяем статус обработки
                if result.get("status") == "processing":
                    await asyncio.sleep(5)
                    continue

                # Проверяем на ошибки API
                if result.get("errorId") != 0:
                    return None

                # Проверяем готовность решения
                if result.get("status") == "ready" and result.get("solution"):
                    solution = result["solution"].get("token")
                    
                    if solution and re.match(r'^[a-zA-Z0-9\.\-_]+$', solution):
                        return solution

                # Если решение еще не готово, ждем
                await asyncio.sleep(5)
                continue

            except Exception:
                await asyncio.sleep(2)
                continue

        return None

    async def solve_captcha(self, session: AsyncSession, action: Optional[str] = None, cdata: Optional[str] = None) -> Optional[str]:
        """Решает Cloudflare Turnstile капчу и возвращает токен используя CapMonster API"""
        # Используем переданные параметры или значения по умолчанию из конструктора
        action_to_use = action if action is not None else self.action
        cdata_to_use = cdata if cdata is not None else self.cdata
        
        task_id = await self.create_turnstile_task(
            session,
            self.website_key,
            self.website_url,
            action_to_use,
            cdata_to_use
        )
        
        if not task_id:
            return None

        return await self.get_task_result(session, task_id)

    # Добавляем алиас для совместимости
    async def get_captcha_token_async(self, session: AsyncSession, action: Optional[str] = None, cdata: Optional[str] = None):
        return await self.solve_captcha(session, action, cdata)

    async def solve_captcha_auto(self, action: Optional[str] = None, cdata: Optional[str] = None) -> Optional[str]:
        """Автоматически создает сессию и решает капчу"""
        session = await self.create_session()
        try:
            return await self.solve_captcha(session, action, cdata)
        finally:
            await session.close()