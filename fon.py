"""TEFAS fund data.

Funds come over plain HTTP rather than the websocket the equity endpoints use,
so they are markedly faster and don't hit the concurrency ceiling that forced
`borsa_limit` on the stock side. They still go through `guarded` so one busy
page can't starve the rest of the app.
"""
import logging
import time

import borsapy as bp

from borsa_limit import guarded, guarded_bulk

_log = logging.getLogger(__name__)

LIST_TTL = 1800        # the screener moves slowly; funds price once a day
DETAY_TTL = 900
MAX_DETAY = 40

FUND_TYPES = {"YAT": "Yatırım Fonları", "EMK": "Emeklilik Fonları"}

_liste_cache = {}
_detay_cache = {}


def _cache_put(cache, key, data, now, ttl, cap):
    for k in [k for k, v in cache.items() if now - v["time"] >= ttl]:
        cache.pop(k, None)
    while len(cache) >= cap:
        cache.pop(min(cache, key=lambda k: cache[k]["time"]), None)
    cache[key] = {"data": data, "time": now}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else round(f, 2)      # f != f filters NaN


def fon_listesi(fund_type="YAT", limit=500):
    """Screener rows for the list page: code, name, type and period returns."""
    key = (fund_type, limit)
    now = time.time()
    hit = _liste_cache.get(key)
    if hit and now - hit["time"] < LIST_TTL:
        return hit["data"]

    try:
        df = guarded_bulk(bp.screen_funds, fund_type=fund_type, limit=limit)
    except Exception as e:
        _log.warning("Fund screener failed (%s): %s", fund_type, e)
        return hit["data"] if hit else []

    rows = []
    for r in df.to_dict("records"):
        rows.append({
            "code": r.get("fund_code", ""),
            "name": (r.get("name") or "").strip(),
            "type": (r.get("fund_type") or "").replace(" Şemsiye Fonu", "").strip(),
            "r1m": _num(r.get("return_1m")),
            "r6m": _num(r.get("return_6m")),
            "rytd": _num(r.get("return_ytd")),
            "r1y": _num(r.get("return_1y")),
        })
    _cache_put(_liste_cache, key, rows, now, LIST_TTL, 4)
    return rows


def fon_detay(kod):
    """Everything the fund page shows, with each upstream call isolated so one
    missing section never blanks the page."""
    kod = kod.upper()
    now = time.time()
    hit = _detay_cache.get(kod)
    if hit and now - hit["time"] < DETAY_TTL:
        return hit["data"]

    result = {"kod": kod, "info": None, "performance": None,
              "risk": None, "fee": None, "hata": None}
    try:
        f = guarded(bp.Fund, kod)
        info = guarded(lambda: f.info)
        if not info or not info.get("name"):
            raise ValueError("no fund data")
        result["info"] = info
    except Exception as e:
        _log.warning("Fund %s failed: %s: %s", kod, type(e).__name__, e)
        result["hata"] = f"'{kod}' için veri alınamadı."
        return result

    # borsapy exposes some of these as properties and others as methods, so
    # resolve whichever it turns out to be instead of guessing per field.
    def _resolve(name):
        v = getattr(f, name)
        return v() if callable(v) else v

    for field, attr in (("performance", "performance"),
                        ("risk", "risk_metrics"),
                        ("fee", "management_fee")):
        try:
            result[field] = guarded(_resolve, attr)
        except Exception as e:
            _log.warning("Fund %s %s failed: %s", kod, field, e)

    _cache_put(_detay_cache, kod, result, now, DETAY_TTL, MAX_DETAY)
    return result


def fon_gecmis(kod, start=None):
    """Price / fund size / investor count series for the chart."""
    f = guarded(bp.Fund, kod.upper())
    return guarded(f.history, start=start) if start else guarded(f.history)
