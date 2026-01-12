## 🔹Grass Auto Farm mod 6.1.3🔹

<div align="center">
  <p align="center">
    <a href="https://t.me/D3_vin">
      <img src="https://img.shields.io/badge/Telegram-Channel-blue?style=for-the-badge&logo=telegram" alt="Telegram Channel">
    </a>
    <a href="https://t.me/D3vin_chat">
      <img src="https://img.shields.io/badge/Telegram-Chat-blue?style=for-the-badge&logo=telegram" alt="Telegram Chat">
    </a>
  </p>
</div>

## 📢 Connect with Us

- **📢 Channel**: [https://t.me/D3_vin](https://t.me/D3_vin) - Latest updates and releases
- **💬 Chat**: [https://t.me/D3vin_chat](https://t.me/D3vin_chat) - Community support and discussions
- **📁 GitHub**: [https://github.com/D3-vin](https://github.com/D3-vin) - Source code and development




### What is bot for?
   - Farm Points in 1x or 1.25x modes
   - Claim Rewards
   - Check Points
   - **🆕 Link Solana Wallets** - mass wallet linking with email verification

> You can put as many proxies as u can, bot uses database and will load up proxies from extra ones


To hang several connections on 1 account, you just need to duplicate it in the accounts.txt.

## Quick Start 📚
   1. To install libraries on Windows click on `INSTALL.bat` (or in console: `pip install -r requirements.txt`).
   2. To start bot use `START.bat` (or in console: `python main.py`).
   3. Choose one of the available modes:
      - Farm 1.25x - farming points with 1.25x multiplier
      - Farm 1x - farming points with 1x multiplier
      - Claim rewards - only claim available rewards
      - Login only - update tokens without farming
      - **Link wallets** - link Solana wallets to accounts
      - Exit - close the application

### Options 📧
  FARM POINTS:
 - Choose mode 1 or 2 to farm points with different multipliers
 - Provide emails and passwords and proxies to register accounts as shown below!

  CLAIM REWARDS:
 - Choose mode 3 to claim all available rewards for your accounts

### Configuration 📧

1. Accounts Setup 🔒

   Put in `data/accounts.txt` accounts in format email:password

2. Proxy Setup 🔒

   Configure your proxies with the *ANY* (socks, http/s, ...) format in `data/proxies.txt` 🌐

## 🔗 Wallet Linking (NEW)

Link Solana wallets to your Grass accounts with automatic email verification.

### Setup

1. **Wallets** - Put your Solana private keys in `data/wallets.txt` (one per line)

2. **Accounts for linking** - Put accounts in `data/acc_to_link_wallet.txt` in format:
   ```
   email:password:imap_password
   ```
   > Note: `imap_password` can contain `:` characters

3. **IMAP Configuration** - Configure email servers in `data/email_config.yaml`:
   ```yaml
   imap_settings:
     use_proxy_for_imap: false  # Set true to use proxy for IMAP
   
   servers:
     gmail.com: imap.gmail.com
     outlook.com: imap-mail.outlook.com
     # Add your email domains here
   ```

### How it works

1. Bot logs into account using saved token or performs full login
2. Checks if wallet is already linked
3. Signs message with Solana private key
4. Sends wallet linking request to Grass API
5. Sends verification email request
6. Reads confirmation link from email via IMAP
7. Confirms wallet address

### Supported Email Providers

- Gmail, Yahoo, iCloud
- Mail.ru, GMX
- Onet.pl, Gazeta.pl
- Custom IMAP servers (add to config)

### Requirements

- Accounts must be logged in first (run "Login only" mode)
- Valid IMAP credentials for email verification
- One wallet per account (duplicates are checked)

