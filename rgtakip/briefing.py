"""Sabah brifingi metnini üretir (Telegram/e-posta için düz metin)."""
from __future__ import annotations

import sqlite3
from datetime import date

from . import config

TYPE_LABEL = {
    "kanun": "Kanun", "khk": "KHK", "cb_karari": "CB Kararı", "cb_kararname": "CB Kararnamesi",
    "yonetmelik": "Yönetmelik", "teblig": "Tebliğ", "atama": "Atama", "kurul_karari": "Kurul Kararı",
    "genelge": "Genelge", "yonerge": "Yönerge", "yargi": "Yargı", "ilan": "İlan", "diger": "Diğer",
}
ROLE_ICON = {"Vali": "🏛", "Rektör": "🎓"}


def _kompakt(items) -> list[str]:
    on = lambda a: (a["predecessor"] or "").replace("Önceki görev:", "").strip()
    emre = lambda a: a["institution"].lower().endswith("emrine")
    groups = [
        ("Görevden alındı", lambda a: a["action"] == "gorevden_alma"),
        ("Vali atamaları", lambda a: a["new_role"] == "Vali"),
        ("İçişleri Bakanlığı emrine alındı", emre),
        ("Diğer atamalar", lambda a: True),
    ]
    left, out = list(items), []
    for title, f in groups:
        g = [a for a in left if f(a)]
        left = [a for a in left if a not in g]
        if not g:
            continue
        out += ["", f"▪️ {title} ({len(g)})"]
        for a in g:
            if emre(a):
                out.append(f"• {a['person']}" + (f" ({on(a)})" if on(a) else ""))
            else:
                icon = "🩺" if a["is_health"] else "•"
                out.append(f"{icon} {a['institution']}: {a['person']}" + (f" ← {on(a)}" if on(a) else ""))
    return out


def build_atamalar(conn: sqlite3.Connection, d: date) -> str:
    """Telegram için YALNIZCA atama kararları: günün tüm atama/görevden alma kayıtları, karara göre gruplu.
    O gün atama yoksa boş metin döner (Telegram'a hiçbir şey gönderilmez)."""
    rows = conn.execute(
        """SELECT a.*, i.title item_title, i.url item_url FROM appointments a
           JOIN items i ON i.id=a.item_id WHERE i.issue_date=? ORDER BY i.id, a.id""", (d.isoformat(),)).fetchall()
    # Atama kararı var ama okunup ayrıştırılamadıysa sessizce geçme: bağlantıyla uyar (kaçırılmasın)
    has_type = any(r[1] == "doc_type" for r in conn.execute("PRAGMA table_info(items)"))
    unparsed = conn.execute(
        """SELECT title, url FROM items i WHERE i.issue_date=? AND i.doc_type='atama'
           AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a.item_id=i.id) ORDER BY i.id""", (d.isoformat(),)).fetchall() if has_type else []
    if not rows and not unparsed:
        return ""
    groups: dict[str, list] = {}
    for a in rows:
        groups.setdefault(a["item_id"], []).append(a)
    lines = [f"👤 Resmi Gazete – Atama Kararları – {d.strftime('%d.%m.%Y')}"]
    if rows:
        lines.append(f"{len(rows)} kayıt")
    for items in groups.values():
        lines += ["", f"📄 {items[0]['item_title']}", items[0]["item_url"]]
        if len(items) > 8:                       # toplu karar: gruplu, kısa satırlar
            lines += _kompakt(items)
            continue
        for a in items:
            icon = "🩺" if a["is_health"] else ROLE_ICON.get(a["new_role"], "•")
            verb = "görevden alındı" if a["action"] == "gorevden_alma" else "atandı"
            pred = (f" ({a['predecessor'] if a['predecessor'].startswith('Önceki görev:') else 'yerine: ' + a['predecessor']})"
                if a["predecessor"] else "")
            lines.append(f"{icon} {a['institution']}: {a['person']} {verb}{pred}")
    for u in unparsed:
        lines += ["", f"⚠️ Otomatik okunamadı, bağlantıdan bakın:", f"📄 {u['title']}", u["url"]]
    return "\n".join(lines)


def build(conn: sqlite3.Connection, d: date, min_importance: int | None = None) -> str:
    mi = config.MIN_IMPORTANCE if min_importance is None else min_importance
    iso = d.isoformat()
    lines = [f"📰 Resmi Gazete – {d.strftime('%d.%m.%Y')}"]

    health = conn.execute(
        """SELECT * FROM items WHERE issue_date=? AND is_health=1 AND doc_type!='atama'
           AND importance>=? ORDER BY importance DESC""", (iso, mi)).fetchall()
    lines.append("")
    lines.append(f"🩺 Sağlık ({len(health)})")
    if not health:
        lines.append("• Bugün öne çıkan sağlık düzenlemesi yok.")
    for r in health[:12]:
        lines.append(f"• [{TYPE_LABEL.get(r['doc_type'], 'Diğer')}] {r['title']}\n  {r['url']}")
        ams = conn.execute("SELECT article_ref, change_kind FROM amendments WHERE item_id=? LIMIT 6", (r["id"],)).fetchall()
        if ams:
            kind = {"degisti": "değişti", "eklendi": "eklendi", "yururlukten_kalkti": "kaldırıldı"}
            lines.append("  Değişen: " + ", ".join(f"{a['article_ref']} ({kind.get(a['change_kind'], '')})" for a in ams))

    # Önemli atamalar: vali, rektör vb. ve sağlık kurumları
    apps = conn.execute(
        """SELECT a.*, i.url FROM appointments a JOIN items i ON i.id=a.item_id
           WHERE i.issue_date=? AND (a.is_key_role=1 OR a.is_health=1)
           ORDER BY a.is_health DESC, a.is_key_role DESC""", (iso,)).fetchall()
    lines.append("")
    lines.append(f"👤 Önemli atamalar ({len(apps)})")
    if not apps:
        lines.append("• Öne çıkan atama yok.")
    for a in apps[:25]:
        icon = ROLE_ICON.get(a["new_role"], "•")
        verb = "görevden alındı" if a["action"] == "gorevden_alma" else "atandı"
        pred = (f" ({a['predecessor'] if a['predecessor'].startswith('Önceki görev:') else 'yerine: ' + a['predecessor']})"
                if a["predecessor"] else "")
        lines.append(f"{icon} {a['institution']}: {a['person']} {verb}{pred}")
    return "\n".join(lines)
