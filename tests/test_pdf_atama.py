import io
from datetime import date

from rgtakip import briefing, db, fetcher

BASLIK = "ATAMA KARARLARI Cumhurbaşkanlığından: Karar: 2026/400 26 Kasım 2026 Recep Tayyip ERDOĞAN CUMHURBAŞKANI " * 9
GOVDE = ("Adli Tıp Kurumu Başkanlığı Grup Başkanlığına Ankara Adli Tıp Grup Başkanı Ali VELİ atanmıştır. " * 12)


class _Sayfa:
    def __init__(self, t): self._t = t
    def extract_text(self): return self._t


def _sahte_pdf(monkeypatch, metin_katmani, sayfa, ocr_metni):
    import pypdf
    class R:
        def __init__(self, *_a, **_k): self.pages = [_Sayfa(metin_katmani if i == 0 else "") for i in range(sayfa)]
    monkeypatch.setattr(pypdf, "PdfReader", R)
    cagrildi = []
    monkeypatch.setattr(fetcher, "ocr_pdf", lambda data, max_pages=12: (cagrildi.append(1), ocr_metni)[1])
    return cagrildi


def test_yalniz_baslik_metin_katmani_ocr_tetikler(monkeypatch):
    """27.11 hatası: metin katmanında yalnızca başlıklar var (tekrarlı 'Karar' _pdf_garbled'ı yanıltıyordu)."""
    assert not fetcher._pdf_garbled(BASLIK)                 # eski kontrol bunu 'sağlam' sayıyordu
    c = _sahte_pdf(monkeypatch, BASLIK, 9, BASLIK + GOVDE)
    out = fetcher.pdf_to_text(b"x")
    assert c and "Adli Tıp" in out and "atanmıştır" in out


def test_dolu_metin_katmaninda_ocr_yok(monkeypatch):
    dolu = "Bu bir ilan metnidir ve karar gereğince bir olarak maddesi hakkında atanmıştır. " * 80
    c = _sahte_pdf(monkeypatch, dolu, 1, "OCR")
    assert "ilan metnidir" in fetcher.pdf_to_text(b"x") and not c


def test_okunamayan_atama_karari_uyari_verir():
    conn = db.connect(":memory:")
    conn.execute("INSERT INTO items(issue_date,url,doc_type,title,issuer) VALUES (?,?,?,?,?)",
                 ("2026-11-27", "https://www.resmigazete.gov.tr/x.pdf", "atama", "Cumhurbaşkanlığı Tarafından Yapılan Atamalar Hakkında Kararlar", ""))
    msg = briefing.build_atamalar(conn, date(2026, 11, 27))
    assert "⚠️" in msg and "x.pdf" in msg                    # sessiz kalmaz
    assert briefing.build_atamalar(conn, date(2026, 11, 26)) == ""
