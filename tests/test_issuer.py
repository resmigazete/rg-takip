from datetime import date

from rgtakip import classifier, db, pipeline

BODY = "T.C. Resmî Gazete\n17 Kasım 2026\nYÖNETMELİK\nSağlık Bakanlığından:\nMADDE 1 – Bu Yönetmeliğin amacı..."


def test_extract_issuer():
    assert classifier.extract_issuer(BODY) == "Sağlık Bakanlığı"
    assert classifier.extract_issuer("Türkiye İlaç ve Tıbbi Cihaz Kurumundan:\nMADDE 1") == "Türkiye İlaç ve Tıbbi Cihaz Kurumu"
    assert classifier.extract_issuer("Ege Üniversitesi Rektörlüğünden:\nMADDE 1") == "Ege Üniversitesi Rektörlüğü"
    assert classifier.extract_issuer("Madde metni: bir şey") == ""


def test_issuer_makes_neutral_title_health():
    r = classifier.classify("Bir Merkezlerin Çalışma Usul ve Esasları Hakkında Yönetmelik", BODY, "yonetmelik")
    assert r.is_health and r.issuer == "Sağlık Bakanlığı"
    assert r.importance >= 40


def test_other_issuer_not_health():
    body = "YÖNETMELİK\nİçişleri Bakanlığından:\nMADDE 1 – Bu Yönetmelik..."
    r = classifier.classify("Bir Merkezlerin Çalışma Usul ve Esasları Hakkında Yönetmelik", body, "yonetmelik")
    assert not r.is_health and r.issuer == "İçişleri Bakanlığı"


def test_pipeline_stores_issuer():
    idx = '<a href="/eskiler/2026/11/20261113-1.htm">Çalışma Usul ve Esasları Hakkında Yönetmelik</a>'
    conn = db.connect(":memory:")
    pipeline.process_issue(conn, date(2026, 11, 13), idx, text_fetcher=lambda u: BODY)
    row = conn.execute("SELECT issuer, is_health FROM items").fetchone()
    assert row["issuer"] == "Sağlık Bakanlığı" and row["is_health"] == 1


def test_issuer_fragmented_lines():
    # HTML'de parçalanmış biçim: her metin düğümü ayrı satır
    body = "13 Kasım 2026 CUMA\nResmî Gazete\nSayı : 33429\nYÖNETMELİK\nSağlık\nBakanlığından:\nDİYALİZ MERKEZLERİ HAKKINDA YÖNETMELİK"
    assert classifier.extract_issuer(body) == "Sağlık Bakanlığı"


def test_issuer_same_line_as_heading():
    assert classifier.extract_issuer("YÖNETMELİK Sağlık Bakanlığından: DİYALİZ MERKEZLERİ") == "Sağlık Bakanlığı"


def test_no_false_issuer_from_header():
    assert classifier.extract_issuer("13 Kasım 2026 CUMA Resmî Gazete Sayı : 33429 YÖNETMELİK MADDE 1-") == ""
