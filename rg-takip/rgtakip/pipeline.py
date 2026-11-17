"""Uçtan uca akış: sayı -> ilanlar -> sınıflandır -> atama/değişiklik -> kaydet."""
from __future__ import annotations

import logging
import sqlite3
from datetime import date
from typing import Callable

from . import amendments, appointments, classifier, fetcher, parser

log = logging.getLogger(__name__)


def process_issue(conn: sqlite3.Connection, d: date, index_html: str,
                  text_fetcher: Callable[[str], str] = fetcher.fetch_item_text,
                  kind: str = "normal", fetch_bodies_for: str = "relevant") -> dict:
    """fetch_bodies_for: 'relevant' = yalnızca başlıkta sağlık/atama ipucu olanların metnini çek,
    'all' = hepsi. Tüm ilanları çekmek yavaştır; ilan türü 'ilan' olanlar atlanır."""
    iso = d.isoformat()
    ih = fetcher.sha(index_html)
    row = conn.execute("SELECT index_hash FROM issues WHERE date=? AND kind=?", (iso, kind)).fetchone()
    if row and row["index_hash"] == ih:
        log.info("Sayı değişmemiş, atlanıyor.")
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
        ) and it.doc_type != "ilan"
        body = ""
        if need_body:
            try:
                body = text_fetcher(it.url)
            except Exception as e:  # tek ilan hatası tüm akışı durdurmasın
                log.warning("Metin alınamadı %s: %s", it.url, e)

        res = classifier.classify(it.title, body, it.doc_type)
        cur = conn.execute(
            """INSERT INTO items(issue_date,url,section,doc_type,title,body,is_health,
                                 health_score,importance,categories)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (iso, it.url, it.section, it.doc_type, it.title, body, int(res.is_health),
             res.health_score, res.importance, ",".join(res.categories)))
        item_id = cur.lastrowid
        stats["new"] += 1
        stats["health"] += int(res.is_health)

        if it.doc_type == "atama" or "atama" in it.title.lower():
            for a in appointments.extract(body or it.title):
                conn.execute(
                    """INSERT INTO appointments(item_id,person,new_role,institution,predecessor,
                                                action,is_key_role,is_health,raw)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (item_id, a.person, a.new_role, a.institution, a.predecessor, a.action,
                     int(a.is_key_role), int(a.is_health), a.raw))
        if it.doc_type in ("yonetmelik", "teblig", "kanun", "khk", "cb_kararname") and body:
            for am in amendments.extract(it.title, body):
                conn.execute(
                    "INSERT INTO amendments(item_id,target_law,article_ref,change_kind,snippet) VALUES (?,?,?,?,?)",
                    (item_id, am.target_law, am.article_ref, am.change_kind, am.snippet))
    conn.commit()
    return stats
