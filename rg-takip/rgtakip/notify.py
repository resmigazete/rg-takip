"""Telegram gönderimi (4096 karakter sınırına göre böler)."""
import requests

from . import config


def chunks(text: str, limit: int = 3800):
    cur = ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            yield cur
            cur = ""
        cur += line + "\n"
    if cur.strip():
        yield cur


def send_telegram(text: str) -> bool:
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    for part in chunks(text):
        r = requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID, "text": part,
            "disable_web_page_preview": True}, timeout=30)
        r.raise_for_status()
    return True
