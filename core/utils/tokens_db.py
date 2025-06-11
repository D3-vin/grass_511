import aiosqlite
import asyncio
import os
from datetime import datetime

class TokensDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.cursor = None
        self.connection = None
        self.db_lock = asyncio.Lock()
        
        # Создаем директорию для базы данных, если она не существует
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        from core.utils import logger
        self.logger = logger

    async def connect(self):
        #self.logger.info(f"Подключение к базе данных токенов: {self.db_path}")
        exists = os.path.exists(self.db_path)
        
        #if exists:
            #self.logger.info(f"База данных токенов уже существует")
        #else:
            #self.logger.info(f"База данных токенов будет создана")
            
        self.connection = await aiosqlite.connect(self.db_path)
        self.cursor = await self.connection.cursor()
        await self.create_tables()
        
        # Проверяем существующие токены
        #await self.check_db()

    #async def check_db(self):
        #"""Проверяет содержимое базы данных и выводит информацию о токенах"""
        #try:
            #async with self.db_lock:
                #await self.cursor.execute("SELECT COUNT(*) FROM AuthTokens")
                #count = await self.cursor.fetchone()
                #if count and count[0] > 0:
                    #self.logger.info(f"В базе данных найдено {count[0]} токенов")
                    
                    # Выводим первые 5 токенов для проверки
                    #await self.cursor.execute("SELECT email, updated_at FROM AuthTokens LIMIT 5")
                    #tokens = await self.cursor.fetchall()
                    #for token in tokens:
                        #self.logger.info(f"Token for {token[0]}, updated {token[1]}")
                #else:
                    #Sself.logger.info("Token database is empty")
        #except Exception as e:
            #self.logger.warning(f"Error checking token database: {e}")

    async def create_tables(self):
        await self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS AuthTokens (
        email TEXT PRIMARY KEY,
        token TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        await self.connection.commit()
    
    async def save_token(self, email, token):
        """Сохраняет токен авторизации для указанного email"""
        async with self.db_lock:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Проверяем, изменился ли токен
            await self.cursor.execute("SELECT token FROM AuthTokens WHERE email=?", (email,))
            result = await self.cursor.fetchone()
            
            if result and result[0] == token:
                self.logger.info(f"Token for {email} has not changed, skipping update")
                return
                
            await self.cursor.execute(
                "INSERT OR REPLACE INTO AuthTokens(email, token, updated_at) VALUES(?, ?, ?)", 
                (email, token, current_time)
            )
            await self.connection.commit()
    
    async def get_token(self, email):
        """Получает сохраненный токен авторизации для указанного email"""
        async with self.db_lock:
            await self.cursor.execute("SELECT token FROM AuthTokens WHERE email=?", (email,))
            result = await self.cursor.fetchone()
            return result[0] if result else None
    
    async def get_all_tokens(self):
        """Получает все сохраненные токены с их email"""
        async with self.db_lock:
            await self.cursor.execute("SELECT email, token, updated_at FROM AuthTokens")
            results = await self.cursor.fetchall()
            return [{"email": row[0], "token": row[1], "updated_at": row[2]} for row in results]
    
    async def delete_token(self, email):
        """Удаляет токен для указанного email"""
        async with self.db_lock:
            await self.cursor.execute("DELETE FROM AuthTokens WHERE email=?", (email,))
            await self.connection.commit()
    
    async def close_connection(self):
        if self.connection:
            await self.connection.close() 