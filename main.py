"""Komut satırı.

  python main.py run                 # bugünü bekle, işle, brifingi gönder (cron: 00:05)
  python main.py run --date 2026-11-16 --no-wait
  python main.py brief --date 2026-11-16   # yalnızca brifing metnini yazdır
"""
import argparse
import logging
from datetime import date, datetime

from rgtakip import briefing, db, fetcher, notify, pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "brief"])
    ap.add_argument("--date", help="YYYY-MM-DD (varsayılan: bugün)")
    ap.add_argument("--no-wait", action="store_true", help="yoklamadan tek deneme")
    ap.add_argument("--no-send", action="store_true", help="Telegram'a gönderme")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    d = datetime.strptime(a.date, "%Y-%m-%d").date() if a.date else date.today()
    conn = db.connect()

    if a.cmd == "run":
        if a.no_wait:
            r = fetcher.get(fetcher.index_url(d))
            html = r.text if r is not None else None
        else:
            html = fetcher.wait_for_issue(d)
        if not html:
            raise SystemExit("Sayı alınamadı.")
        print(pipeline.process_issue(conn, d, html))

    text = briefing.build(conn, d)
    print(text)
    if a.cmd == "run" and not a.no_send:
        print("Telegram:", "gönderildi" if notify.send_telegram(text) else "ayarlı değil")


if __name__ == "__main__":
    main()
