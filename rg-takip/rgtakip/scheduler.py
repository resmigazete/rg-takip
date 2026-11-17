"""Her gece 00:05'te (Türkiye saati, UTC+3) sayıyı bekler, işler, brifingi gönderir.
Sunucuda cron olmadan çalışsın diye döngü halinde bekler."""
import logging
import time
from datetime import datetime, timedelta, timezone

from . import briefing, db, fetcher, notify, pipeline

TR = timezone(timedelta(hours=3))  # Türkiye yıl boyu UTC+3
log = logging.getLogger("scheduler")


def seconds_until_next_run(now: datetime, hour=0, minute=5) -> float:
    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


def run_once(d):
    html = fetcher.wait_for_issue(d)
    if not html:
        log.error("Sayı alınamadı: %s", d)
        return
    conn = db.connect()
    log.info("İşlendi: %s", pipeline.process_issue(conn, d, html))
    try:
        notify.send_telegram(briefing.build(conn, d))
    except Exception as e:
        log.warning("Telegram gönderilemedi: %s", e)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        wait = seconds_until_next_run(datetime.now(TR))
        log.info("Sonraki çalıştırmaya %.0f dk var", wait / 60)
        time.sleep(wait)
        run_once(datetime.now(TR).date())


if __name__ == "__main__":
    main()
