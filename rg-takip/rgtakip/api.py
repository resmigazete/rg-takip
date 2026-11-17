"""Telefon uygulaması için JSON API + statik PWA sunucusu (Starlette).

Çalıştır:  RG_API_TOKEN=gizli uvicorn rgtakip.api:app --host 0.0.0.0 --port 8000
Token ayarlıysa /api/* uçları `Authorization: Bearer <token>` ister.
"""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import db, queries

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
TOKEN = os.environ.get("RG_API_TOKEN", "")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _conn():
    return db.connect()


def _authorized(request) -> bool:
    if not TOKEN:
        return True
    h = request.headers.get("authorization", "")
    return h == f"Bearer {TOKEN}" or request.query_params.get("token") == TOKEN


def guarded(fn):
    async def wrapper(request):
        if not _authorized(request):
            return JSONResponse({"error": "yetkisiz"}, status_code=401)
        return await fn(request)
    return wrapper


@guarded
async def days(request):
    return JSONResponse(queries.days(_conn(), 60))


@guarded
async def day(request):
    d = request.path_params["d"]
    if not DATE_RE.match(d):
        return JSONResponse({"error": "tarih biçimi YYYY-AA-GG olmalı"}, status_code=400)
    return JSONResponse(queries.day(_conn(), d))


@guarded
async def search(request):
    q = (request.query_params.get("q") or "").strip()
    if len(q) < 2:
        return JSONResponse({"items": [], "appointments": []})
    return JSONResponse(queries.search(_conn(), q))


async def healthz(request):
    return JSONResponse({"ok": True, "today": date.today().isoformat()})


app = Starlette(routes=[
    Route("/healthz", healthz),
    Route("/api/days", days),
    Route("/api/day/{d}", day),
    Route("/api/search", search),
    Mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web"),
])
