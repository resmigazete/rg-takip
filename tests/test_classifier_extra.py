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
