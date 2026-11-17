from rgtakip import classifier


def test_saglik_bilimleri_universitesi_sb_rozeti_almaz_ama_saglik_sayilir():
    body = "Sağlık Bakanlığı ... Sağlık Bakanlığı ... Sağlık Bakanlığı Eğitim ve Araştırma Hastanesi"
    for b in ("", body):
        r = classifier.classify("Sağlık Bilimleri Üniversitesi Rektörlüğünden", b, "ilan",
                                issuer="Sağlık Bilimleri Üniversitesi Rektörlüğü")
        assert r.is_health
        assert "saglik_bakanligi" not in r.categories


def test_bakanlik_ilani_rozet_almaya_devam_eder():
    r = classifier.classify("Sağlık Bakanlığı Kamu Hastaneleri Genel Müdürlüğünden", "", "ilan",
                            issuer="Sağlık Bakanlığı Kamu Hastaneleri Genel Müdürlüğü")
    assert "saglik_bakanligi" in r.categories
