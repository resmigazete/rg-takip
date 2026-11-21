"""Resmi Gazete'den günün sayısını ve ilan sayfalarını çeker.

NOT: URL kalıpları resmigazete.gov.tr'nin bilinen arşiv yapısına göredir
(/eskiler/YYYY/MM/YYYYMMDD.htm). Canlıda ilk çalıştırmada doğrula.
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
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


_STOP = ("ve", "bir", "olarak", "kararı", "karar", "maddesi", "gereğince", "hakkında", "atanmıştır")


def _garbled(text: str) -> bool:
    """Metin katmanı yok / bozuk mu? (Resmi Gazete'nin atama PDF'leri gömülü yazı tipi eşlemesiz ve
    metni resim olarak taşıyor: pypdf boş ya da anlamsız karakter döndürür.)"""
    letters = len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]", text))
    if letters < 200:
        return True
    words = re.findall(r"[a-zçğıöşü]+", text.lower())
    return sum(w in _STOP for w in words) < 3


def ocr_pdf(data: bytes, max_pages: int = 12) -> str:
    """PDF'i sayfa sayfa resme çevirip Tesseract (Türkçe) ile okur.
    Gerekli sistem paketleri: poppler-utils, tesseract-ocr, tesseract-ocr-tur."""
    import pathlib
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        pdf = pathlib.Path(d) / "a.pdf"
        pdf.write_bytes(data)
        subprocess.run(["pdftoppm", "-r", "200", "-l", str(max_pages), "-png", str(pdf), str(pathlib.Path(d) / "p")],
                       check=True, timeout=180)
        pages = []
        for img in sorted(pathlib.Path(d).glob("p-*.png")):
            r = subprocess.run(["tesseract", str(img), "-", "-l", "tur", "--psm", "6"],
                               capture_output=True, text=True, timeout=180)
            pages.append(r.stdout)
    return "\n".join(pages)


def pdf_to_text(data: bytes) -> str:
    """PDF baytlarından düz metin: önce metin katmanı, bozuksa OCR.
    Satır sonlarında bölünen cümleleri birleştirir ('.' veya ':' ile bitmeyen satır sonrakiyle birleşir)."""
    from pypdf import PdfReader

    try:
        text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    except Exception as e:
        log.warning("PDF metin katmanı okunamadı: %s", type(e).__name__)
        text = ""
    if _garbled(text):
        log.info("PDF metin katmanı kullanılamıyor, OCR deneniyor")
        text = ocr_pdf(data)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"(?<![.:])\n(?!\n)", " ", text).strip()


def fetch_item_text(url: str) -> str:
    """Bir ilan sayfasının düz metnini getirir (HTML ya da PDF)."""
    from bs4 import BeautifulSoup

    if url.lower().endswith(".pdf"):
        r = _session.get(url, timeout=config.HTTP_TIMEOUT)
        if r.status_code == 404:
            return ""
        r.raise_for_status()
        try:
            return pdf_to_text(r.content)
        except Exception as e:  # bozuk/taranmış PDF akışı durdurmasın
            log.warning("PDF okunamadı %s: %s", url, type(e).__name__)
            return ""
    r = get(url)
    if r is None:
        return ""
    soup = BeautifulSoup(r.text, "lxml")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    text = soup.get_text("\n", strip=True)
    return text
