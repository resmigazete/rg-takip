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
        pred = f" (yerine: {a['predecessor']})" if a["predecessor"] else ""
        lines.append(f"{icon} {a['institution']}: {a['person']} {verb}{pred}")
    return "\n".join(lines)
