"""Resmi Gazete'den günün sayısını ve ilan sayfalarını çeker.

NOT: URL kalıpları resmigazete.gov.tr'nin bilinen arşiv yapısına göredir
(/eskiler/YYYY/MM/YYYYMMDD.htm). Canlıda ilk çalıştırmada doğrula.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import date, datetime

import requests

from . import config

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT


def index_url(d: date, kind: str = "normal") -> str:
    ymd = d.strftime("%Y%m%d")
    suffix = {"normal": "", "mukerrer": "M1"}.get(kind, "")
    return f"{config.BASE_URL}/eskiler/{d:%Y}/{d:%m}/{ymd}{suffix}.htm"


def get(url: str) -> requests.Response | None:
    """404 -> None (henüz yayımlanmadı). Diğer hatalar fırlatılır."""
    r = _session.get(url, timeout=config.HTTP_TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    return r


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wait_for_issue(d: date, kind: str = "normal") -> str | None:
    """Sayı yayımlanana kadar yokla. İçerik HTML'ini döndürür, süre dolarsa None."""
    url = index_url(d, kind)
    deadline = time.time() + config.POLL_MAX_MINUTES * 60
    while True:
        try:
            r = get(url)
        except requests.RequestException as e:
            log.warning("İstek hatası: %s", e)
            r = None
        if r is not None and len(r.text) > 500:
            log.info("Sayı bulundu: %s", url)
            return r.text
        if time.time() > deadline:
            log.error("Süre doldu, sayı bulunamadı: %s", url)
            return None
        log.info("Henüz yok (%s). %s sn sonra tekrar.", datetime.now().strftime("%H:%M:%S"), config.POLL_INTERVAL_SEC)
        time.sleep(config.POLL_INTERVAL_SEC)


def fetch_item_text(url: str) -> str:
    """Bir ilan sayfasının düz metnini getirir (HTML ise). PDF'ler şimdilik atlanır."""
    from bs4 import BeautifulSoup

    if url.lower().endswith(".pdf"):
        return ""
    r = get(url)
    if r is None:
        return ""
    soup = BeautifulSoup(r.text, "lxml")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    text = soup.get_text("\n", strip=True)
    return text
