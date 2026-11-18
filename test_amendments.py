from rgtakip.amendments import analyze, extract, target_from_title

T_2022 = "Diyaliz Merkezleri Hakkında Yönetmelikte Değişiklik Yapılmasına Dair Yönetmelik"
B_2022 = """
MADDE 1- 1/3/2019 tarihli ve 30701 sayılı Resmî Gazete’de yayımlanan Diyaliz Merkezleri Hakkında Yönetmeliğin 4 üncü maddesinin birinci fıkrasının (ı) bendi yürürlükten kaldırılmış, (j) ve (m) bentleri aşağıdaki şekilde değiştirilmiştir.
“j) Uzman tabip: İç hastalıkları uzmanı ile çocuk sağlığı ve hastalıkları uzmanını,”
MADDE 2- Aynı Yönetmeliğin 8 inci maddesinin ikinci fıkrasında yer alan “sertifikalı uzman tabip” ibaresi “uzman tabip” olarak değiştirilmiş, aynı maddenin üçüncü fıkrasında yer alan “diyaliz sertifikalı” ibaresi yürürlükten kaldırılmıştır.
MADDE 3- Aynı Yönetmeliğin 9 uncu maddesinin altıncı fıkrası aşağıdaki şekilde değiştirilmiş, aynı maddeye aşağıdaki fıkra eklenmiştir.
“(6) Halkın ihtiyaç duyacağı ... ünite kurulabilir.

a) Merkez bulunmayan kamuya ait hastaneler bünyesinde,”
“(11) Kaynakların etkin kullanımı ... Bakanlıkça azaltılabilir.”
MADDE 4- Aynı Yönetmeliğin 15 inci maddesinin birinci fıkrasının (a) bendinde yer alan “nefroloji yan dal eğitimi olan” ibaresi “nefroloji uzmanı bulunan” şeklinde değiştirilmiştir.
MADDE 5- Aynı Yönetmeliğin 21 inci maddesinin birinci fıkrasının (b) bendinde yer alan “diyaliz sertifikalı” ibaresi yürürlükten kaldırılmıştır.
MADDE 6- Aynı Yönetmeliğin 22 nci maddesinin birinci fıkrasının (a) ve (c) bentlerinde yer alan “sertifikalı uzman tabip” ibareleri “uzman tabip” olarak; aynı fıkranın (b) bendinde yer alan “otuz” ibareleri “elli” olarak değiştirilmiştir.
MADDE 7- Aynı Yönetmeliğin 25 inci maddesinin ikinci fıkrasında yer alan “sertifikalı uzman tabip” ibaresi “uzman tabip” şeklinde değiştirilmiş, aynı maddenin dördüncü fıkrasında yer alan “nefroloji uzmanı, sertifikalı uzman tabip” ibaresi “nefroloji uzmanı; uzman tabip” olarak değiştirilmiştir.
MADDE 8- Aynı Yönetmeliğin 26 ncı maddesinin birinci fıkrasında, 27 nci maddesinin birinci fıkrasında ve 29 uncu maddesinin ikinci fıkrasında yer alan “sertifikalı” ibareleri yürürlükten kaldırılmıştır.
MADDE 9- Aynı Yönetmeliğin 37 nci maddesinin birinci fıkrasında yer alan “iç hastalıkları uzmanı ve” ibaresi ile aynı maddenin ikinci fıkrası yürürlükten kaldırılmıştır.
MADDE 10- Bu Yönetmelik yayımı tarihinde yürürlüğe girer.
MADDE 11- Bu Yönetmelik hükümlerini Sağlık Bakanı yürütür.
"""


def _by_kind(items):
    out = {}
    for a in items:
        out.setdefault(a.change_kind, set()).add(a.article_ref)
    return out


def test_gercek_2022_degisikligi():
    a = analyze(T_2022, B_2022)
    assert a.type == "degisiklik"
    assert a.base.title == "Diyaliz Merkezleri Hakkında Yönetmelik"
    assert (a.base.rg_date, a.base.rg_no) == ("1/3/2019", "30701")
    k = _by_kind(a.amendments)
    assert k["degisti"] == {f"{n}. madde" for n in (4, 8, 9, 15, 22, 25)}
    assert k["eklendi"] == {"9. madde"}
    assert k["yururlukten_kalkti"] == {f"{n}. madde" for n in (4, 8, 21, 26, 27, 29, 37)}


def test_eski_api_uyumu():
    am = extract(T_2022, B_2022)
    assert am and all(set(vars(x)) == {"target_law", "article_ref", "change_kind", "snippet"} for x in am)
    assert am[0].target_law == "Diyaliz Merkezleri Hakkında Yönetmeliği"   # eski target_from_title biçimi
    assert target_from_title("Aile Hekimliği Uygulama Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik") == "Aile Hekimliği Uygulama Yönetmeliği"
    assert extract("Diyaliz Merkezleri Hakkında Yönetmelik", B_2022) == []


def test_alinti_icindeki_sahte_islemler_sayilmaz():
    body = ("MADDE 1- 1/1/2020 tarihli ve 31000 sayılı Resmî Gazete’de yayımlanan Deneme Yönetmeliğinin 3 üncü maddesi aşağıdaki şekilde değiştirilmiştir.\n"
            "“MADDE 3- Bu madde 5 inci maddesi uyarınca değiştirilmiş ve yürürlükten kaldırılmış sayılmaz.”")
    a = analyze("Deneme Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik", body)
    assert [(x.article_ref, x.change_kind) for x in a.amendments] == [("3. madde", "degisti")]


def test_maddeden_sonra_gelmek_uzere():
    body = ("MADDE 1- 16/11/2022 tarihli ve 32015 sayılı Resmî Gazete’de yayımlanan Türkiye Sağlık Enstitüleri Başkanlığı Teşkilat ve Görevleri Hakkında Yönetmeliğe "
            "9 uncu maddeden sonra gelmek üzere aşağıdaki madde eklenmiştir.\n“MADDE 9/A- (1) ...”\nMADDE 2- Bu Yönetmelik yayımı tarihinde yürürlüğe girer.")
    a = analyze("Türkiye Sağlık Enstitüleri Başkanlığı Teşkilat ve Görevleri Hakkında Yönetmelikte Değişiklik Yapılmasına Dair Yönetmelik", body)
    assert [(x.article_ref, x.change_kind) for x in a.amendments] == [("9. madde sonrası", "eklendi")]
    assert a.base.rg_no == "32015"


def test_baslikta_yonetmelik_gecen_hedef():
    body = "MADDE 1- 2/2/2021 tarihli ve 31400 sayılı Resmî Gazete’de yayımlanan Yönetmelik Hazırlama Usul ve Esasları Hakkında Yönetmeliğin 5 inci maddesi yürürlükten kaldırılmıştır."
    a = analyze("Yönetmelik Hazırlama Usul ve Esasları Hakkında Yönetmelikte Değişiklik Yapılmasına Dair Yönetmelik", body)
    assert a.base.title == "Yönetmelik Hazırlama Usul ve Esasları Hakkında Yönetmelik"


def test_yeni_yonetmelik_eskisini_kaldirir():
    body = "MADDE 30- (1) 1/3/2019 tarihli ve 30701 sayılı Resmî Gazete’de yayımlanan Diyaliz Merkezleri Hakkında Yönetmelik yürürlükten kaldırılmıştır.\nMADDE 31- Bu Yönetmelik yayımı tarihinde yürürlüğe girer."
    a = analyze("Diyaliz Merkezleri Hakkında Yönetmelik", body)
    assert a.type == "yeni" and a.amendments == []
    assert [(r.title, r.rg_no) for r in a.repealed] == [("Diyaliz Merkezleri Hakkında Yönetmelik", "30701")]


def test_yurürlükten_kaldirma_basligi():
    a = analyze("Gaziantep Üniversitesi Strateji Uygulama ve Araştırma Merkezi Yönetmeliğinin Yürürlükten Kaldırılmasına Dair Yönetmelik", "")
    assert a.type == "kaldirma"
    assert [r.title for r in a.repealed] == ["Gaziantep Üniversitesi Strateji Uygulama ve Araştırma Merkezi Yönetmelik"]


def test_duz_metin_madde_basligi_olmadan():
    a = analyze("Deneme Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik", "Yönetmeliğin 4 üncü maddesi yürürlükten kaldırılmıştır.")
    assert [(x.article_ref, x.change_kind) for x in a.amendments] == [("4. madde", "yururlukten_kalkti")]


# ---- Gerçek Resmî Gazete metninin biçimi: sabit genişlikte satırlara bölünmüş (UYDURMA içerik, gerçek biçim) ----
WRAPPED = """MADDE l-
3/3/2025
tarihli ve 32830
    sayılı Resmî Gazete’de yayımlanan Örnek Üniversitesi Ön Lisans ve
    Lisans Eğitim-Öğretim ve Sınav Yönetmeliğinin 31 inci maddesinin birinci
    fıkrası aşağıdaki şekilde değiştirilmiştir.
“(1) Başarı harfi; öğrencilerin yarıyıl
    notlarına göre hesaplanır.”
MADDE 2-
Aynı Yönetmeliğin 17
nci
maddesinin on ikinci fıkrası aşağıdaki şekilde değiştirilmiştir.
MADDE 3-
Aynı Yönetmeliğin geçici 1 inci ve geçici 2 nci maddeleri yürürlükten kaldırılmıştır.
MADDE 4-
Aynı Yönetmeliğin 4 üncü ve 5 inci maddeleri yürürlükten kaldırılmıştır.
MADDE 5-
Bu Yönetmelik yayımı tarihinde yürürlüğe girer.
"""


def test_satir_kirilmis_gercek_bicim():
    a = analyze("Örnek Üniversitesi Ön Lisans ve Lisans Eğitim-Öğretim ve Sınav Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik", WRAPPED)
    assert (a.base.title, a.base.rg_date, a.base.rg_no) == (
        "Örnek Üniversitesi Ön Lisans ve Lisans Eğitim-Öğretim ve Sınav Yönetmelik", "3/3/2025", "32830")
    k = _by_kind(a.amendments)
    assert k["degisti"] == {"31. madde", "17. madde"}                  # "MADDE l-" ve "17\nnci\nmaddesinin"
    assert k["yururlukten_kalkti"] == {"Geçici 1. madde", "Geçici 2. madde", "4. madde", "5. madde"}


def test_yeni_yonetmelik_gercek_bicim_kaldirma():
    body = ("MADDE 36-\n(3) Müstakil merkezler, 8/1/2025 tarihli ve 32776 sayılı Resmî Gazete’de yayımlanan Ambulanslar\n"
            "    Hizmetleri Yönetmeliğine uygun olarak ambulans bulundurabilir.\n"
            "Yürürlükten\n    kaldırılan yönetmelik\nMADDE 37-\n(1)\n1/3/2019\ntarihli ve\n    30701 sayılı Resmî Gazete’de yayımlanan Diyaliz Merkezleri Hakkında\n"
            "    Yönetmelik yürürlükten kaldırılmıştır.\nMADDE 38-\nBu Yönetmelik yayımı tarihinde yürürlüğe girer.")
    a = analyze("Diyaliz Merkezleri Hakkında Yönetmelik", body)
    # Ambulans yönetmeliğine yapılan ATIF kaldırma sayılmamalı; yalnız gerçekten kaldırılan alınmalı
    assert [(r.title, r.rg_date, r.rg_no) for r in a.repealed] == [("Diyaliz Merkezleri Hakkında Yönetmelik", "1/3/2019", "30701")]


def test_tebligde_parantez_ve_mukerrer():
    body = ("MADDE 1- 20/2/2025 tarihli ve 32819 sayılı Resmî Gazete’de yayımlanan İthalatta Haksız Rekabetin Önlenmesine İlişkin "
            "Tebliğ (Tebliğ No: 2025/4)’in 4 üncü maddesinin ikinci fıkrasında yer alan tablo aşağıdaki şekilde değiştirilmiştir.")
    a = analyze("İthalatta Haksız Rekabetin Önlenmesine İlişkin Tebliğ (Tebliğ No: 2025/4)’de Değişiklik Yapılmasına Dair Tebliğ", body)
    assert a.base.title == "İthalatta Haksız Rekabetin Önlenmesine İlişkin Tebliğ (Tebliğ No: 2025/4)" and a.base.rg_no == "32819"
    assert [(x.article_ref, x.change_kind) for x in a.amendments] == [("4. madde", "degisti")]
    k = analyze("Toros Üniversitesi X Merkezi Yönetmeliğinin Yürürlükten Kaldırılmasına Dair Yönetmelik",
                "MADDE 1- 28/8/2015 tarihli ve 29459 mükerrer sayılı Resmî Gazete’de yayımlanan Toros Üniversitesi X Merkezi Yönetmeliği yürürlükten kaldırılmıştır.")
    assert [(r.rg_date, r.rg_no) for r in k.repealed] == [("28/8/2015", "29459")]
