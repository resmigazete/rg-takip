import json
from datetime import date
from pathlib import Path

from rgtakip import db, export, pipeline
import test_pipeline as t


def test_export(tmp_path):
    conn = db.connect(":memory:")
    pipeline.process_issue(conn, date(2026, 11, 16), t.INDEX, text_fetcher=lambda u: t.BODIES.get(u, ""))
    out = tmp_path / "docs"
    n = export.export(out=out, web=Path(__file__).resolve().parent.parent / "web", conn=conn)
    assert n == 1
    assert (out / "index.html").exists() and (out / ".nojekyll").exists()
    assert 'RG_MODE="static"' in (out / "config.js").read_text()
    day = json.loads((out / "data/day/2026-11-16.json").read_text(encoding="utf-8"))
    assert len(day["health"]) == 2 and len(day["appointments"]) == 4
    idx = json.loads((out / "data/search.json").read_text(encoding="utf-8"))
    assert any("Rektörlüğüne" in a["institution"] for a in idx["appointments"])
    assert all(i["type"] != "ilan" for i in idx["items"])
