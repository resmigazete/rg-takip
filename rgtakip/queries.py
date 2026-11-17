"""API ve statik dışa aktarım için ortak sorgular (saf fonksiyonlar, dict döndürür)."""
from __future__ import annotations

import sqlite3

from . import briefing


def item_dict(r) -> dict:
    return {"id": r["id"], "date": r["issue_date"], "type": r["doc_type"],
            "type_label": briefing.TYPE_LABEL.get(r["doc_type"], "Diğer"),
            "title": r["title"], "issuer": r["issuer"] or "", "url": r["url"], "importance": r["importance"],
            "categories": [c for c in (r["categories"] or "").split(",") if c]}


def days(conn: sqlite3.Connection, limit: int = 400) -> list[dict]:
    rows = conn.execute(
        """SELECT issue_date d, COUNT(*) n, SUM(is_health) h FROM items
           GROUP BY issue_date ORDER BY issue_date DESC LIMIT ?""", (limit,)).fetchall()
    return [{"date": r["d"], "items": r["n"], "health": r["h"] or 0} for r in rows]


def day(conn: sqlite3.Connection, d: str) -> dict:
    health = [item_dict(r) for r in conn.execute(
        "SELECT * FROM items WHERE issue_date=? AND is_health=1 AND doc_type!='atama' ORDER BY importance DESC", (d,))]
    for h in health:
        h["amendments"] = [dict(a) for a in conn.execute(
            "SELECT target_law, article_ref, change_kind FROM amendments WHERE item_id=?", (h["id"],))]
    apps = [dict(a) for a in conn.execute(
        """SELECT a.person, a.new_role, a.institution, a.predecessor, a.action,
                  a.is_key_role, a.is_health, i.url
           FROM appointments a JOIN items i ON i.id=a.item_id
           WHERE i.issue_date=? ORDER BY a.is_health DESC, a.is_key_role DESC""", (d,))]
    others = [item_dict(r) for r in conn.execute(
        """SELECT * FROM items WHERE issue_date=? AND is_health=0 AND doc_type!='ilan'
           ORDER BY importance DESC, id LIMIT 100""", (d,))]
    return {"date": d, "health": health, "appointments": apps, "others": others}


def search(conn: sqlite3.Connection, q: str) -> dict:
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    rows = conn.execute(
        """SELECT * FROM items WHERE title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\'
           ORDER BY issue_date DESC LIMIT 50""", (like, like)).fetchall()
    people = [dict(a) for a in conn.execute(
        """SELECT a.person, a.new_role, a.institution, a.action, i.issue_date date, i.url
           FROM appointments a JOIN items i ON i.id=a.item_id
           WHERE a.person LIKE ? ESCAPE '\\' OR a.institution LIKE ? ESCAPE '\\'
           ORDER BY i.issue_date DESC LIMIT 50""", (like, like))]
    return {"items": [item_dict(r) for r in rows], "appointments": people}


def search_index(conn: sqlite3.Connection, limit_items: int = 6000) -> dict:
    """Tarayıcıda arama için hafif dizin (sağlıkla ilgili olmayan ilanlar yok, gövde yok, yalnızca başlık/kişi/kurum)."""
    items = [item_dict(r) for r in conn.execute(
        "SELECT * FROM items WHERE doc_type!='ilan' OR is_health=1 ORDER BY issue_date DESC, id DESC LIMIT ?", (limit_items,))]
    for i in items:
        i.pop("categories", None)
        i.pop("id", None)
    people = [dict(a) for a in conn.execute(
        """SELECT a.person, a.new_role, a.institution, a.action, i.issue_date date, i.url
           FROM appointments a JOIN items i ON i.id=a.item_id ORDER BY i.issue_date DESC""")]
    return {"items": items, "appointments": people}
