"""Mevzuat değişikliklerini tespit eder: hangi mevzuat, hangi madde, ne yapıldı.

Bu ilk adımdır (kimin değiştiği + madde numaraları). Sonraki aşama:
mevzuat.gov.tr'den ana metnin eski halini çekip madde bazında diff üretmek.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .textutil import normalize

TITLE_AMEND = re.compile(
    r"^(?P<target>.+?)(?:['’]?(?:n[ıiuü]n|[ıiuü]n|n?[ıiuü]n))?\s+(?:de|da|te|ta)?\s*"
    r"(?:Değişiklik Yapılmasına Dair|Değişiklik Yapılmasına İlişkin)",
    re.I)
TITLE_AMEND_SIMPLE = re.compile(r"(?P<target>.+?)\s+(?:Değişiklik Yapılmasına Dair|Değişiklik Yapılmasına İlişkin)", re.I)

ARTICLE = re.compile(
    r"(?P<no>\d{1,3})\s*(?:inci|ıncı|nci|ncı|uncu|üncü|ncu|ncü|\.)\s*madde(?:si|nin)?", re.I)
KIND = [
    (re.compile(r"yürürlükten kaldırıl", re.I), "yururlukten_kalkti"),
    (re.compile(r"eklenmiştir|ilave edilmiştir|eklenmişt", re.I), "eklendi"),
    (re.compile(r"değiştirilmiştir|değiştirilmişt|şeklinde değiştir", re.I), "degisti"),
]


@dataclass
class Amendment:
    target_law: str
    article_ref: str
    change_kind: str
    snippet: str


def target_from_title(title: str) -> str:
    t = normalize(title)
    m = TITLE_AMEND_SIMPLE.search(t)
    if not m:
        return ""
    tgt = m.group("target").strip()
    # "Yönetmeliğinde" -> "Yönetmeliği" gibi çekim ekini sadeleştir
    tgt = re.sub(r"(?i)(yönetmeli[ğg])in(de|den)?$", r"\1i", tgt)
    return tgt


def extract(title: str, body: str, limit: int = 40) -> list[Amendment]:
    target = target_from_title(title)
    if not target:
        return []
    out: list[Amendment] = []
    text = normalize(body)
    for sent in re.split(r"(?<=[.])\s+|\n+", text):
        s = sent.strip()
        if not s or len(s) > 800:
            continue
        am = ARTICLE.search(s)
        if not am:
            continue
        kind = next((k for rx, k in KIND if rx.search(s)), "")
        if not kind:
            continue
        out.append(Amendment(target, f"{am.group('no')}. madde", kind, s[:300]))
        if len(out) >= limit:
            break
    return out
