from rgtakip import classifier


def test_universite_hastanesi_basligi():
    r = classifier.classify("Ege Üniversitesi Hastanesi Başhekimliğinden Personel İlanı", "", "ilan")
    assert r.is_health and "universite_hastanesi" in r.categories


def test_universite_ilani_metinde_hastane_gecerse_yakalanir():
    body = "Üniversitemiz Tıp Fakültesi Hastanesinde görevlendirilmek üzere öğretim üyesi alınacaktır."
    r = classifier.classify("Örnek Üniversitesi Rektörlüğünden", body, "ilan", issuer="Örnek Üniversitesi Rektörlüğü")
    assert r.is_health


def test_universite_ilani_hastane_yoksa_saglik_degil():
    body = "Mühendislik Fakültesi için araştırma görevlisi alınacaktır."
    r = classifier.classify("Örnek Üniversitesi Rektörlüğünden", body, "ilan", issuer="Örnek Üniversitesi Rektörlüğü")
    assert not r.is_health


def test_uygulama_ve_arastirma_hastanesi():
    assert classifier.classify("X Uygulama ve Araştırma Hastanesi Yönergesi", "", "yonetmelik").is_health
