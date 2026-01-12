import base64
import base58
from solders.keypair import Keypair

from core.utils import logger


class SolanaWallet:
    """Solana wallet manager for message signing"""
    
    def __init__(self, private_key: str):
        self.keypair = Keypair.from_bytes(base58.b58decode(private_key))

    @property
    def address(self) -> str:
        return str(self.keypair.pubkey())

    @property
    def public_key(self) -> str:
        return base64.b64encode(bytes(self.keypair.pubkey())).decode('utf-8')

    def sign_message(self, message: str) -> str:
        signature_bytes = self.keypair.sign_message(message.encode('utf-8'))
        return base64.b64encode(bytes(signature_bytes)).decode('utf-8')

    def get_signature_data(self, timestamp: int) -> tuple:
        """Returns data for wallet linking: (address, public_key, message, signature)"""
        message = (
            f'By signing this message you are binding this wallet to all activities '
            f'associated to your Grass account and agree to our Terms and Conditions '
            f'(https://www.grass.io/terms-and-conditions) and Privacy Policy '
            f'(https://www.grass.io/privacy-policy).\n\nNonce: {timestamp}'
        )
        signature = self.sign_message(message)
        return self.address, self.public_key, message, signature


def load_wallets(file_path: str) -> list:
    """Load private keys from file"""
    try:
        with open(file_path, 'r') as f:
            wallets = [line.strip() for line in f if line.strip()]
        return wallets
    except FileNotFoundError:
        logger.warning(f"Wallets file not found: {file_path}")
        return []
    except Exception as e:
        logger.error(f"Error loading wallets: {e}")
        return []
