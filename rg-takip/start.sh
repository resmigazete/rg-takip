#!/bin/sh
# Toplayıcı (arka planda) + API/PWA sunucusu
python -m rgtakip.scheduler &
exec python -m uvicorn rgtakip.api:app --host 0.0.0.0 --port ${PORT:-8000}
