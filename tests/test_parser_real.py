"""Gerçek sayıdan (17.11.2026) alınan biçimi taklit eden fihrist parçası."""
from rgtakip import classifier, parser

HTML = """
<html><body>
<a href="/20261117-1.htm">–– Adli \nTıp Kurumu Personeli Görevde Yükselme ve Unvan Değişikliği Yönetmeliğinde \nDeğişiklik Yapılmasına Dair Yönetmelik</a>
<a href="/20261117-3.pdf">––  Anayasa Mahkemesinin \n16/7/2026 Tarihli ve E: 2025/144, K: 2026/164 Sayılı Kararı</a>
<a href="http://www.resmigazete.gov.tr/main.aspx?home=http://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261117.htm&main=http://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261117-2.htm">a - Yargı İlânları</a>
<a href="http://www.resmigazete.gov.tr/main.aspx?home=x&main=http://www.resmigazete.gov.tr/ilanlar/eskiilanlar/2026/11/20261117-5.htm">– T.C. Merkez Bankasınca Belirlenen Döviz Kurları ve Devlet İç Borçlanma \n\tSenetlerinin Günlük Değerleri</a>
</body></html>
"""


def test_real_format():
    it = parser.parse_index(HTML)
    assert len(it) == 4
    assert it[0].title.startswith("Adli Tıp Kurumu Personeli") and "\n" not in it[0].title
    assert it[0].doc_type == "yonetmelik"
    assert it[1].doc_type == "yargi"
    assert it[2].doc_type == "ilan" and it[3].doc_type == "ilan"
    assert classifier.classify(it[0].title, "", it[0].doc_type).is_health
