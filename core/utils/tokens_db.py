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
        
        # Create database directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        from core.utils import logger
        self.logger = logger

    async def connect(self):
        #self.logger.info(f"Connecting to tokens database: {self.db_path}")
        exists = os.path.exists(self.db_path)
        
        #if exists:
            #self.logger.info(f"Tokens database already exists")
        #else:
            #self.logger.info(f"Tokens database will be created")
            
        self.connection = await aiosqlite.connect(self.db_path)
        self.cursor = await self.connection.cursor()
        await self.create_tables()
        
        # Check existing tokens
        #await self.check_db()

    #async def check_db(self):
        #"""Checks database content and outputs token info"""
        #try:
            #async with self.db_lock:
                #await self.cursor.execute("SELECT COUNT(*) FROM AuthTokens")
                #count = await self.cursor.fetchone()
                #if count and count[0] > 0:
                    #self.logger.info(f"Found {count[0]} tokens in database")
                    
                    # Output first 5 tokens for verification
                    #await self.cursor.execute("SELECT email, updated_at FROM AuthTokens LIMIT 5")
                    #tokens = await self.cursor.fetchall()
                    #for token in tokens:
                        #self.logger.info(f"Token for {token[0]}, updated {token[1]}")
                #else:
                    #self.logger.info("Token database is empty")
        #except Exception as e:
            #self.logger.warning(f"Error checking token database: {e}")

    async def create_tables(self):
        await self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS AuthTokens (
        email TEXT PRIMARY KEY,
        token TEXT NOT NULL,
        refresh_token TEXT,
        wallet TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        await self.connection.commit()
        
        # Migration: add new columns if they don't exist
        await self._migrate_add_columns()
    
    async def _migrate_add_columns(self):
        """Adds new columns to existing table"""
        try:
            await self.cursor.execute("ALTER TABLE AuthTokens ADD COLUMN refresh_token TEXT")
        except Exception:
            pass  # Column already exists
        
        try:
            await self.cursor.execute("ALTER TABLE AuthTokens ADD COLUMN wallet TEXT")
        except Exception:
            pass  # Column already exists
        
        await self.connection.commit()

    async def save_token(self, email, token):
        """Saves authorization token for specified email"""
        async with self.db_lock:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if token has changed
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
        """Gets saved authorization token for specified email"""
        async with self.db_lock:
            await self.cursor.execute("SELECT token FROM AuthTokens WHERE email=?", (email,))
            result = await self.cursor.fetchone()
            return result[0] if result else None
    
    async def get_all_tokens(self):
        """Gets all saved tokens with their emails"""
        async with self.db_lock:
            await self.cursor.execute("SELECT email, token, updated_at FROM AuthTokens")
            results = await self.cursor.fetchall()
            return [{"email": row[0], "token": row[1], "updated_at": row[2]} for row in results]
    
    async def delete_token(self, email):
        """Deletes token for specified email"""
        async with self.db_lock:
            await self.cursor.execute("DELETE FROM AuthTokens WHERE email=?", (email,))
            await self.connection.commit()
    
    async def save_refresh_token(self, email, refresh_token):
        """Saves refresh token for email"""
        async with self.db_lock:
            await self.cursor.execute(
                "UPDATE AuthTokens SET refresh_token=? WHERE email=?",
                (refresh_token, email)
            )
            await self.connection.commit()
    
    async def get_refresh_token(self, email):
        """Gets refresh token for email"""
        async with self.db_lock:
            await self.cursor.execute(
                "SELECT refresh_token FROM AuthTokens WHERE email=?", (email,)
            )
            result = await self.cursor.fetchone()
            return result[0] if result else None
    
    async def save_wallet(self, email, wallet):
        """Links wallet to account"""
        async with self.db_lock:
            await self.cursor.execute(
                "UPDATE AuthTokens SET wallet=? WHERE email=?",
                (wallet, email)
            )
            await self.connection.commit()
    
    async def get_wallet_by_email(self, email):
        """Gets wallet by email"""
        async with self.db_lock:
            await self.cursor.execute(
                "SELECT wallet FROM AuthTokens WHERE email=?", (email,)
            )
            result = await self.cursor.fetchone()
            return result[0] if result else None
    
    async def is_wallet_linked(self, wallet):
        """Checks if wallet is linked to any account"""
        async with self.db_lock:
            await self.cursor.execute(
                "SELECT email FROM AuthTokens WHERE wallet=?", (wallet,)
            )
            result = await self.cursor.fetchone()
            return result[0] if result else None
    
    async def get_accounts_without_wallet(self):
        """Gets list of accounts without linked wallet"""
        async with self.db_lock:
            await self.cursor.execute(
                "SELECT email, token FROM AuthTokens WHERE wallet IS NULL OR wallet=''"
            )
            results = await self.cursor.fetchall()
            return [{"email": row[0], "token": row[1]} for row in results]
    
    async def close_connection(self):
        if self.connection:
            await self.connection.close() 