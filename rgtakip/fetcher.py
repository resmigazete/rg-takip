"""Resmi Gazete'den günün sayısını ve ilan sayfalarını çeker.

NOT: URL kalıpları resmigazete.gov.tr'nin bilinen arşiv yapısına göredir
(/eskiler/YYYY/MM/YYYYMMDD.htm). Canlıda ilk çalıştırmada doğrula.
"""
from __future__ import annotations

import hashlib
import io
import os
import logging
import re
import time
from datetime import date, datetime

import requests

from . import config

log = logging.getLogger(__name__)

_NO_ISSUE = re.compile(r"bugün\s+Resm[iî]\s+Gazete\s+yayımlanmamaktadır", re.I)   # "...uyarınca bugün Resmî Gazete yayımlanmamaktadır."


def is_no_issue(text: str) -> bool:
    return bool(text) and len(text) < 20000 and bool(_NO_ISSUE.search(text))

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
        if r is not None and is_no_issue(r.text):   # resmî tatil: sayı hiç yayımlanmayacak, beklemeye gerek yok
            log.info("Resmî Gazete bu tarihte yayımlanmıyor: %s", url)
            return r.text
        if r is not None and len(r.text) > 500:
            log.info("Sayı bulundu: %s", url)
            return r.text
        if time.time() > deadline:
            log.error("Süre doldu, sayı bulunamadı: %s", url)
            return None
        log.info("Henüz yok (%s). %s sn sonra tekrar.", datetime.now().strftime("%H:%M:%S"), config.POLL_INTERVAL_SEC)
        time.sleep(config.POLL_INTERVAL_SEC)


_PDF_STOP = ("ve", "bir", "olarak", "kararı", "karar", "maddesi", "gereğince", "hakkında", "atanmıştır")


_MIN_LETTERS_PER_PAGE = 400   # dolu bir Resmî Gazete sayfası binlerce harf taşır; başlık-yalnızca sayfa yüzlerce değil onlarca


def _letters(text: str) -> int:
    return len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]", text))


def _pdf_garbled(text: str) -> bool:
    """Metin katmanı yok/bozuk mu? (Atama PDF'lerinde yazı resim olarak gömülü; pypdf boş/anlamsız döner.)"""
    letters = len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]", text))
    if letters < 200:
        return True
    words = re.findall(r"[a-zçğıöşü]+", text.lower())
    return sum(w in _PDF_STOP for w in words) < 3


def _read_pgm(path) -> tuple[int, int, bytearray]:
    """Ham (P5) gri tonlamalı PGM dosyasını okur: (genişlik, yükseklik, bayt dizisi)."""
    raw = open(path, "rb").read()
    parts, pos = [], 0
    while len(parts) < 4:                      # P5 genişlik yükseklik maxval
        while raw[pos:pos + 1].isspace():
            pos += 1
        if raw[pos:pos + 1] == b"#":
            pos = raw.index(b"\n", pos)
            continue
        end = pos
        while not raw[end:end + 1].isspace():
            end += 1
        parts.append(raw[pos:end])
        pos = end
    w, h = int(parts[1]), int(parts[2])
    return w, h, bytearray(raw[pos + 1: pos + 1 + w * h])


def _write_pgm(path, w: int, h: int, data) -> None:
    with open(path, "wb") as fh:
        fh.write(b"P5\n%d %d\n255\n" % (w, h))
        fh.write(bytes(data))


_DARK = bytes(1 if i < 150 else 0 for i in range(256))   # bayt -> koyu mu (1) açık mı (0)


def _runs(idx: list[int]) -> list[int]:
    """Ardışık indeksleri tek çizgide topla, çizgi merkezlerini döndür."""
    out, start, prev = [], None, None
    for i in idx:
        if start is None:
            start = prev = i
        elif i == prev + 1:
            prev = i
        else:
            out.append((start + prev) // 2)
            start = prev = i
    if start is not None:
        out.append((start + prev) // 2)
    return out


def find_grid(w: int, h: int, gray) -> tuple[list[int], list[int]] | None:
    """Sayfadaki tablo ızgarasını (yatay çizgi y'leri, dikey çizgi x'leri) bulur; tablo yoksa None."""
    dark = bytes(gray).translate(_DARK)
    rows = [int.from_bytes(dark[y * w:(y + 1) * w], "big") for y in range(h)]
    ys = [y for y in range(1, h - 1)
          if bin(rows[y - 1] | rows[y] | rows[y + 1]).count("1") >= 0.38 * w]   # soluk/kopuk çizgiler için ±1 satır
    hlines = _runs(ys)
    if len(hlines) < 3:
        return None
    top, bot = hlines[0], hlines[-1]
    row = bytes(a | b | c for a, b, c in zip(dark[(top - 1) * w:top * w], dark[top * w:(top + 1) * w],
                                              dark[(top + 1) * w:(top + 2) * w]))
    x0, x1 = row.find(1), row.rfind(1)
    span = max(bot - top, 1)
    # Taranmış belgelerde dikey çizgi ince ve dalgalıdır: her sütunu ±2 piksel komşusuyla birleştirip yoğunluğa bak
    lo, hi = max(x0 - 6, 0), min(x1 + 7, w)
    col = {x: int.from_bytes(dark[top * w + x: bot * w + x + 1: w], "big") for x in range(lo, hi)}
    xs = []
    for x in range(lo + 2, hi - 2):
        merged = col[x - 2] | col[x - 1] | col[x] | col[x + 1] | col[x + 2]
        if bin(merged).count("1") >= 0.55 * span:
            xs.append(x)
    vlines = _runs(xs)
    if len(vlines) < 3:
        return None
    if vlines[-1] < x1 - 60:          # soluk/kopuk kenar çizgisini yatay çizgilerin uç noktasından tamamla
        vlines.append(x1)
    if vlines[0] > x0 + 60:
        vlines.insert(0, x0)
    return hlines, vlines


def _ocr_cell(job) -> str:
    """Tek bir hücrenin kırpılmış görüntüsünü Tesseract ile okur."""
    import subprocess

    path, digits = job
    cmd = ["tesseract", path, "-", "-l", "tur", "--psm", "7" if digits else "6", "-c", "preserve_interword_spaces=1"]
    if digits:
        cmd += ["-c", "tessedit_char_whitelist=0123456789"]
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    return " ".join(r.stdout.split())


def _table_rows(tmpdir, grid, w, h, gray) -> list[list[str]]:
    """Izgara hücrelerini tek tek kırpıp OCR'lar (sütunlar birbirine karışmaz). Boş hücreler okunmaz."""
    import pathlib
    from concurrent.futures import ThreadPoolExecutor

    hlines, vlines = grid
    pad = 6
    jobs, index = [], []
    for ri in range(len(hlines) - 1):
        y0, y1 = hlines[ri] + pad, hlines[ri + 1] - pad
        if y1 - y0 < 15:
            continue
        for ci in range(len(vlines) - 1):
            x0, x1 = vlines[ci] + pad, vlines[ci + 1] - pad
            if x1 - x0 < 15:
                continue
            cell = bytearray()
            for y in range(y0, y1):
                cell += gray[y * w + x0: y * w + x1]
            if bytes(cell).translate(_DARK).count(1) < 40:      # boş hücre
                continue
            p = pathlib.Path(tmpdir) / f"c{ri}_{ci}.pgm"
            _write_pgm(p, x1 - x0, y1 - y0, cell)
            jobs.append((str(p), ci == 0))
            index.append((ri, ci))
    with ThreadPoolExecutor(max_workers=4) as ex:
        texts = list(ex.map(_ocr_cell, jobs))
    ncol = len(vlines) - 1
    rows = [[""] * ncol for _ in range(len(hlines) - 1)]
    for (ri, ci), t in zip(index, texts):
        rows[ri][ci] = t
    return rows


def ocr_pdf(data: bytes, max_pages: int = 12) -> str:
    """PDF'i sayfa sayfa resme çevirip Tesseract (Türkçe) ile okur.
    Izgaralı tablolar (örn. Cumhurbaşkanlığı atama listesi: Adı Soyadı | Mevcut Görevi | Atandığı Görev) sütun/satır
    konumlarına göre okunur ve 'TABLO|sıra|ad|mevcut|atandığı|' satırları olarak döner; düz sayfalar eskisi gibi okunur.
    Sistem paketleri: poppler-utils, tesseract-ocr, tesseract-ocr-tur."""
    import pathlib
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        pdf = pathlib.Path(d) / "a.pdf"
        pdf.write_bytes(data)
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-l", str(max_pages), str(pdf), str(pathlib.Path(d) / "p")],
                       check=True, timeout=300)
        pages = []
        for img in sorted(pathlib.Path(d).glob("p-*.pgm")):
            w, h, gray = _read_pgm(img)
            grid = None
            try:
                grid = find_grid(w, h, gray)
            except Exception as e:   # ızgara bulunamazsa düz OCR'a düş
                log.warning("Tablo algılanamadı: %s", type(e).__name__)
            if grid:
                rows = _table_rows(d, grid, w, h, gray)
                pages.append("\n".join("TABLO|" + "|".join(c.replace("|", "/") for c in r) + "|" for r in rows if any(r)))
                continue
            r = subprocess.run(["tesseract", str(img), "-", "-l", "tur", "--psm", "6"],
                               capture_output=True, text=True, timeout=180)
            pages.append(r.stdout)
    return "\n".join(pages)


def pdf_to_text(data: bytes) -> str:
    """PDF baytlarından düz metin: önce metin katmanı, bozuksa OCR. Satır sonlarında bölünen cümleleri birleştirir
    ('.' veya ':' ile bitmeyen satır sonrakiyle birleşir)."""
    from pypdf import PdfReader

    pages = 0
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = len(reader.pages)
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        log.warning("PDF metin katmanı okunamadı: %s", type(e).__name__)
        text = ""
    # Atama kararlarında yalnızca başlıklar ("Karar: 2026/400 … CUMHURBAŞKANI") metin katmanındadır, asıl metin resimdir.
    # Başlıklardaki tekrarlı "Karar" kelimesi _pdf_garbled'ı yanıltır; bu yüzden sayfa başına harf sayısına da bakılır.
    thin = pages > 0 and _letters(text) / pages < _MIN_LETTERS_PER_PAGE
    if _pdf_garbled(text) or thin:
        log.info("PDF metin katmanı yok/yetersiz (%d sayfa, %d harf), OCR deneniyor", pages, _letters(text))
        ocr = ocr_pdf(data)
        if _pdf_garbled(text) or _letters(ocr) > 1.3 * _letters(text):
            text = ocr
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"(?<![.:|])\n(?!\n)", " ", text).strip()


def pdf_item_text(url: str) -> str:
    """Bir ilan/karar PDF'inin metnini getirir; hata olursa boş döner (akışı durdurmaz)."""
    r = _session.get(url, timeout=config.HTTP_TIMEOUT)
    if r.status_code == 404:
        return ""
    r.raise_for_status()
    try:
        return pdf_to_text(r.content)
    except Exception as e:
        log.warning("PDF okunamadı %s: %s", url, type(e).__name__)
        return ""


def fetch_item_text(url: str) -> str:
    """Bir ilan sayfasının düz metnini getirir (HTML ya da PDF)."""
    from bs4 import BeautifulSoup

    if url.lower().endswith(".pdf"):
        return pdf_item_text(url)
    r = get(url)
    if r is None:
        return ""
    soup = BeautifulSoup(r.text, "lxml")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    text = soup.get_text("\n", strip=True)
    return text
