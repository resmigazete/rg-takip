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
    assert ("9. madde (1. fık.)", "yururlukten_kalkti") in kinds

    # aynı sayı tekrar işlenirse atlanmalı
    assert pipeline.process_issue(conn, d, INDEX, text_fetcher=lambda u: BODIES.get(u, ""))["skipped"]

    text = briefing.build(conn, d)
    print(text)
    assert "Tıbbi Cihaz" in text and "Ankara Valiliğine" in text
    assert "Su Tarifesi" not in text
    assert "Sağlık Uygulama Tebliğinde" in text
    assert "Belediye Başkan Yardımcılığına" not in text


def test_law_refs_ve_reanalyze():
    """Değişen/kaldırılan mevzuat DB'ye yazılır, JSON'a çıkar ve ağsız yeniden hesaplanabilir."""
    from rgtakip import queries
    index = INDEX.replace("<h3>TEBLİĞLER</h3>",
                          '<a href="/eskiler/2026/11/20261116-6.htm">Sağlık Bakanlığı Örnek Merkezler Hakkında Yönetmelik</a><h3>TEBLİĞLER</h3>')
    bodies = dict(BODIES)
    bodies["https://www.resmigazete.gov.tr/eskiler/2026/11/20261116-6.htm"] = (
        "MADDE 9-\n(1)\n1/3/2019\ntarihli ve\n    30701 sayılı Resmî Gazete’de yayımlanan Örnek Merkezler\n    Yönetmelik yürürlükten kaldırılmıştır.")
    bodies["https://www.resmigazete.gov.tr/eskiler/2026/11/20261116-2.htm"] = (
        "MADDE 1- 2/2/2020 tarihli ve 31000 sayılı Resmî Gazete’de yayımlanan Tıbbi Cihaz Satış\n    Yönetmeliğinin 5 inci\n    maddesi aşağıdaki şekilde değiştirilmiştir.")
    conn = db.connect(":memory:")
    pipeline.process_issue(conn, date(2026, 11, 16), index, text_fetcher=lambda u: bodies.get(u, ""))
    day = queries.day(conn, "2026-11-16")
    by = {i["url"][-6:]: i for i in day["health"] + day["others"]}
    assert by["-6.htm"]["repealed"] == [{"title": "Örnek Merkezler Yönetmelik", "rg_date": "1/3/2019", "rg_no": "30701"}]
    assert by["-2.htm"]["base"]["rg_no"] == "31000"
    assert [a["article_ref"] for a in by["-2.htm"]["amendments"]] == ["5. madde"]

    # Ayrıştırıcı iyileşince eski kayıtlar ağ olmadan düzelir; tekrar çalıştırmak çoğaltmaz
    conn.execute("DELETE FROM amendments"); conn.execute("DELETE FROM law_refs"); conn.commit()
    n = pipeline.reanalyze(conn)
    assert n >= 3 and pipeline.reanalyze(conn) == n
    refs = conn.execute("SELECT role FROM law_refs ORDER BY id").fetchall()
    assert sorted(r["role"] for r in refs).count("repealed") == 1
    rows = conn.execute("SELECT item_id, article_ref FROM amendments WHERE article_ref='5. madde'").fetchall()
    assert len(rows) >= 1 and len(rows) == len({r["item_id"] for r in rows})
