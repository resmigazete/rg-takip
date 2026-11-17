"""Türkçe metin yardımcıları (İ/I tuzağına karşı)."""
import re


def tr_lower(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def normalize(s: str) -> str:
    s = s.replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", s).strip()
