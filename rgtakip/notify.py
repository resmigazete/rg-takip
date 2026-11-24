"""Telegram gönderimi (4096 karakter sınırına göre böler; birden çok alıcıya gönderebilir)."""
import logging
import re

import requests

from . import config

log = logging.getLogger(__name__)


def chunks(text: str, limit: int = 3800):
    cur = ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            yield cur
            cur = ""
        cur += line + "\n"
    if cur.strip():
        yield cur


def chat_ids() -> list[str]:
    """TELEGRAM_CHAT_ID tek sayı ya da virgül/boşlukla ayrılmış birden çok sayı olabilir (grup kimlikleri '-100…' ile başlar)."""
    out: list[str] = []
    for c in re.split(r"[,;\s]+", config.TELEGRAM_CHAT_ID or ""):
        if c.strip() and c.strip() not in out:
            out.append(c.strip())
    return out


def send_telegram(text: str) -> bool:
    """Her alıcıya ayrı gönderir; biri başarısız olursa diğerleri yine de alır.
    Hiçbirine gönderilemezse hata verir (Actions kırmızı olur). Ayarlı değilse False."""
    ids = chat_ids()
    if not (config.TELEGRAM_TOKEN and ids):
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    sent, failed = 0, []
    for cid in ids:
        try:
            for part in chunks(text):
                r = requests.post(url, json={"chat_id": cid, "text": part, "disable_web_page_preview": True}, timeout=30)
                r.raise_for_status()
            sent += 1
        except Exception as e:   # hata metni token'lı adresi içerebilir; yalnızca türünü ve kodunu yaz
            code = getattr(getattr(e, "response", None), "status_code", "")
            log.warning("Telegram gönderilemedi (alıcı %s): %s %s", cid, type(e).__name__, code)
            failed.append(cid)
    if not sent:
        raise RuntimeError(f"Telegram: hiçbir alıcıya gönderilemedi ({len(failed)} alıcı)")
    return True
