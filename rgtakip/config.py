"""Yapılandırma. Ortam değişkenleriyle ezilebilir."""
import os

BASE_URL = "https://www.resmigazete.gov.tr"
DB_PATH = os.environ.get("RG_DB", "rgtakip.sqlite3")

# Yoklama: 00:05'ten itibaren, yayımlanana kadar
POLL_INTERVAL_SEC = int(os.environ.get("RG_POLL_INTERVAL", "300"))
POLL_MAX_MINUTES = int(os.environ.get("RG_POLL_MAX_MIN", "180"))
HTTP_TIMEOUT = 30
USER_AGENT = "rg-takip/0.1 (kisisel arastirma)"

# Telegram (isteğe bağlı)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Bildirim eşiği (0-100)
MIN_IMPORTANCE = int(os.environ.get("RG_MIN_IMPORTANCE", "40"))
