"""Çevrimdışı uçtan uca test. Fixture'lar UYDURMA örneklerdir (gerçek sayı değil)."""
from datetime import date

from rgtakip import briefing, db, pipeline

INDEX = """
<html><body>
<h2>YÜRÜTME VE İDARE BÖLÜMÜ</h2>
<h3>ATAMA KARARLARI</h3>
<a href="/eskiler/2026/11/20261116-1.htm">Atama Kararları</a>
<h3>YÖNETMELİKLER</h3>
<a href="/eskiler/2026/11/20261116-2.htm">Sağlık Bakanlığı Tıbbi Cihaz Satış Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik</a>
<a href="/eskiler/2026/11/20261116-3.htm">Bir Belediye Su Tarifesi Yönetmeliği</a>
<h3>TEBLİĞLER</h3>
<a href="/eskiler/2026/11/20261116-4.htm">Sağlık Uygulama Tebliğinde Değişiklik Yapılmasına Dair Tebliğ</a>
<h2>İLAN BÖLÜMÜ</h2>
<a href="/eskiler/2026/11/20261116-5.htm">Bir ticari ilan</a>
</body></html>
"""

BODIES = {
    "https://www.resmigazete.gov.tr/eskiler/2026/11/20261116-1.htm": (
        "Ankara Valiliğine, İzmir Valisi Ali VELİ atanmıştır.\n"
        "Örnek Üniversitesi Rektörlüğüne, Prof. Dr. Ayşe ÖRNEK atanmıştır.\n"
        "Sağlık Bakanlığı Kamu Hastaneleri Genel Müdürlüğüne, Dr. Can TEST atanmıştır.\n"
        "Bir Belediye Başkan Yardımcılığına Veli DENEME atanmıştır."),
    "https://www.resmigazete.gov.tr/eskiler/2026/11/20261116-2.htm": (
        "MADDE 1 – Yönetmeliğin 5 inci maddesi aşağıdaki şekilde değiştirilmiştir.\n"
        "MADDE 2 – Yönetmeliğin 9 uncu maddesinin birinci fıkrası yürürlükten kaldırılmıştır.\n"
        "MADDE 3 – Yönetmeliğe 12 nci maddesinden sonra gelmek üzere ek madde eklenmiştir."),
    "https://www.resmigazete.gov.tr/eskiler/2026/11/20261116-3.htm": "Su tarifesi belirlenmiştir.",
    "https://www.resmigazete.gov.tr/eskiler/2026/11/20261116-4.htm": (
        "MADDE 1 – Tebliğin 3 üncü maddesi değiştirilmiştir. Geri ödeme listesi güncellenmiştir."),
}


def test_end_to_end():
    conn = db.connect(":memory:")
    d = date(2026, 11, 16)
    st = pipeline.process_issue(conn, d, INDEX, text_fetcher=lambda u: BODIES.get(u, ""))
    assert st["new"] == 5

    rows = {r["url"][-6:]: r for r in conn.execute("SELECT * FROM items")}
    assert rows["-2.htm"]["is_health"] == 1
    assert rows["-3.htm"]["is_health"] == 0
    assert rows["-4.htm"]["is_health"] == 1
    assert rows["-5.htm"]["doc_type"] == "ilan"

    apps = conn.execute("SELECT * FROM appointments").fetchall()
    roles = {a["new_role"] for a in apps}
    assert {"Vali", "Rektör", "Genel Müdür"} <= roles
    assert any(a["is_health"] and a["new_role"] == "Genel Müdür" for a in apps)

    ams = conn.execute("SELECT * FROM amendments").fetchall()
    kinds = {(a["article_ref"], a["change_kind"]) for a in ams}
    assert ("5. madde", "degisti") in kinds
    assert ("9. madde", "yururlukten_kalkti") in kinds

    # aynı sayı tekrar işlenirse atlanmalı
    assert pipeline.process_issue(conn, d, INDEX, text_fetcher=lambda u: BODIES.get(u, ""))["skipped"]

    text = briefing.build(conn, d)
    print(text)
    assert "Tıbbi Cihaz" in text and "Ankara Valiliğine" in text
    assert "Su Tarifesi" not in text
    assert "Sağlık Uygulama Tebliğinde" in text
    assert "Belediye Başkan Yardımcılığına" not in text
