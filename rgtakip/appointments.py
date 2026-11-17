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


def _clean_person(s: str) -> str:
    s = normalize(s).replace("§", ".").strip(" ,-–")
    # "İzmir Valisi Ahmet YILMAZ" -> sadece unvan+ad kısmını bırakma, olduğu gibi tut
    return s


_ABBR = re.compile(r"\b(Prof|Dr|Doç|Av|Uzm|Yrd|Öğr|Üyesi|Müh|Alb|Org|Tuğg|Kd|Bşk|No|Sn)\.", re.I)


def extract(text: str) -> list[Appointment]:
    out: list[Appointment] = []
    # Unvan kısaltmalarındaki noktalar cümle sonu sayılmasın
    text = _ABBR.sub(lambda m: m.group(1) + "§", normalize(text))
    for sent in re.split(r"(?<=[.])\s+|\n+", text):
        s = sent.strip().replace("§", ".")
        # regex'ler nokta içeremez; unvan noktalarını geçici gizle
        s_work = _ABBR.sub(lambda m: m.group(1) + "§", s)
        if not s or len(s) > 600:
            continue
        m = APPOINT.search(s_work)
        if m:
            inst = normalize(m.group("inst")).replace("§", ".").strip(" ,")
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
