import requests
import time
from concurrent.futures import ThreadPoolExecutor

_rates_cache = {"data": None, "time": 0}
CACHE_TTL = 300


def _fetch_tcmb():
    from xml.etree import ElementTree as ET
    r = requests.get("https://www.tcmb.gov.tr/kurlar/today.xml", timeout=5)
    root = ET.fromstring(r.content)
    out = {}
    for cur in root.findall(".//Currency"):
        code = cur.get("Kod")
        if code in ("USD", "EUR"):
            buy = cur.find("ForexBuying")
            sell = cur.find("ForexSelling")
            bval = float(buy.text) if buy is not None and buy.text else 0
            sval = float(sell.text) if sell is not None and sell.text else 0
            out[code] = round((bval + sval) / 2, 4)
    return out


def _fetch_metals():
    headers = {"User-Agent": "Mozilla/5.0"}
    out = {}
    for sym, key in [("GC=F", "XAU"), ("SI=F", "XAG")]:
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d",
                headers=headers, timeout=5,
            )
            if r.status_code == 200:
                meta = r.json()["chart"]["result"][0]["meta"]
                out[key] = meta["regularMarketPrice"]
        except Exception:
            pass
    return out


def get_rates():
    now = time.time()
    if _rates_cache["data"] and (now - _rates_cache["time"]) < CACHE_TTL:
        return _rates_cache["data"]

    rates = []
    tcmb = {}
    metals = {}

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_fetch_tcmb)
        f2 = pool.submit(_fetch_metals)
        try:
            tcmb = f1.result(timeout=10)
        except Exception:
            pass
        try:
            metals = f2.result(timeout=10)
        except Exception:
            pass

    usd_try = tcmb.get("USD", 0)
    eur_try = tcmb.get("EUR", 0)

    if usd_try:
        rates.append({"symbol": "USD/TRY", "price": f"{usd_try:.2f}", "unit": "₺"})
    if eur_try:
        rates.append({"symbol": "EUR/TRY", "price": f"{eur_try:.2f}", "unit": "₺"})

    xau_usd = metals.get("XAU", 0)
    xag_usd = metals.get("XAG", 0)
    if xau_usd:
        gram_try = round((xau_usd / 31.1035) * usd_try, 2) if usd_try else 0
        rates.append({"symbol": "Altın", "price": f"{gram_try:.2f}", "unit": "₺/g"})
    if xag_usd:
        gram_try = round((xag_usd / 31.1035) * usd_try, 2) if usd_try else 0
        rates.append({"symbol": "Gümüş", "price": f"{gram_try:.2f}", "unit": "₺/g"})

    _rates_cache["data"] = rates
    _rates_cache["time"] = now
    return rates
