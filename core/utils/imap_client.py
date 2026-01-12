import ssl
import re
import asyncio
import yaml
from typing import Optional
from datetime import datetime, timezone
from imaplib import IMAP4_SSL
from imap_tools import MailBox, AND, MailboxLoginError
from python_socks.sync import Proxy as SyncProxy

from core.utils import logger


# Patterns for wallet confirmation link search
WALLET_PATTERNS = [
    r'(https://[^\s"<>]+confirm-wallet-address[^\s"<>]+token=[^\s"<>]+)',
    r'(https://[^/]+/L0/https:%2F%2Fapp\.getgrass\.io%2Fconfirm-wallet-address%2F%3Ftoken=[^/]+/\d+/[^/]+-[^/]+-[^/]+-[^/]+-[^/]+-[^/]+/[^=]+=\d+)',
]

# Cache of used links
_used_links: set = set()


def load_email_config(path: str = "data/email_config.yaml") -> dict:
    """Load email config from yaml"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load email config: {e}")
        return {}


def get_imap_server(email: str, config: dict = None) -> str:
    """Determines IMAP server by email domain"""
    if config is None:
        config = load_email_config()
    
    if config.get('use_single_imap', {}).get('enable'):
        return config['use_single_imap']['imap_server']
    
    domain = email.split('@')[-1].lower()
    servers = config.get('servers', {})
    return servers.get(domain)  # Returns None if domain not found


def is_domain_supported(email: str, config: dict = None) -> bool:
    """Checks if email domain is supported"""
    if config is None:
        config = load_email_config()
    
    if config.get('use_single_imap', {}).get('enable'):
        return True
    
    domain = email.split('@')[-1].lower()
    return domain in config.get('servers', {})


# === IMAP with proxy ===

class IMAP4ProxySSL(IMAP4_SSL):
    """IMAP4 SSL with proxy support"""
    
    def __init__(self, host: str, proxy_url: str = None, port: int = 993, timeout: float = 30):
        self._proxy_url = proxy_url
        self._real_host = host
        self._real_port = port
        self._timeout = timeout
        super().__init__(host, port, timeout=timeout)
    
    def _create_socket(self, timeout=None):
        if self._proxy_url:
            proxy = SyncProxy.from_url(self._proxy_url, rdns=True)
            sock = proxy.connect(self._real_host, self._real_port, timeout or self._timeout)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx.wrap_socket(sock, server_hostname=self._real_host)
        return super()._create_socket(timeout)


class ProxyMailBox(MailBox):
    """MailBox with proxy support"""
    
    def __init__(self, host: str, proxy_url: str = None, port: int = 993, timeout: float = 30):
        self._proxy_url = proxy_url
        super().__init__(host=host, port=port, timeout=timeout)
    
    def _get_mailbox_client(self):
        if self._proxy_url:
            return IMAP4ProxySSL(self._host, self._proxy_url, self._port, self._timeout)
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return IMAP4_SSL(self._host, port=self._port, timeout=self._timeout, ssl_context=ctx)


def _is_grass_sender(from_addr: str) -> bool:
    """Checks if sender is Grass"""
    from_lower = from_addr.lower()
    return 'grassfoundation.io' in from_lower or 'no-reply_at_grassfoundation_io' in from_lower


# === Main functions ===

async def check_imap_login(email: str, password: str, proxy_url: str = None) -> bool:
    """Check IMAP login validity"""
    imap_server = get_imap_server(email)
    
    if not imap_server:
        logger.error(f"{email} | IMAP server not found for domain")
        return False
    
    logger.debug(f"IMAP check: {email} -> {imap_server}, pass_len={len(password)}")
    
    def _login():
        try:
            with ProxyMailBox(imap_server, proxy_url, timeout=15).login(email, password):
                logger.debug(f"{email} | IMAP login successful")
                return True
        except MailboxLoginError as e:
            logger.error(f"{email} | IMAP MailboxLoginError: {e}")
            return False
        except Exception as e:
            logger.error(f"{email} | IMAP error: {type(e).__name__}: {e}")
            return False
    
    return await asyncio.to_thread(_login)


async def find_wallet_confirmation_link(
    email: str,
    password: str,
    proxy_url: str = None,
    max_attempts: int = 10,
    delay: int = 5,
    max_age_seconds: int = 300
) -> Optional[str]:
    """Search for wallet confirmation link in emails"""
    imap_server = get_imap_server(email)
    
    for attempt in range(max_attempts):
        result = await _search_wallet_link(email, password, imap_server, proxy_url, max_age_seconds)
        
        if result == "LOGIN_ERROR":
            return None
        
        if result:
            return result
        
        if attempt < max_attempts - 1:
            logger.info(f"{email} | Link not found, attempt {attempt + 1}/{max_attempts}")
            await asyncio.sleep(delay)
    
    logger.warning(f"{email} | Link not found after {max_attempts} attempts")
    return None


async def _search_wallet_link(
    email: str,
    password: str,
    imap_server: str,
    proxy_url: str,
    max_age: int
) -> Optional[str]:
    """Search for link in all mail folders"""
    
    def _search():
        try:
            with ProxyMailBox(imap_server, proxy_url, timeout=30).login(email, password) as mailbox:
                all_messages = []
                
                for folder in mailbox.folder.list():
                    try:
                        mailbox.folder.set(folder.name)
                        messages = _collect_grass_messages(mailbox)
                        all_messages.extend(messages)
                    except Exception:
                        continue
                
                return _find_link_in_messages(all_messages, max_age)
                
        except MailboxLoginError as e:
            logger.error(f"{email} | IMAP login invalid: {e}")
            return "LOGIN_ERROR"
        except Exception as e:
            logger.error(f"{email} | IMAP error: {e}")
            return None
    
    return await asyncio.to_thread(_search)


def _collect_grass_messages(mailbox) -> list:
    """Collects emails from Grass"""
    messages = []
    
    try:
        for msg in mailbox.fetch(AND(from_='grassfoundation.io'), reverse=True, limit=10, mark_seen=True):
            messages.append(msg)
    except Exception:
        pass
    
    if not messages:
        try:
            for msg in mailbox.fetch(reverse=True, limit=15, mark_seen=True):
                if _is_grass_sender(msg.from_):
                    messages.append(msg)
        except Exception:
            pass
    
    return messages


def _find_link_in_messages(messages: list, max_age: int) -> Optional[str]:
    """Searches for link in messages"""
    global _used_links
    now = datetime.now(timezone.utc)
    
    # Sort by date
    dated = []
    for msg in messages:
        msg_date = msg.date
        if msg_date.tzinfo is None:
            msg_date = msg_date.replace(tzinfo=timezone.utc)
        dated.append((msg, msg_date))
    
    dated.sort(key=lambda x: x[1], reverse=True)
    
    for msg, msg_date in dated:
        if (now - msg_date).total_seconds() > max_age:
            continue
        
        body = msg.html or msg.text or ""
        
        for pattern in WALLET_PATTERNS:
            match = re.search(pattern, body)
            if match:
                link = match.group(1)
                if link not in _used_links:
                    _used_links.add(link)
                    return link
    
    return None
