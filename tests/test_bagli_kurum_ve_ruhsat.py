import pytest

from rgtakip import classifier


@pytest.mark.parametrize("title", [
    "Türkiye Sağlık Enstitüleri Başkanlığı Personel Alım İlanı",
    "TÜSEB Araştırma Destek Yönetmeliği",
    "USHAŞ Uluslararası Sağlık Hizmetleri A.Ş. Genel Müdürlüğünden",
    "Türkiye İlaç ve Tıbbi Cihaz Kurumu Başkanlığından",
    "TİTCK Ruhsatlandırma Yönetmeliği",
    "Hudut ve Sahiller Sağlık Genel Müdürlüğü Personel Alım İlanı",
])
def test_bagli_kurumlar_saglik_bakanligi_sayilir(title):
    r = classifier.classify(title, "", "ilan")
    assert r.is_health and "saglik_bakanligi" in r.categories


@pytest.mark.parametrize("title", [
    "6 ADET JEOTERMAL KAYNAK ARAMA RUHSAT SAHASI İHALE EDİLECEKTİR — Afyonkarahisar İl Özel İdaresi İl Encümeni Başkanlığından",
    "6 ADET JEOTERMAL KAYNAK RUHSAT SAHASI İHALE EDİLECEKTİR — Denizli Valiliği Yatırım İzleme ve Koordinasyon Başkanlığından",
    "Maden Ruhsat Sahası İhale İlanı",
])
def test_jeotermal_ruhsat_ihalesi_saglik_degil(title):
    assert not classifier.classify(title, "", "ilan").is_health


def test_ilac_ruhsati_hala_saglik():
    assert classifier.classify("Beşeri Tıbbi Ürünlerin Ruhsatlandırılması Hakkında Yönetmelik", "", "yonetmelik").is_health
