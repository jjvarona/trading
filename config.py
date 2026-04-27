import os

# ── Telegram ─────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
RENDER_URL       = os.environ.get("RENDER_URL", "")

# ── Bitget Futures ────────────────────────────────────────────
BITGET_API_KEY        = os.environ.get("BITGET_API_KEY", "")
BITGET_API_SECRET     = os.environ.get("BITGET_API_SECRET", "")
BITGET_API_PASSPHRASE = os.environ.get("BITGET_API_PASSPHRASE", "")

LEVERAGE       = 20          # x20 isolated
MARGIN_MODE    = "isolated"
TP_LEVEL       = "tp2"       # usar TP2 del Pine como take profit
