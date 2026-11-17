from datetime import date

from rgtakip import classifier, db, pipeline


def test_diyaliz_title():
    assert classifier.classify("Diyaliz Merkezleri Hakkında Yönetmelik", "", "yonetmelik").is_health


def test_body_density():
    body = "Sağlık Bakanlığı ... Sağlık Bakanlığınca ... Sağlık Bakanlığının izni"
    assert classifier.classify("Bir Merkezlerin Çalışma Usulleri Hakkında Yönetmelik", body, "yonetmelik").is_health


def test_unrelated_stays_unhealthy():
    assert not classifier.classify("Belediye Su Tarifesi Yönetmeliği", "su tarifesi", "yonetmelik").is_health


def test_force_reprocess_and_skip_rules():
    idx = '<a href="/eskiler/2026/11/20261113-1.htm">Diyaliz Merkezleri Hakkında Yönetmelik</a>'
    conn = db.connect(":memory:")
    d = date(2026, 11, 13)
    f = lambda u: ""
    # önceki bir denemeden kalan, maddesiz kayıt atlamaya yol açmamalı
    conn.execute("INSERT INTO issues(date, kind, index_hash) VALUES (?,?,?)",
                 ("2026-11-13", "normal", pipeline.fetcher.sha(idx)))
    st = pipeline.process_issue(conn, d, idx, text_fetcher=f)
    assert st["new"] == 1 and not st["skipped"]
    assert pipeline.process_issue(conn, d, idx, text_fetcher=f)["skipped"]
    st = pipeline.process_issue(conn, d, idx, text_fetcher=f, force=True)
    assert st["new"] == 1
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1


def test_saglik_bakanligi_ilani_yakalanir():
    r = classifier.classify("Sağlık Bakanlığı Ankara Şehir Hastanesi Başhekimliğinden Personel Alım İlanı", "", "ilan")
    assert r.is_health and r.importance >= 25


def test_alakasiz_ilan_saglik_degil():
    assert not classifier.classify("Ankara 5. İcra Müdürlüğünden Satış İlanı", "", "ilan").is_health



LISTING = """<html><body><h1>ÇEŞİTLİ İLÂNLAR</h1>
<p><a href="20261110-4-6.htm">Sağlık Bakanlığı Kamu Hastaneleri Genel Müdürlüğünden:</a></p>
<p><a href="20261110-4-1.htm">Toros Üniversitesi Rektörlüğünden:</a></p>
<p><a href="/ilanlar/eskiilanlar/2026/11/20261110-4-18.htm">Sağlık Bilimleri Üniversitesi Rektörlüğünden:</a></p>
<a href="/eskiler/2026/11/20261109.htm">Önceki Sayı</a></body></html>"""
BASE = "https://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261110-4.htm"


def test_ilan_listesi_ayrisir():
    from rgtakip import ilanlar
    got = ilanlar.parse_listing(LISTING, BASE)
    assert len(got) == 3
    assert got[0][0] == "Sağlık Bakanlığı Kamu Hastaneleri Genel Müdürlüğünden"
    assert got[0][1].endswith("/eskiilanlar/2026/11/20261110-4-6.htm")
    assert got[0][2] == ""   # Çeşitli İlanlar'da konu satırı yok


IHALE = """<h1>ARTIRMA, EKSİLTME VE İHALE İLÂNLARI</h1>
<p>TIBBİ CİHAZ ALIMI İHALE EDİLECEKTİR</p><p><a href="20261110-3-2.pdf">Ankara Şehir Hastanesi Başhekimliğinden:</a></p>
<p>ORMAN EMVALİ SATILACAKTIR</p><p><a href="20261110-3-3.pdf">Antalya Orman Bölge Müdürlüğü Kaş Orman İşletme Müdürlüğünden:</a></p>"""


def test_ihale_konu_satiri_ve_saglik():
    from rgtakip import ilanlar
    got = ilanlar.parse_listing(IHALE, "https://x.gov.tr/ilanlar/eskiilanlar/2026/11/20261110-3.htm")
    assert got[0][2] == "TIBBİ CİHAZ ALIMI İHALE EDİLECEKTİR"
    assert got[0][1].endswith("20261110-3-2.pdf")
    conn = db.connect(":memory:")
    st = ilanlar.expand(conn, "2026-11-10", "Artırma, Eksiltme ve İhale İlânları",
                        "https://x.gov.tr/ilanlar/eskiilanlar/2026/11/20261110-3.htm", lambda u: IHALE, lambda u: "")
    assert st["new"] == 2 and st["health"] == 1


def test_ilan_listesi_kayda_gecer():
    from rgtakip import ilanlar
    conn = db.connect(":memory:")
    bodies = {}
    ft = lambda u: "Sağlık Bakanlığı Kamu Hastaneleri Genel Müdürlüğünden:\nSÖZLEŞMELİ PERSONEL ALIM İLANI\nmetin"
    st = ilanlar.expand(conn, "2026-11-10", "Çeşitli İlânlar", BASE, lambda u: LISTING, ft)
    assert st["new"] == 3 and st["health"] == 2
    row = conn.execute("SELECT title, issuer FROM items WHERE title LIKE 'Sağlık Bakanlığı%'").fetchone()
    assert "PERSONEL ALIM İLANI" in row["title"]
    assert not ilanlar.is_listing("Yargı İlânları", "ilan")
    assert ilanlar.is_listing("Çeşitli İlânlar", "ilan")


def test_main_aspx_sarmalayici_cozulur():
    from rgtakip import ilanlar
    w = ("http://www.resmigazete.gov.tr/main.aspx?home=http://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261110.htm"
         "&main=http://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261110-4.htm")
    assert ilanlar.resolve_url(w).endswith("/eskiilanlar/2026/11/20261110-4.htm")
    assert ilanlar.resolve_url("https://x/20261110-4-6.pdf") == "https://x/20261110-4-6.pdf"


def test_fihristten_ilan_sayfasina_uctan_uca():
    """Gerçek fihrist biçimi: ilan bölümü main.aspx sarmalayıcıyla gelir; içindeki sağlık ilanı kayda girmeli."""
    from rgtakip import parser
    wrap = ("http://www.resmigazete.gov.tr/main.aspx?home=http://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261110.htm"
            "&main=http://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261110-4.htm")
    idx = f'<a href="{wrap}">c - Çeşitli İlânlar</a>'
    seen = []
    def hf(u):
        seen.append(u)
        return LISTING
    conn = db.connect(":memory:")
    st = pipeline.process_issue(conn, date(2026, 11, 10), idx, text_fetcher=lambda u: "", html_fetcher=hf)
    assert seen and seen[0].endswith("20261110-4.htm") and "main.aspx" not in seen[0]
    assert st["health"] == 2
    rows = conn.execute("SELECT title FROM items WHERE is_health=1").fetchall()
    assert len(rows) == 2
