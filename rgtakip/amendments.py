"""Mevzuat değişikliklerini tespit eder: hangi mevzuat, hangi madde, ne yapıldı.

Eski API korunur: `extract(title, body)` -> list[Amendment] (db/pipeline değişmeden çalışır).
Yeni: `analyze(title, body)` -> Analysis
    type      : "degisiklik" | "kaldirma" | "yeni"
    base      : değişikliğin hedefi (başlık + RG tarih/sayı), yalnız "degisiklik"
    repealed  : yürürlükten kaldırılan düzenlemeler ("yeni" ve "kaldirma")
    amendments: madde bazında işlemler (eski Amendment nesneleri)

Sonraki aşama: mevzuat.gov.tr'den ana metnin eski halini çekip madde bazında diff üretmek.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

try:
    from .textutil import normalize
except ImportError:  # modül tek başına test edilirken
    def normalize(s: str) -> str:
        return unicodedata.normalize("NFC", s or "")

TITLE_AMEND_SIMPLE = re.compile(r"(?P<target>.+?)\s+(?:Değişiklik Yapılmasına Dair|Değişiklik Yapılmasına İlişkin)", re.I)
TITLE_REPEAL = re.compile(r"(?P<target>.+?)\s+Yürürlükten Kaldırılmasına\s+(?:Dair|İlişkin)", re.I)

_ORD = r"(?:inci|ıncı|nci|ncı|uncu|üncü|ncu|ncü|\.)"
_NUM = r"\d{1,3}(?:/[A-ZÇĞİÖŞÜ])?"
_ITEM = rf"(?:(?:geçici|ek)\s+)?{_NUM}\s*{_ORD}"                       # "17 nci", "geçici 2 nci"
_LIST = rf"{_ITEM}(?:\s*(?:,|\bve\b|\bile\b)\s*{_ITEM})*"           # "4 üncü ve 5 inci"

# MADDE 3-  /  GEÇİCİ MADDE 1-  /  MADDE 1 –   (gerçek metinde başlık ayrı satırdadır: "MADDE 37-\n(1)")
_HEAD = re.compile(r"(?:(?:GEÇİCİ|EK)\s+)?MADDE\s+[\dlI]{1,3}\s*[-–—]")   # Resmî Gazete bazen "MADDE l-" (harf) basar
_MD_HEAD = re.compile(r"(?m)^[ \t]*#+[ \t]*((?:(?:GEÇİCİ|EK)\s+)?MADDE\s+\d+)[ \t]*$")

_FIK = {"birinci": "1", "ikinci": "2", "üçüncü": "3", "dördüncü": "4", "beşinci": "5", "altıncı": "6", "yedinci": "7",
        "sekizinci": "8", "dokuzuncu": "9", "onuncu": "10", "on birinci": "11", "on ikinci": "12", "son": "son"}
_ORDW = r"(?:on\s+birinci|on\s+ikinci|birinci|ikinci|üçüncü|dördüncü|beşinci|altıncı|yedinci|sekizinci|dokuzuncu|onuncu|son)"

_TOKEN = re.compile(
    rf"(?P<after>(?P<an>{_NUM})\s*{_ORD}?\s*madde(?:sin)?den\s+sonra\s+gelmek\s+üzere)"
    r"|(?P<sameafter>[Aa]ynı\s+madde(?:sin)?den\s+sonra\s+gelmek\s+üzere)"
    rf"|(?P<art>(?P<lst>{_LIST})\s*madde\w*)"
    r"|(?P<same>[Aa]ynı\s+madde\w*)"
    rf"|(?P<fik>(?P<fl>{_ORDW}(?:\s*(?:,|\bve\b)\s*{_ORDW})*)\s+f[ıi]kra\w*)"
    r"|(?P<rep>yürürlükten\s+kaldırıl\w*)"
    r"|(?P<add>eklen\w*|ilave\s+edil\w*)"
    r"|(?P<chg>değiştirilmiş\w*|şeklinde\s+değiştir\w*)",
    re.I)

# "1/3/2019 tarihli ve 30701 sayılı Resmî Gazete'de yayımlanan <başlık> Yönetmeliğin ..."
_DATE = r"\d{1,2}[/.]\d{1,2}[/.]\d{4}"
_BASE_HEAD = (
    rf"(?P<date>{_DATE})\s+tarihli\s+ve\s+(?P<no>\d+)(?:\s+mükerrer)?\s+sayılı\s+"
    r"Resm[iî]\s+Gazete\S{0,3}\s+yayımlanan\s+"
    rf"(?P<title>(?:(?!{_DATE}\s+tarihli).){{1,250}}?)\s+"          # başka bir RG referansına taşmaz
    r"(?P<kind>Yönetmeli\w*|Tebli[ğg]\w*|Kanun\w*)(?P<extra>\s*\([^)]{1,40}\))?")
_BASE = re.compile(_BASE_HEAD + r"(?:[’'][a-zçğıöşü]{1,4})?(?=\s+\d)")  # "... Yönetmeliğin 4 üncü ...", "Tebliğ (No: 1)’in 4 üncü"
_REPEALED = re.compile(_BASE_HEAD + r"\s+yürürlükten\s+kaldırıl")        # "... Yönetmelik yürürlükten kaldırılmıştır"

KIND_NAMES = {"rep": "yururlukten_kalkti", "add": "eklendi", "chg": "degisti"}


@dataclass
class Amendment:
    target_law: str
    article_ref: str
    change_kind: str
    snippet: str


@dataclass
class Ref:
    title: str
    rg_date: str = ""
    rg_no: str = ""

    def as_dict(self) -> dict:
        return {"title": self.title, "rg_date": self.rg_date, "rg_no": self.rg_no}


@dataclass
class Analysis:
    type: str                                   # degisiklik | kaldirma | yeni
    base: Ref | None = None
    repealed: list[Ref] = field(default_factory=list)
    amendments: list[Amendment] = field(default_factory=list)


def _tr_lower(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def _strip_target_suffix(t: str) -> str:
    # "Yönetmeliğinde/-nin/-den" -> "Yönetmeliği", "Yönetmelikte" -> "Yönetmeliği", "Tebliğinde" -> "Tebliği"
    t = re.sub(r"(?i)(yönetmeli[ğg])i(?:nin|n|nde|nden)$", r"\1i", t)
    t = re.sub(r"(?i)yönetmelikte$", "Yönetmeliği", t)
    t = re.sub(r"(?i)(tebli[ğg])i(?:nin|n|nde|nden)$", r"\1i", t)
    return re.sub(r"(\))[’'][a-zçğıöşü]{1,4}$", r"\1", t)         # "(Tebliğ No: 2025/4)’de" -> "(Tebliğ No: 2025/4)"


def target_from_title(title: str) -> str:
    t = normalize(title)
    m = TITLE_AMEND_SIMPLE.search(t)
    if not m:
        return ""
    return _strip_target_suffix(m.group("target").strip())


def _nominative(s: str) -> str:
    s = re.sub(r"(?i)yönetmeli[ğg]i$", "Yönetmelik", s)
    return re.sub(r"(?i)tebli[ğg]i$", "Tebliğ", s)


def _kind_name(word: str) -> str:
    if word.lower().startswith("yönetmeli"):
        return "Yönetmelik"
    if word.lower().startswith("tebli"):
        return "Tebliğ"
    return "Kanun"


def _ref(m: re.Match) -> Ref:
    extra = re.sub(r"\s+", " ", m.group("extra") or "")
    return Ref(f"{m.group('title')} {_kind_name(m.group('kind'))}{extra}", m.group("date"), m.group("no"))


def _strip_quotes(text: str) -> str:
    """“...” içindeki (iç içe olabilen) madde gövdelerini atar: oradaki 'değiştirilmiş', '5 inci madde' vb. sahte işlemdir."""
    out, depth = [], 0
    for ch in text:
        if ch == "“":
            depth += 1
        elif ch == "”":
            depth = max(0, depth - 1)
            if depth == 0:
                out.append(" ")
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def _prepare(body: str) -> str:
    """Gerçek metin sabit genişlikte satırlara bölünmüştür ("17\nnci\nmaddesinin"): boşlukları tek aralığa indirir."""
    s = unicodedata.normalize("NFC", (body or "").replace("\xa0", " "))
    s = _strip_quotes(s)
    s = _MD_HEAD.sub(r"\1-", s)
    return re.sub(r"\s+", " ", s).strip()


def _split_maddeler(text: str) -> list[str]:
    heads = list(_HEAD.finditer(text))
    if not heads:
        return [text]
    parts = [text[:heads[0].start()]]   # ilk başlıktan öncesi de taranır (başlık tanınmasa bile işlem kaçmasın)
    parts += [text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)] for i, h in enumerate(heads)]
    return parts


def _item_label(item: str) -> str:
    """"17 nci" -> "17"; "geçici 2 nci" -> "Geçici 2"; "ek 1 inci" -> "Ek 1"."""
    m = re.match(rf"(?:(geçici|ek)\s+)?({_NUM})", item, re.I)
    prefix = (m.group(1) or "").capitalize()
    return f"{prefix} {m.group(2)}".strip()


def _fik_label(fl: str) -> str:
    nums = [_FIK[re.sub(r"\s+", " ", w.lower())] for w in re.findall(_ORDW, fl, re.I)]
    if nums == ["son"]:
        return "son fık."
    return ", ".join(nums) + ". fık."


def _ops_in_madde(body: str) -> list[tuple[str, str, str]]:
    """Tek bir MADDE'deki işlemler: [(madde_no veya 'N sonrası', kind, fıkra), ...]"""
    ops: list[tuple[str, str, str]] = []
    fik = ""
    pending: list[str] = []
    last: str | None = None
    for m in _TOKEN.finditer(body):
        if m.group("after"):
            last = f"{m.group('an')} sonrası"
            pending = [last]
        elif m.group("sameafter"):
            if last:
                last = last.split(" ")[0] + " sonrası"
                pending = [last]
        elif m.group("art"):
            names = [_item_label(x) for x in re.findall(_ITEM, m.group("lst"), re.I)]
            last = names[-1]
            pending.extend(names)
        elif m.group("same"):
            if last:
                pending.append(last)
        elif m.group("fik"):
            fik = _fik_label(m.group("fl"))
        else:
            kind = KIND_NAMES["rep" if m.group("rep") else "add" if m.group("add") else "chg"]
            for art in (pending or ([last] if last else [])):
                if (art, kind, fik) not in ops:
                    ops.append((art, kind, fik))
            pending = []
            fik = ""
    return ops


def _ref_label(art: str, fik: str = "") -> str:
    base = f"{art[:-len(' sonrası')]}. madde sonrası" if art.endswith(" sonrası") else f"{art}. madde"
    return f"{base} ({fik})" if fik and not art.endswith(" sonrası") else base


def analyze(title: str, body: str) -> Analysis:
    t = _tr_lower(normalize(title))
    clean = _prepare(body)

    if "değişiklik yapılmasına" in t:
        base_m = _BASE.search(clean)
        base = _ref(base_m) if base_m else None
        target = base.title if base else _nominative(target_from_title(title))
        if base is None and target:
            base = Ref(target)
        a = Analysis("degisiklik", base=base)
        if not (target or base):
            return a
        law = target_from_title(title) or (base.title if base else "")
        for part in _split_maddeler(clean):
            snippet = part.strip()[:300]
            for art, kind, fik in _ops_in_madde(part):
                a.amendments.append(Amendment(law, _ref_label(art, fik), kind, snippet))
        return a

    if "yürürlükten kaldırılmasına" in t:
        a = Analysis("kaldirma")
        a.repealed = [_ref(m) for m in _REPEALED.finditer(clean)]
        if not a.repealed:
            m = TITLE_REPEAL.search(normalize(title))
            if m:
                a.repealed = [Ref(_nominative(_strip_target_suffix(m.group("target").strip())))]
        return a

    a = Analysis("yeni")
    a.repealed = [_ref(m) for m in _REPEALED.finditer(clean)]
    return a


def extract(title: str, body: str, limit: int = 40) -> list[Amendment]:
    """Eski API: yalnız 'Değişiklik Yapılmasına Dair' başlıklı metinler için madde işlemleri."""
    a = analyze(title, body)
    return a.amendments[:limit] if a.type == "degisiklik" else []
