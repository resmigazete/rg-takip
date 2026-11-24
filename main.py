"""Komut satırı.

  python main.py run                 # bugünü bekle, işle; Telegram'a YALNIZCA atama kararlarını gönder (cron: 00:05)
  python main.py run --date 2026-11-16 --no-wait
  python main.py brief --date 2026-11-16   # yalnızca (tam) brifing metnini yazdır
  python main.py atama --date 2026-11-16   # Telegram'a gidecek atama mesajını yazdır (göndermez)
  python main.py reanalyze [--date 2026-11-10]   # kayıtlı metinlerden madde farkını yeniden hesapla (ağ yok)
"""
import argparse
import logging
import time
from datetime import date, datetime

from rgtakip import briefing, db, fetcher, notify, pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "brief", "atama", "reanalyze"])
    ap.add_argument("--date", help="YYYY-MM-DD (varsayılan: bugün)")
    ap.add_argument("--no-wait", action="store_true", help="yoklamadan tek deneme")
    ap.add_argument("--no-send", action="store_true", help="Telegram'a gönderme")
    ap.add_argument("--force", action="store_true", help="O günün kayıtlarını silip yeniden işle")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    d = datetime.strptime(a.date, "%Y-%m-%d").date() if a.date else date.today()
    conn = db.connect()

    skipped = False
    if a.cmd == "run":
        if a.no_wait:
            html = None
            for deneme in range(1, 5):  # bağlantı zaman aşımına karşı 4 deneme
                try:
                    r = fetcher.get(fetcher.index_url(d))
                    html = r.text if r is not None else None
                    break
                except Exception as e:
                    logging.warning("Sayı alınamadı (deneme %d/4): %s", deneme, type(e).__name__)
                    time.sleep(20 * deneme)
        else:
            html = fetcher.wait_for_issue(d)
        if not html:
            raise SystemExit("Sayı alınamadı.")
        if fetcher.is_no_issue(html):   # resmî tatil: işlenecek sayı yok, iş başarıyla biter
            print("Resmî Gazete bu tarihte yayımlanmamış (resmî tatil):", d.isoformat())
            return
        stats = pipeline.process_issue(conn, d, html, force=a.force)
        print(stats)
        skipped = bool(stats.get("skipped"))   # o gün zaten işlenmişse (tekrarlı zamanlama) brifing yeniden gönderilmez

    if a.cmd in ("run", "reanalyze"):
        # Ağsız ve ucuz: son 45 günün mevzuat kayıtlarını güncel ayrıştırıcıyla yeniden çözümler
        since = a.date if (a.cmd == "reanalyze" and a.date) else date.fromordinal(d.toordinal() - 45).isoformat()
        print("Mevzuat farkı yeniden hesaplandı:", pipeline.reanalyze(conn, since), "kayıt")
    if a.cmd == "reanalyze":
        return

    if a.cmd == "atama":
        print(briefing.build_atamalar(conn, d) or "Bu tarihte atama kararı yok.")
        return

    print(briefing.build(conn, d))            # günlük kaydı (log) için tam brifing
    if a.cmd == "run" and not a.no_send and not skipped:
        atama = briefing.build_atamalar(conn, d)   # Telegram'a yalnızca atamalar gider
        if not atama:
            print("Telegram: bu tarihte atama kararı yok, mesaj gönderilmedi")
        else:
            print("Telegram:", "gönderildi" if notify.send_telegram(atama) else "ayarlı değil")


if __name__ == "__main__":
    main()
