import pytest

from rgtakip import config, notify


class _R:
    def __init__(self, code): self.status_code = code
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("hata")


def _kur(monkeypatch, chat_ids, bad=()):
    gonderilen = []
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", "TOKEN")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", chat_ids)
    def post(url, json, timeout):
        gonderilen.append(json["chat_id"])
        return _R(403 if json["chat_id"] in bad else 200)
    monkeypatch.setattr(notify.requests, "post", post)
    return gonderilen


def test_birden_cok_alici(monkeypatch):
    g = _kur(monkeypatch, "111, 222;-100333  111")          # virgül/noktalı virgül/boşluk, tekrar yok
    assert notify.send_telegram("merhaba") is True
    assert g == ["111", "222", "-100333"]


def test_bir_alici_basarisizsa_digerleri_alir(monkeypatch):
    g = _kur(monkeypatch, "111,222,333", bad={"222"})
    assert notify.send_telegram("merhaba") is True
    assert g == ["111", "222", "333"]


def test_hicbirine_gitmezse_hata(monkeypatch):
    _kur(monkeypatch, "111,222", bad={"111", "222"})
    with pytest.raises(RuntimeError):
        notify.send_telegram("merhaba")


def test_ayarli_degilse_false(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", "")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "111")
    assert notify.send_telegram("x") is False
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", "T")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "")
    assert notify.send_telegram("x") is False
