from datetime import date

from rgtakip import briefing, db, pipeline
import test_pipeline as t


def _conn():
    conn = db.connect(":memory:")
    pipeline.process_issue(conn, date(2026, 11, 16), t.INDEX, text_fetcher=lambda u: t.BODIES.get(u, ""))
    return conn


def test_yalniz_atamalar_gruplu():
    msg = briefing.build_atamalar(_conn(), date(2026, 11, 16))
    n = _conn().execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    assert msg.startswith("👤 Resmi Gazete – Atama Kararları – 16.11.2026")
    assert f"{n} kayıt" in msg and n >= 4
    assert "http" in msg                                   # karar bağlantısı
    assert "atandı" in msg or "görevden alındı" in msg
    # sağlık düzenlemesi / yönetmelik satırları Telegram mesajına karışmaz
    assert "Yönetmelik" not in msg and "Sağlık (" not in msg


def test_atama_yoksa_bos():
    conn = db.connect(":memory:")
    assert briefing.build_atamalar(conn, date(2026, 11, 16)) == ""
    pipeline.process_issue(conn, date(2026, 11, 16), t.INDEX, text_fetcher=lambda u: t.BODIES.get(u, ""))
    assert briefing.build_atamalar(conn, date(2026, 11, 15)) == ""   # başka güne ait atama gelmez
