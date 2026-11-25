import pathlib, shutil
import pytest
from rgtakip import appointments as ap

PDF = pathlib.Path(__file__).with_name("20261125-3.pdf")


def test_tablo_satiri():
    r = ap.extract("TABLO|16|Recep SOYTÜRK|Tekirdağ Valisi|Kayseri Valisi|\nTABLO|3|Ali Veli|X|Edime Valisi|")
    assert r[0].person == "Recep SOYTÜRK" and r[0].institution == "Kayseri Valisi"
    assert r[0].predecessor == "Önceki görev: Tekirdağ Valisi" and r[0].is_key_role
    assert r[1].institution == "Edirne Valisi"


def test_emrine_ve_baslik():
    r = ap.extract("TABLO|SIRA|ADI SOYADI|MEVCUT GÖREVİ|ATANDIĞI GÖREV|\nTABLO|1|Ziya POLAT|Kars Valisi|İçişleri Bakanlığı emrine|")
    assert len(r) == 1 and r[0].new_role == ""


@pytest.mark.skipif(not shutil.which("tesseract") or not shutil.which("pdftoppm"), reason="OCR yok")
def test_gercek_pdf():
    from rgtakip import fetcher
    r = ap.extract(fetcher.pdf_to_text(PDF.read_bytes()))
    assert len(r) >= 59
    assert any(x.person == "Bülent AY" for x in r)


def test_telegram_kompakt():
    import sqlite3
    from datetime import date
    from rgtakip import briefing
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
    c.executescript("CREATE TABLE items(id,issue_date,title,url);CREATE TABLE appointments(id INTEGER PRIMARY KEY,item_id,person,new_role,institution,predecessor,action,is_key_role,is_health);")
    c.execute("INSERT INTO items VALUES(1,'2026-11-25','Karar','http://x')")
    for i in range(10):
        c.execute("INSERT INTO appointments(item_id,person,new_role,institution,predecessor,action,is_key_role,is_health) VALUES(1,?,?,?,?,?,1,0)",
                  (f"Kişi {i}", "Vali", f"Şehir{i} Valisi", "Önceki görev: Kars Valisi", "atama"))
    m = briefing.build_atamalar(c, date(2026, 11, 25))
    assert "Vali atamaları (10)" in m and "Şehir3 Valisi: Kişi 3 ← Kars Valisi" in m
