from rgtakip import parser


def test_goreli_baglanti_arsiv_yoluna_cevrilir():
    html = '<h2>YÖNETMELİKLER</h2><a href="20261113-1.htm">Diyaliz Merkezleri Hakkında Yönetmelik</a>'
    it = parser.parse_index(html)[0]
    assert it.url == "https://www.resmigazete.gov.tr/eskiler/2026/11/20261113-1.htm"


def test_kok_mutlak_baglanti_cevrilir():
    html = '<h2>YÖNETMELİKLER</h2><a href="/20261110-4.htm">Bir Yönetmelik</a>'
    assert parser.parse_index(html)[0].url == "https://www.resmigazete.gov.tr/eskiler/2026/11/20261110-4.htm"


def test_zaten_dogru_ve_ilan_adresleri_degismez():
    assert parser.canonical_url("https://www.resmigazete.gov.tr/eskiler/2026/11/20261113-1.htm").endswith("/eskiler/2026/11/20261113-1.htm")
    u = "http://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261110-4-6.pdf"
    assert parser.canonical_url(u) == u


def test_mukerrer_ve_pdf():
    assert parser.canonical_url("https://x.gov.tr/20260918M1-8.pdf") == "https://x.gov.tr/eskiler/2026/09/20260918M1-8.pdf"
