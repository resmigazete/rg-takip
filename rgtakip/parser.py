"""Günün fihristini (içindekiler) ilan kayıtlarına böler.

Yaklaşım: sayfadaki, ilan sayfasına işaret eden tüm bağlantıları topla;
her bağlantının üstündeki en yakın bölüm başlığını `section` olarak ata.
Sayfa yapısı değişirse yalnızca bu dosya güncellenir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import config

# /eskiler/2026/11/20261116-12.htm, ...M1-3.htm, .pdf
ITEM_HREF = re.compile(r"\d{8}(?:M\d+)?-\d+\.(?:htm|html|pdf)$", re.I)

# Kısa biçim: https://site/20261113-1.htm (ya da göreli 20261113-1.htm). Sitede bu adres günün ana sayfasına gider;
# gerçek yer arşiv klasörüdür: /eskiler/YYYY/AA/20261113-1.htm
SHORT_URL = re.compile(r"^(https?://[^/]+)/((\d{4})(\d{2})\d{2}(?:M\d+)?-\d+\.(?:htm|html|pdf))$", re.I)


def canonical_url(url: str) -> str:
    m = SHORT_URL.match(url)
    if not m:
        return url
    host, name, yyyy, mm = m.group(1), m.group(2), m.group(3), m.group(4)
    return f"{host}/eskiler/{yyyy}/{mm}/{name}"


HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

SECTION_TO_TYPE = [
    (r"kanun", "kanun"),
    (r"kanun hükmünde", "khk"),
    (r"cumhurba[şs]kan[ıi]\s+kararlar", "cb_karari"),
    (r"cumhurba[şs]kanl[ıi][ğg][ıi]\s+kararnam", "cb_kararname"),
    (r"yönetmelik", "yonetmelik"),
    (r"tebli[ğg]", "teblig"),
    (r"atama", "atama"),
    (r"kurul\s+kararlar", "kurul_karari"),
    (r"yarg[ıi]\s+b[öo]l", "yargi"),
    (r"ilan", "ilan"),
    (r"genelge", "genelge"),
    (r"yönerge", "yonerge"),
]


@dataclass
class Item:
    url: str
    title: str
    section: str
    doc_type: str


def clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"^[\s–—\-]+", "", t).strip()


def is_notice(url: str, title: str) -> bool:
    """İlan bölümü bağlantıları ve günlük döviz/borçlanma kayıtları."""
    u = url.lower()
    if "main.aspx" in u or "eskiilanlar" in u or "/ilanlar/" in u:
        return True
    return bool(re.search(r"döviz kurları|iç borçlanma senetlerinin", title.lower()))


def guess_type(section: str, title: str) -> str:
    probe = f"{section} {title}".lower()
    if re.search(r"(anayasa mahkemesi|danıştay|yargıtay|uyuşmazlık mahkemesi).{0,120}(karar|ilam)", probe):
        return "yargi"
    # KHK, "kanun" kalıbından önce kontrol edilmeli
    if re.search(r"kanun hükmünde", probe):
        return "khk"
    for pat, t in SECTION_TO_TYPE:
        if re.search(pat, probe, re.I):
            return t
    return "diger"


def parse_index(html: str, base: str | None = None) -> list[Item]:
    base = base or config.BASE_URL
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()
    current_section = ""

    for el in soup.find_all(True):
        if el.name in HEADING_TAGS:
            txt = el.get_text(" ", strip=True)
            if txt:
                current_section = txt
            continue
        # "class" içinde başlık/bölüm geçen blok öğeleri de bölüm sayılır
        cls = " ".join(el.get("class", [])).lower() if el.get("class") else ""
        if el.name in {"div", "p", "span"} and re.search(r"baslik|başlık|bolum|bölüm|fihrist-title|section", cls) \
                and not el.find("a", href=ITEM_HREF):
            txt = el.get_text(" ", strip=True)
            if 2 < len(txt) < 120:
                current_section = txt
            continue
        if el.name == "a":
            href = el.get("href", "")
            if not ITEM_HREF.search(href):
                continue
            url = canonical_url(urljoin(base + "/", href))
            if url in seen:
                continue
            seen.add(url)
            title = clean_title(el.get_text(" ", strip=True))
            if not title:
                continue
            dtype = "ilan" if is_notice(url, title) else guess_type(current_section, title)
            items.append(Item(url, title, current_section, dtype))
    return items
