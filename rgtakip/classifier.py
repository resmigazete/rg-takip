"""Kural tabanlı sağlık sınıflandırması + önem puanı.

Katman 1 (burada): ağırlıklı anahtar kelime. Hızlı, açıklanabilir, ücretsiz.
Katman 2 (sonra): belirsiz kayıtlar (skor 15-45) için LLM ile doğrulama/özet.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .textutil import tr_lower

# Sağlık Bakanlığı'na bağlı / ilişkili kuruluşlar (rozet ve skor için "Sağlık Bakanlığı" sayılır)
AFFILIATE_PAT = (r"türkiye sağlık enstitüleri|tüseb|tuseb"
                 r"|uluslararası sağlık hizmetleri|ushaş|ushas"
                 r"|türkiye ilaç ve tıbbi cihaz kurum|titck"
                 r"|hudut ve sahiller sağlık")
AFFILIATE_RE = re.compile(AFFILIATE_PAT)

# Başlıkta geçerse (ve güçlü sağlık sinyali yoksa) sağlık dışı sayılan konular: jeotermal/maden ruhsat ihaleleri vb.
EXCLUDE_TITLE_RE = re.compile(r"jeotermal|ruhsat sahas|maden|petrol|doğal gaz|taş ocağ|orman emval")
STRONG_HEALTH_RE = re.compile(r"sağlık|hastane|tıbbi|ilaç|hekim|hasta\b|eczane")

# (regex, ağırlık, kategori)
HEALTH_RULES: list[tuple[str, int, str]] = [
    (r"sağlık bakanlığ", 40, "saglik_bakanligi"),
    (AFFILIATE_PAT, 40, "saglik_bakanligi"),
    (r"türkiye ilaç ve tıbbi cihaz kurumu|titck", 40, "ilac_cihaz"),
    (r"sosyal güvenlik kurumu|sgk|geri ödeme listesi|sut\b|sağlık uygulama tebliği", 30, "sgk_odeme"),
    (r"türkiye halk sağlığı|halk sağlığı", 30, "halk_sagligi"),
    (r"türkiye sağlık enstitüleri|tüseb|tuseb", 35, "arastirma"),
    (r"kamu hastaneler|şehir hastane|hastane", 25, "hastane_kurum"),
    (r"ilaç|beşeri tıbbi|reçete|(?:tıbbi|ilaç|ürün|eczane|hastane|sağlık|cihaz)\\w*\\s+ruhsat", 25, "ilac_cihaz"),
    (r"tıbbi cihaz|medikal|in vitro", 25, "ilac_cihaz"),
    (r"tıp fakülte|diş hekim|eczac|hemşire|ebe\b|ebelik|sağlık hizmetleri meslek", 25, "saglik_egitim"),
    (r"sağlık personel|hekim|uzman tabip|asistan|döner sermaye", 25, "saglik_personel"),
    (r"sağlık|tedavi|hasta\b|hastalık|aşı|bulaşıcı|salgın|epidemi|pandemi", 15, "genel_saglik"),
    (r"adli tıp", 25, "adli_tip"),
    (r"diyaliz|hemodiyaliz|organ nakli|organ ve doku|kan ve kan ürünleri|kan merkez", 30, "tedavi_hizmeti"),
    (r"ameliyat|cerrahi|poliklinik|klinik|yoğun bakım|ambulans|acil sağlık|112 acil", 25, "tedavi_hizmeti"),
    (r"laboratuvar|radyoloji|görüntüleme merkez|tanı merkez|patoloji", 20, "tedavi_hizmeti"),
    (r"psikiyatri|ruh sağlığı|rehabilitasyon|fizik tedavi|diş protez|ağız ve diş", 25, "tedavi_hizmeti"),
    (r"tıbbi|tıp\b|tıbbî|eczane|eczacılık|beşeri|kozmetik|takviye edici|gıda takviye", 20, "ilac_cihaz"),
    (r"nadir hastalık|kanser|diyabet|obezite|bağışıklama|aşılama|enfeksiyon", 25, "halk_sagligi"),
    (r"sosyal hizmet|engelli|yaşlı bakım|bakım merkezi", 10, "sosyal_hizmet"),
    (r"tütün|alkol|bağımlılık|uyuşturucu", 15, "halk_sagligi"),
    (r"gıda güvenli|gıda ve yem|veteriner", 10, "gida_veteriner"),
]

# Üniversite hastanesi / tıp fakültesi hastanesi ibareleri (başlıkta da metinde de tam ağırlık)
UNIV_HOSPITAL_RE = re.compile(
    r"üniversite(?:si)?\s+(?:tıp\s+fakültesi\s+)?hastane"
    r"|tıp\s+fakültesi\s+hastane"
    r"|(?:uygulama\s+ve\s+araştırma|eğitim\s+ve\s+araştırma)\s+hastane"
    r"|sağlık\s+uygulama\s+ve\s+araştırma\s+merkez"
    r"|diş\s+hekimliği\s+(?:fakülte|uygulama)"
    r"|hastanesi\s+başhekim|başhekimliğ"
    r"|hastane\s+yönetim"
)
UNIV_HOSPITAL_W = 30

# Kurum satırı üniversite/rektörlük ise ilanın metni de kontrol edilir (başlık "sağlık" taşımasa da)
UNIVERSITY_ISSUER_RE = re.compile(r"üniversite|rektörlüğ")


def is_university_issuer(text: str) -> bool:
    return UNIVERSITY_ISSUER_RE.search(tr_lower(text)) is not None


# Doküman türüne göre taban önem
TYPE_BASE = {
    "kanun": 60, "khk": 70, "cb_kararname": 60, "cb_karari": 45,
    "yonetmelik": 40, "teblig": 30, "atama": 35, "kurul_karari": 25,
    "genelge": 30, "yonerge": 20, "yargi": 15, "ilan": 20, "diger": 10,
}

ORG_BOOST = [
    (r"sağlık bakanlığ", 15),
    (AFFILIATE_PAT, 15),
    (r"cumhurbaşkan", 5),
    (r"sağlık uygulama tebliği|geri ödeme listesi", 15),
]


# Düzenleme sayfalarının başındaki "Sağlık Bakanlığından:" gibi yayımlayan kurum satırı
ISSUER_RE = re.compile(r"(?m)^[ \t]*([^\n:]{3,120}?(?:ndan|nden|dan|den|tan|ten))[ \t]*:[ \t]*$")

# Yayımlayan kurum sağlıkla doğrudan ilgiliyse (ağırlık)
ISSUER_HEALTH = [
    (r"sağlık bakanlığ", 60),
    (AFFILIATE_PAT, 60),
    (r"ilaç ve tıbbi cihaz kurum", 60),
    (r"halk sağlığı", 60),
    (r"sağlık enstitüleri|sağlık bilimleri|sağlık hizmetleri", 50),
    (r"kamu hastaneler|şehir hastane", 50),
    (r"sosyal güvenlik kurum", 15),   # tek başına yetmez; SUT/geri ödeme sinyalleriyle birlikte
]


def normalize_issuer(raw: str) -> str:
    t = " ".join(raw.split())
    if t.endswith(("ndan", "nden")):
        return t[:-4]
    if t.endswith(("dan", "den", "tan", "ten")):
        return t[:-3]
    return t


# Yedek: satırlar parçalanmışsa boşlukları birleştirip kurum adı kalıbını ara
ISSUER_FALLBACK = re.compile(
    r"((?:[A-ZÇĞİÖŞÜ][^\s:]*\s+){0,7}?(?:[A-ZÇĞİÖŞÜ][^\s:]*\s+){0,2}"
    r"[A-ZÇĞİÖŞÜ]?[^\s:]*(?:Bakanlığ|Kurum|Başkanlığ|Kurul|Müdürlüğ|Üniversite|Banka|Enstitü|Meclis|Teşkilat|Rektörlüğ)[^\s:]*(?:ndan|nden))\s*:")


def _strip_heading_caps(text: str) -> str:
    """'YÖNETMELİK Sağlık Bakanlığı' -> 'Sağlık Bakanlığı' (baştaki tamamı büyük harfli başlık kelimeleri)."""
    toks = text.split()
    while toks and len(toks[0]) > 3 and toks[0].isupper():
        toks.pop(0)
    return " ".join(toks)


def extract_issuer(body: str) -> str:
    """Sayfanın ilk bölümünden 'X'ndan:' satırını bulur, 'X' biçiminde döndürür."""
    if not body:
        return ""
    line_hit = ""
    m = ISSUER_RE.search(body[:2500])
    if m:
        line_hit = normalize_issuer(m.group(1))
        if " " in line_hit.strip():  # çok sözcüklü ve tam satırsa güvenilir
            return line_hit
    # Satır tek sözcük kaldıysa (parçalanmış metin) ya da hiç yoksa: birleştirilmiş metinde ara
    flat = " ".join(body[:1500].split())
    m = ISSUER_FALLBACK.search(flat)
    if m:
        cand = _strip_heading_caps(m.group(1))
        if cand:
            return normalize_issuer(cand)
    return line_hit


@dataclass
class Result:
    is_health: bool
    health_score: int
    importance: int
    categories: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    issuer: str = ""


def classify(title: str, body: str = "", doc_type: str = "diger", issuer: str | None = None) -> Result:
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
    # Üniversite hastanesi ibaresi: başlıkta ya da metinde geçmesi yeterli (ilan, yönetmelik vb.)
    if UNIV_HOSPITAL_RE.search(t) or UNIV_HOSPITAL_RE.search(b):
        score += UNIV_HOSPITAL_W
        if "universite_hastanesi" not in cats:
            cats.append("universite_hastanesi")
        reasons.append("universite_hastanesi")
    # Yayımlayan kurum (en güvenilir sinyal)
    if issuer is None:
        issuer = extract_issuer(body)
        if not issuer and doc_type == "ilan":
            # İlan başlıkları genelde "Sağlık Bakanlığı ... Başhekimliğinden" gibi kurumla başlar
            issuer = extract_issuer(title.strip() + ":\n")
            if not issuer and re.search(r"sağlık bakanlığ", t):
                issuer = "Sağlık Bakanlığı"
    issuer_health = False
    il = tr_lower(issuer)
    for pat, w in ISSUER_HEALTH:
        if re.search(pat, il):
            score += w
            issuer_health = issuer_health or w >= 50
            reasons.append(f"yayımlayan:{issuer}")
            if "saglik_bakanligi" not in cats and w >= 50:
                cats.append("saglik_bakanligi")
            break

    # Gövdede "Sağlık Bakanlığı" sık geçiyorsa başlık sağlık kelimesi taşımasa da sağlıkla ilgilidir
    mentions = len(re.findall(r"sağlık bakanlığ", b))
    if mentions >= 3:
        score += 25
        if "saglik_bakanligi" not in cats:
            cats.append("saglik_bakanligi")
        reasons.append(f"gövdede sağlık bakanlığı x{mentions}")
    # Jeotermal/maden ruhsat ihalesi gibi sağlık dışı konular: kurum ya da başlıkta sağlık sinyali yoksa ele
    if (EXCLUDE_TITLE_RE.search(t) and not issuer_health
            and not AFFILIATE_RE.search(t + " " + il) and not STRONG_HEALTH_RE.search(t)):
        score = 0
        cats = []
        reasons.append("dışlandı:sağlık dışı konu")
    score = min(score, 100)
    is_health = score >= 25

    importance = 0
    if is_health:
        importance = TYPE_BASE.get(doc_type, 10)
        importance += min(score // 4, 25)
        for pat, bonus in ORG_BOOST:
            if re.search(pat, t):
                importance += bonus
        if issuer_health and not re.search(r"sağlık bakanlığ", t):
            importance += 15
        # değişiklik yönetmeliği ana düzenleme kadar kritik değil ama yine de önemli
        if "değişiklik yapılmasına dair" in t:
            importance -= 5
    importance = max(0, min(importance, 100))
    return Result(is_health, score, importance, cats, reasons, issuer)
