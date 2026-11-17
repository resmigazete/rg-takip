"""Kural tabanlı sağlık sınıflandırması + önem puanı.

Katman 1 (burada): ağırlıklı anahtar kelime. Hızlı, açıklanabilir, ücretsiz.
Katman 2 (sonra): belirsiz kayıtlar (skor 15-45) için LLM ile doğrulama/özet.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .textutil import tr_lower

# (regex, ağırlık, kategori)
HEALTH_RULES: list[tuple[str, int, str]] = [
    (r"sağlık bakanlığ", 40, "saglik_bakanligi"),
    (r"türkiye ilaç ve tıbbi cihaz kurumu|titck", 40, "ilac_cihaz"),
    (r"sosyal güvenlik kurumu|sgk|geri ödeme listesi|sut\b|sağlık uygulama tebliği", 30, "sgk_odeme"),
    (r"türkiye halk sağlığı|halk sağlığı", 30, "halk_sagligi"),
    (r"türkiye sağlık enstitüleri|tuseb", 35, "arastirma"),
    (r"kamu hastaneler|şehir hastane|hastane", 25, "hastane_kurum"),
    (r"ilaç|beşeri tıbbi|ruhsat|reçete", 25, "ilac_cihaz"),
    (r"tıbbi cihaz|medikal|in vitro", 25, "ilac_cihaz"),
    (r"tıp fakülte|diş hekim|eczac|hemşire|ebe\b|ebelik|sağlık hizmetleri meslek", 25, "saglik_egitim"),
    (r"sağlık personel|hekim|uzman tabip|asistan|döner sermaye", 25, "saglik_personel"),
    (r"sağlık|tedavi|hasta\b|hastalık|aşı|bulaşıcı|salgın|epidemi|pandemi", 15, "genel_saglik"),
    (r"sosyal hizmet|engelli|yaşlı bakım|bakım merkezi", 10, "sosyal_hizmet"),
    (r"tütün|alkol|bağımlılık|uyuşturucu", 15, "halk_sagligi"),
    (r"gıda güvenli|gıda ve yem|veteriner", 10, "gida_veteriner"),
]

# Doküman türüne göre taban önem
TYPE_BASE = {
    "kanun": 60, "khk": 70, "cb_kararname": 60, "cb_karari": 45,
    "yonetmelik": 40, "teblig": 30, "atama": 35, "kurul_karari": 25,
    "genelge": 30, "yonerge": 20, "yargi": 15, "ilan": 5, "diger": 10,
}

ORG_BOOST = [
    (r"sağlık bakanlığ", 15),
    (r"cumhurbaşkan", 5),
    (r"sağlık uygulama tebliği|geri ödeme listesi", 15),
]


@dataclass
class Result:
    is_health: bool
    health_score: int
    importance: int
    categories: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def classify(title: str, body: str = "", doc_type: str = "diger") -> Result:
    # Başlıkta geçen eşleşme gövdeden iki kat değerli
    t = tr_lower(title)
    b = tr_lower(body[:6000])  # ilk bölüm yeterli, hız için kırp
    score = 0
    cats: list[str] = []
    reasons: list[str] = []
    for pat, w, cat in HEALTH_RULES:
        in_title = re.search(pat, t) is not None
        in_body = re.search(pat, b) is not None
        if in_title:
            score += w
        elif in_body:
            score += w // 2
        if in_title or in_body:
            if cat not in cats:
                cats.append(cat)
            reasons.append(f"{cat}:{'başlık' if in_title else 'metin'}")
    score = min(score, 100)
    is_health = score >= 25

    importance = 0
    if is_health:
        importance = TYPE_BASE.get(doc_type, 10)
        importance += min(score // 4, 25)
        for pat, bonus in ORG_BOOST:
            if re.search(pat, t):
                importance += bonus
        # değişiklik yönetmeliği ana düzenleme kadar kritik değil ama yine de önemli
        if "değişiklik yapılmasına dair" in t:
            importance -= 5
    importance = max(0, min(importance, 100))
    return Result(is_health, score, importance, cats, reasons)
