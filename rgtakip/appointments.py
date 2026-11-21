"""Atama / görevden alma cümlelerini kişi-görev-kurum olarak çıkarır (kural tabanlı).

Tipik kalıplar:
  "Ankara Valiliğine, İzmir Valisi Ahmet YILMAZ atanmıştır."
  "Ege Üniversitesi Rektörlüğüne, Prof. Dr. Ayşe DEMİR atanmıştır."
  "Mehmet KAYA'nın Sağlık Bakanlığı ... Genel Müdürlüğü görevinden alınmasına ..."
Heuristiktir; belirsiz cümleler `raw` ile kaydedilir, LLM katmanı sonra düzeltir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .textutil import normalize, tr_lower

ROLE_WORDS = [
    ("Valiliğine", "Vali"), ("Rektörlüğüne", "Rektör"),
    ("Genel Müdürlüğüne", "Genel Müdür"), ("Müsteşarlığına", "Müsteşar"),
    ("Müsteşar Yardımcılığına", "Müsteşar Yardımcısı"),
    ("Başkanlığına", "Başkan"), ("Başkan Yardımcılığına", "Başkan Yardımcısı"),
    ("Daire Başkanlığına", "Daire Başkanı"), ("Müdürlüğüne", "Müdür"),
    ("Başhekimliğine", "Başhekim"), ("Dekanlığına", "Dekan"),
    ("Genel Müdür Yardımcılığına", "Genel Müdür Yardımcısı"), ("Müdür Yardımcılığına", "Müdür Yardımcısı"),
    ("Üyeliğine", "Üye"), ("Başmüfettişliğine", "Başmüfettiş"), ("Müfettişliğine", "Müfettiş"),
    ("Müşavirliğine", "Müşavir"), ("Başdanışmanlığına", "Başdanışman"), ("Danışmanlığına", "Danışman"),
    ("Başkan Vekilliğine", "Başkan Vekili"), ("Rektör Yardımcılığına", "Rektör Yardımcısı"),
]
KEY_ROLES = {"Vali", "Rektör", "Genel Müdür", "Müsteşar", "Müsteşar Yardımcısı",
             "Başhekim", "Dekan"}  # "Başkan" gibi geniş unvanlar yalnızca sağlık kurumuysa öne çıkar

HEALTH_INST = re.compile(
    r"sağlık|hastane|tıp|ilaç|halk sağlığı|titck|tuseb|sosyal güvenlik|sgk|eczac|diş hekim",
    re.I)

_ROLE_ALT = "|".join(re.escape(w) for w, _ in sorted(ROLE_WORDS, key=lambda x: -len(x[0])))
APPOINT = re.compile(
    rf"(?P<inst>[^.\n;]{{2,140}}?(?:{_ROLE_ALT})),?\s*"
    rf"(?:(?P<pred>[^.\n;]{{2,100}}?)\s+(?:görevinden|yerine)[^.\n;]*?,?\s*)?"
    rf"(?P<person>[^.\n;]{{3,110}}?)\s+atanm(?:ıştır|ıs|asına)",
    re.I)
REMOVAL = re.compile(
    r"(?P<person>[^.\n;]{3,110}?)(?:['’]n[ıiuü]n)?\s+(?P<inst>[^.\n;]{2,140}?)\s+görevinden\s+(?:alınmas|alınm|affı)",
    re.I)


@dataclass
class Appointment:
    person: str
    new_role: str
    institution: str
    predecessor: str
    action: str
    is_key_role: bool
    is_health: bool
    raw: str


def _role_of(inst: str) -> str:
    for w, role in sorted(ROLE_WORDS, key=lambda x: -len(x[0])):
        if inst.endswith(w):
            return role
    return ""


_HEADER = re.compile(r"^.*?Karar\s+Sayısı\s*:\s*[\w/.\-]+\s*|^\s*KARAR\s+(?=\S)", re.I)


def _strip_header(inst: str) -> str:
    """PDF'te satırlar birleşince kurum adının önüne yapışan 'KARAR Karar Sayısı : 2026/400' başlığını at."""
    return _HEADER.sub("", inst).strip(" ,")


def _clean_person(s: str) -> str:
    s = normalize(s).replace("§", ".").strip(" ,-–")
    # "İzmir Valisi Ahmet YILMAZ" -> sadece unvan+ad kısmını bırakma, olduğu gibi tut
    return s


# --- Cumhurbaşkanlığı atama kararı biçimi -------------------------------------------------
# "Karar: 2026/390 ... 3 sayılı Cumhurbaşkanlığı Kararnamesinin ... gereğince <Kurum Unvan Ad SOYAD>
#  görevden alınmış ve bu suretle boşalan <Kadro>ne, <Ad SOYAD> atanmıştır."
_CB_HEADER = re.compile(r"Cumhurbaşkanlığından\s*:?\s*|Karar\s*:\s*\d{4}/\d+\s*", re.I)
_CB_SIGNATURE = re.compile(r"\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}\s+Recep\s+Tayyip\s+ERDOĞAN\s+CUMHURBAŞKANI", re.I)
# "3 sayılı Cumhurbaşkanlığı Kararnamesinin 2, 3 ve 4 üncü maddeleri gereğince" (ve "233 sayılı KHK ... ile ...")
_LEGAL = re.compile(r",?\s*\d+\s+sayılı\s+[^.;]*?(?:gereğince|uyarınca)\s*,?\s*", re.I)
_REMOVED = re.compile(r"^(?P<pre>.+?)\s+görev(?:inden|den)\s+(?:alınmış|alınmıştır|affedilmiş|affedilmiştir)\b(?P<rest>.*)$", re.I)
_AFTER = re.compile(r"(?:ve\s+bu\s+suretle\s+boşalan|yerine)\s+(?P<body>.+?)\s+atanm(?:ıştır|ıs)", re.I)
_NAME = r"[A-ZÇĞİÖŞÜ][a-zçğıöşüâîû]+"
_SURNAME = r"[A-ZÇĞİÖŞÜ]{2,}(?:\s+[A-ZÇĞİÖŞÜ]{2,})?"
_TRAILING_PERSON = re.compile(rf"((?:{_NAME}\s+){{1,3}}{_SURNAME})\s*$")
_ROLE_TOKENS = {
    "Müdürü", "Başkanı", "Valisi", "Rektörü", "Dekanı", "Müsteşarı", "Yardımcısı", "Başhekimi", "Kaymakamı",
    "Müşaviri", "Danışmanı", "Müfettişi", "Başmüfettişi", "Üyesi", "Sekreteri", "Amiri", "Komutanı",
    "Savcısı", "Hâkimi", "Bakanı", "Vekili", "Şefi", "Şube", "Daire", "İl", "İlçe", "Genel", "Müdür",
}
_MINISTRY = re.compile(r"^.*?(?:Bakanlığı|Başkanlığı|Kurumu|Üniversitesi|Kurulu|Teşkilatı)\b")


def _split_person(pre: str) -> tuple[str, str]:
    """'... Genel Müdürü Ömer ALAN' -> ('... Genel Müdürü', 'Ömer ALAN')."""
    pre = pre.strip(" ,")
    m = _TRAILING_PERSON.search(pre)
    if not m:
        return pre, ""
    toks = m.group(1).split()
    surname = [t for t in toks if t.isupper() and len(t) > 1]
    names = [t for t in toks if t not in surname]
    keep: list[str] = []
    for t in reversed(names):          # sondan başa: unvan sözcüğüne gelince dur
        if t in _ROLE_TOKENS:
            break
        keep.insert(0, t)
    if not keep:
        return pre, ""
    person = " ".join(keep + surname)
    return pre[: pre.rfind(person)].strip(" ,"), person


def _cb_sentence(s: str) -> list[Appointment]:
    m = _REMOVED.match(s)
    if not m:
        return []
    inst_old, person_old = _split_person(m.group("pre"))
    if not person_old:
        return []
    low = tr_lower(inst_old)
    out = [Appointment(
        person=person_old, new_role="", institution=inst_old, predecessor="", action="gorevden_alma",
        is_key_role=any(k in low for k in ("vali", "rektör", "genel müdür", "müsteşar")),
        is_health=bool(HEALTH_INST.search(low)), raw=s)]
    a = _AFTER.search(m.group("rest"))
    if a:
        mm = re.match(rf"(?P<inst>.+?(?:{_ROLE_ALT}))\s*,?\s*(?P<person>.+)$", a.group("body"))
        if mm:
            inst = mm.group("inst").strip(" ,")
            mn = _MINISTRY.match(inst_old)
            if mn and not inst.startswith(mn.group(0)):
                inst = f"{mn.group(0)} {inst}"
            role = _role_of(inst)
            out.append(Appointment(
                person=_clean_person(mm.group("person")), new_role=role or "Diğer", institution=inst,
                predecessor=person_old, action="atama", is_key_role=role in KEY_ROLES,
                is_health=bool(HEALTH_INST.search(tr_lower(inst))), raw=s))
    return out


_ABBR = re.compile(r"\b(Prof|Dr|Doç|Av|Uzm|Yrd|Öğr|Üyesi|Müh|Alb|Org|Tuğg|Kd|Bşk|No|Sn)\.", re.I)


def extract(text: str) -> list[Appointment]:
    out: list[Appointment] = []
    # Unvan kısaltmalarındaki noktalar cümle sonu sayılmasın
    text = _ABBR.sub(lambda m: m.group(1) + "§", normalize(text))
    # Cumhurbaşkanlığı atama kararı: başlık/imza ve "N sayılı ... gereğince" dayanak ibaresini at
    text = re.sub(r"[—–\-]{2,}\s*[o•●·]?\s*[—–\-]{2,}", "\n", text)   # "——— o ———" ayırıcıları
    text = _CB_SIGNATURE.sub("\n", text)
    text = _CB_HEADER.sub("\n", text)
    text = _LEGAL.sub(" ", text)
    # "…Valiliğine,\nAd SOYAD atanmıştır." gibi satır sonunda virgülle bölünmüş cümleleri birleştir
    text = re.sub(r",[ \t]*\n+[ \t]*", ", ", text)
    for sent in re.split(r"(?<=[.])\s+|\n+", text):
        s = sent.strip().replace("§", ".")
        # regex'ler nokta içeremez; unvan noktalarını geçici gizle
        s_work = _ABBR.sub(lambda m: m.group(1) + "§", s)
        if not s or len(s) > 600:
            continue
        cb = _cb_sentence(s)
        if cb:
            out.extend(cb)
            continue
        m = APPOINT.search(s_work)
        if m:
            inst = _strip_header(normalize(m.group("inst")).replace("§", ".").strip(" ,"))
            role = _role_of(inst)
            person = _clean_person(m.group("person"))
            pred = _clean_person(m.group("pred") or "")
            out.append(Appointment(
                person=person, new_role=role or "Diğer", institution=inst,
                predecessor=pred, action="atama",
                is_key_role=role in KEY_ROLES,
                is_health=bool(HEALTH_INST.search(tr_lower(inst))),
                raw=s))
            continue
        m = REMOVAL.search(s_work)
        if m:
            inst = normalize(m.group("inst")).replace("§", ".")
            out.append(Appointment(
                person=_clean_person(m.group("person")), new_role="", institution=inst,
                predecessor="", action="gorevden_alma",
                is_key_role=any(k.lower() in tr_lower(inst) for k in ("vali", "rektör", "genel müdür", "müsteşar")),
                is_health=bool(HEALTH_INST.search(tr_lower(inst))),
                raw=s))
    return out
