"""Uçtan uca akış: sayı -> ilanlar -> sınıflandır -> atama/değişiklik -> kaydet."""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import date
from typing import Callable

from . import amendments, appointments, classifier, fetcher, ilanlar, parser

log = logging.getLogger(__name__)

LEGAL_TYPES = ("yonetmelik", "teblig", "kanun", "khk", "cb_kararname")


def store_legal(conn: sqlite3.Connection, item_id: int, title: str, body: str) -> None:
    """Bir mevzuat kaydının madde işlemlerini ve değiştirilen/kaldırılan mevzuatını (yeniden) yazar.
    Tekrar çalıştırılabilir: önce o kaydın eski satırlarını siler."""
    conn.execute("DELETE FROM amendments WHERE item_id=?", (item_id,))
    conn.execute("DELETE FROM law_refs WHERE item_id=?", (item_id,))
    an = amendments.analyze(title, body or "")
    for am in an.amendments:
        conn.execute(
            "INSERT INTO amendments(item_id,target_law,article_ref,change_kind,snippet) VALUES (?,?,?,?,?)",
            (item_id, am.target_law, am.article_ref, am.change_kind, am.snippet))
    refs = [("repealed", r) for r in an.repealed]
    if an.base and (body or "").strip():          # gövde yoksa "değiştirildi" demek için dayanak yok
        refs.insert(0, ("base", an.base))
    for role, ref in refs:
        conn.execute("INSERT INTO law_refs(item_id,role,title,rg_date,rg_no) VALUES (?,?,?,?,?)",
                     (item_id, role, ref.title, ref.rg_date, ref.rg_no))


def reanalyze(conn: sqlite3.Connection, since: str | None = None) -> int:
    """Kayıtlı gövdelerden madde farkını yeniden hesaplar (ağ gerekmez). since: 'YYYY-MM-DD' (dahil)."""
    rows = conn.execute(
        f"SELECT id, title, body FROM items WHERE doc_type IN ({','.join('?' * len(LEGAL_TYPES))}) "
        "AND (? IS NULL OR issue_date >= ?)", (*LEGAL_TYPES, since, since)).fetchall()
    for r in rows:
        store_legal(conn, r["id"], r["title"], r["body"] or "")
    conn.commit()
    return len(rows)


def process_issue(conn: sqlite3.Connection, d: date, index_html: str,
                  text_fetcher: Callable[[str], str] = fetcher.fetch_item_text,
                  kind: str = "normal", fetch_bodies_for: str = "relevant",
                  force: bool = False,
                  html_fetcher: Callable[[str], str] = ilanlar.fetch_html) -> dict:
    """fetch_bodies_for: 'relevant' = yalnızca başlıkta sağlık/atama ipucu olanların metnini çek,
    'all' = hepsi. İlanlar yalnızca başlığı sağlıkla ilgiliyse çekilir."""
    iso = d.isoformat()
    ih = fetcher.sha(index_html)
    if force:
        conn.execute("DELETE FROM amendments WHERE item_id IN (SELECT id FROM items WHERE issue_date=?)", (iso,))
        conn.execute("DELETE FROM law_refs WHERE item_id IN (SELECT id FROM items WHERE issue_date=?)", (iso,))
        conn.execute("DELETE FROM appointments WHERE item_id IN (SELECT id FROM items WHERE issue_date=?)", (iso,))
        conn.execute("DELETE FROM items WHERE issue_date=?", (iso,))
        conn.execute("DELETE FROM issues WHERE date=? AND kind=?", (iso, kind))
    row = conn.execute("SELECT index_hash FROM issues WHERE date=? AND kind=?", (iso, kind)).fetchone()
    has_items = conn.execute("SELECT COUNT(*) FROM items WHERE issue_date=?", (iso,)).fetchone()[0] > 0
    if row and row["index_hash"] == ih and has_items:
        log.info("Sayı değişmemiş ve kayıtlı, atlanıyor.")
        return {"new": 0, "health": 0, "skipped": True}
    conn.execute("INSERT OR REPLACE INTO issues(date, kind, index_hash) VALUES (?,?,?)", (iso, kind, ih))

    stats = {"new": 0, "health": 0, "skipped": False}
    for it in parser.parse_index(index_html):
        if conn.execute("SELECT 1 FROM items WHERE url=?", (it.url,)).fetchone():
            continue

        title_cls = classifier.classify(it.title, "", it.doc_type)
        need_body = (
            fetch_bodies_for == "all"
            or it.doc_type in ("atama", "yonetmelik", "teblig", "kanun", "khk", "cb_karari", "cb_kararname", "kurul_karari")
            or title_cls.health_score >= 15
        )
        # İlanlar: yalnızca başlığı sağlıkla ilgiliyse ("Sağlık Bakanlığı ... ilanı") metni çek
        if it.doc_type == "ilan":
            need_body = (title_cls.is_health or classifier.is_university_issuer(it.title)) \
                and not re.search(r"main\.aspx|eskiilanlar", it.url)
        body = ""
        if need_body:
            try:
                body = text_fetcher(it.url)
            except Exception as e:  # tek ilan hatası tüm akışı durdurmasın
                log.warning("Metin alınamadı %s: %s", it.url, e)

        res = classifier.classify(it.title, body, it.doc_type)
        cur = conn.execute(
            """INSERT INTO items(issue_date,url,section,doc_type,title,issuer,body,is_health,
                                 health_score,importance,categories)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (iso, it.url, it.section, it.doc_type, it.title, res.issuer, body, int(res.is_health),
             res.health_score, res.importance, ",".join(res.categories)))
        item_id = cur.lastrowid
        stats["new"] += 1
        stats["health"] += int(res.is_health)

        # İlan kategori sayfası (Çeşitli / İhale): içindeki ilanları tek tek ekle
        if ilanlar.is_listing(it.title, it.doc_type):
            sub = ilanlar.expand(conn, iso, it.title, it.url, html_fetcher, text_fetcher)
            stats["new"] += sub["new"]
            stats["health"] += sub["health"]

        if it.doc_type == "atama" or "atama" in it.title.lower():
            for a in appointments.extract(body or it.title):
                conn.execute(
                    """INSERT INTO appointments(item_id,person,new_role,institution,predecessor,
                                                action,is_key_role,is_health,raw)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (item_id, a.person, a.new_role, a.institution, a.predecessor, a.action,
                     int(a.is_key_role), int(a.is_health), a.raw))
        if it.doc_type in LEGAL_TYPES:
            store_legal(conn, item_id, it.title, body)
    conn.commit()
    return stats
