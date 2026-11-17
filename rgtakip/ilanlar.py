"""İlan bölümü: 'Çeşitli İlânlar' / 'Artırma, Eksiltme ve İhale İlânları' liste sayfalarını açar.

Fihristte ilanlar tek tek değil, yalnızca kategori bağlantısı olarak durur. Kategori sayfası ise
"Sağlık Bakanlığı Kamu Hastaneleri Genel Müdürlüğünden:" gibi, her biri tek bir ilana giden
kurum satırlarından oluşur. Burada bu satırlar ayrıştırılır, sağlıkla ilgili olanların metni çekilir.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import urllib.request
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, urljoin, urlparse

from . import classifier
from .textutil import tr_lower

log = logging.getLogger(__name__)

# Açılacak kategori sayfaları (başlığa göre). Yargı ilanları binlerce satır olduğu için atlanır.
EXPAND_RE = re.compile(r"çeşitli|artırma|eksiltme|ihale")
SKIP_RE = re.compile(r"yargı|döviz|borçlanma")


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str, str]] = []   # (href, metin, önceki konu satırı)
        self._href: str | None = None
        self._buf: list[str] = []
        self._prev = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._buf = []

    def handle_data(self, data):
        if self._href is not None:
            self._buf.append(data)
        else:
            t = " ".join(data.split())
            if t:
                self._prev = t

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._buf).split()), self._prev))
            self._href = None
            self._prev = ""


def _clean_subject(t: str) -> str:
    """Bağlantıdan önceki satır gerçek bir ilan konusu mu? ('TAŞINMAZ SATILACAKTIR' evet, sayfa başlığı hayır)"""
    if not t or len(t) < 8 or len(t) > 160:
        return ""
    low = tr_lower(t)
    if re.search(r"il[aâ]nlar[ıi]?$|resm[iî] gazete|sayı\s*:|^\d+ \w+ \d{4}", low):
        return ""
    return t


def parse_listing(html: str, base_url: str) -> list[tuple[str, str, str]]:
    """[(kurum satırı, mutlak adres, konu)] — yalnızca 'X'ndan:' biçimindeki bağlantılar.
    Konu yalnızca İhale sayfasında vardır (kurum satırının üstündeki büyük harfli başlık)."""
    p = _Links()
    p.feed(html)
    out, seen = [], set()
    for href, text, prev in p.links:
        text = text.strip()
        if not text.endswith(":") or len(text) < 6:
            continue
        if not href or href.startswith(("#", "javascript")):
            continue
        url = resolve_url(urljoin(base_url, href))
        if url in seen or url.rstrip("/") == base_url.rstrip("/"):
            continue
        seen.add(url)
        out.append((text.rstrip(": ").strip(), url, _clean_subject(prev)))
    return out


def resolve_url(url: str) -> str:
    """Fihristteki ilan bağlantıları 'main.aspx?home=...&main=<gerçek adres>' sarmalayıcısıdır;
    gerçek sayfa 'main' parametresindedir."""
    if "main.aspx" in url.lower():
        q = parse_qs(urlparse(url).query)
        real = (q.get("main") or [""])[0]
        if real:
            return real
    return url


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (rg-takip)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        cs = r.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(cs, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def is_listing(title: str, doc_type: str) -> bool:
    t = tr_lower(title)
    return doc_type == "ilan" and bool(EXPAND_RE.search(t)) and not SKIP_RE.search(t)


def _subject(body: str) -> str:
    """İlan metninden konuyu özetleyen ilk 'İLAN' satırı."""
    for line in body.splitlines()[:40]:
        line = " ".join(line.split())
        if 6 <= len(line) <= 150 and re.search(r"il[aâ]n", tr_lower(line)):
            return line
    return ""


def expand(conn: sqlite3.Connection, iso: str, parent_title: str, parent_url: str,
           html_fetcher: Callable[[str], str], text_fetcher: Callable[[str], str]) -> dict:
    """Kategori sayfasındaki her ilanı ayrı kayıt olarak ekler. Yalnızca sağlıkla ilgili olanın metni çekilir."""
    stats = {"new": 0, "health": 0}
    parent_url = resolve_url(parent_url)
    try:
        listing = parse_listing(html_fetcher(parent_url), parent_url)
    except Exception as e:
        log.warning("İlan listesi alınamadı %s: %s", parent_url, e)
        return stats
    if not listing:
        log.warning("İlan listesinde bağlantı bulunamadı: %s", parent_url)
    for issuer_line, url, subject in listing:
        if conn.execute("SELECT 1 FROM items WHERE url=?", (url,)).fetchone():
            continue
        issuer = classifier.normalize_issuer(issuer_line)
        title = f"{subject} — {issuer_line}" if subject else issuer_line
        first = classifier.classify(title, "", "ilan", issuer=issuer)
        body = ""
        if first.is_health:
            try:
                body = text_fetcher(url)
            except Exception as e:
                log.warning("İlan metni alınamadı %s: %s", url, e)
        res = classifier.classify(title, body, "ilan", issuer=issuer)
        subj = _subject(body) if (body and not subject) else ""
        full_title = f"{title} — {subj}" if subj else title
        conn.execute(
            """INSERT INTO items(issue_date,url,section,doc_type,title,issuer,body,is_health,
                                 health_score,importance,categories)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (iso, url, parent_title, "ilan", full_title, res.issuer, body, int(res.is_health),
             res.health_score, res.importance, ",".join(res.categories)))
        stats["new"] += 1
        stats["health"] += int(res.is_health)
    return stats
