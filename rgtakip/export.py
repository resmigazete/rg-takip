"""Veritabanından statik JSON üretir (GitHub Pages için).

  python -m rgtakip.export            # docs/ klasörünü yazar
Çıktı: docs/ (web/ kopyası + config.js statik mod) ve docs/data/*.json
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from . import db, queries

ROOT = Path(__file__).resolve().parent.parent


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def export(out: Path | None = None, web: Path | None = None, conn=None) -> int:
    out = out or ROOT / "docs"
    web = web or ROOT / "web"
    conn = conn or db.connect()
    out.mkdir(parents=True, exist_ok=True)
    for f in web.iterdir():  # uygulama dosyalarını kopyala
        if f.is_file():
            shutil.copy2(f, out / f.name)
    (out / "config.js").write_text('window.RG_MODE="static";\n', encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    day_list = queries.days(conn)
    _write(out / "data" / "days.json", day_list)
    for d in day_list:
        _write(out / "data" / "day" / f"{d['date']}.json", queries.day(conn, d["date"]))
    _write(out / "data" / "search.json", queries.search_index(conn))
    return len(day_list)


if __name__ == "__main__":
    n = export()
    print(f"{n} gün dışa aktarıldı.", file=sys.stderr)
