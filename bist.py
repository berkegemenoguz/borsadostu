import borsapy as bp
import pandas as pd
import time
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from graphicgenerator import grafik_ciz_html


TICKER_SYMBOLS = ["THYAO", "TUPRS", "ASELS", "GARAN", "EREGL", "KCHOL", "AKBNK", "SASA", "BIMAS", "SAHOL",
                  "SISE", "FROTO", "TCELL", "PGSUS", "TOASO"]
TOP_MOVERS_SYMBOLS = [
    "THYAO", "TUPRS", "ASELS", "GARAN", "EREGL", "KCHOL", "AKBNK", "SASA",
    "BIMAS", "SAHOL", "SISE", "TOASO", "FROTO", "PETKM", "TCELL", "ENKAI",
    "TAVHL", "HEKTS", "KOZAL", "KOZAA", "PGSUS", "VESTL", "ARCLK", "MGROS",
    "TKFEN", "TTKOM", "AEFES", "DOHOL", "EKGYO", "ISCTR",
]
_ticker_cache = {"data": [], "time": 0}
_movers_cache = {"data": [], "time": 0}
CACHE_TTL = 300
_detay_cache = {}
_mcap_cache = {}


def _fetch_one(sym):
    for attempt in range(2):
        try:
            info = bp.Ticker(sym).info
            info.get("last")
            return {"symbol": sym, "price": f"{info.get('last', 0):.2f}",
                    "change": info.get("change_percent", 0),
                    "pos": info.get("change_percent", 0) >= 0}
        except Exception:
            if attempt == 0:
                time.sleep(0.5)
    return None


def bist_ticker_veri():
    now = time.time()
    if _ticker_cache["data"] and (now - _ticker_cache["time"]) < CACHE_TTL:
        return _ticker_cache["data"]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(_fetch_one, TICKER_SYMBOLS))
    items = [r for r in results if r]

    # if most symbols failed (upstream throttling), keep the previous good data
    # rather than locking a thin ticker in for the full cache window
    if len(items) < len(TICKER_SYMBOLS) * 0.6:
        if len(_ticker_cache["data"]) > len(items):
            return _ticker_cache["data"]
        _ticker_cache["data"] = items
        _ticker_cache["time"] = now - CACHE_TTL + 30  # retry in ~30s
        return items

    _ticker_cache["data"] = items
    _ticker_cache["time"] = now
    return items


def _spark_points(closes, width=60, height=20, pad=2):
    lo, hi = min(closes), max(closes)
    span = (hi - lo) or 1
    n = len(closes) - 1 or 1
    pts = []
    for i, c in enumerate(closes):
        x = pad + (i / n) * (width - 2 * pad)
        y = (height - pad) - ((c - lo) / span) * (height - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _fetch_weekly_change(sym):
    try:
        t = bp.Ticker(sym)
        df = t.history(period="5g", interval="1d")
        if df.empty or len(df) < 2:
            return None
        closes = df["Close"].tolist()
        first_close = closes[0]
        last_close = closes[-1]
        change = ((last_close - first_close) / first_close) * 100
        volume = float(df["Volume"].iloc[-1]) if "Volume" in df else 0
        return {
            "symbol": sym,
            "price": f"{last_close:.2f}",
            "change": round(change, 2),
            "pos": change >= 0,
            "spark": _spark_points(closes),
            "volume": volume,
            "volume_str": _format_volume(volume),
        }
    except Exception:
        return None


def _format_volume(v):
    if v >= 1e9:
        return f"{v / 1e9:.1f}B"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"


def bist_top_movers():
    now = time.time()
    if _movers_cache["data"] and (now - _movers_cache["time"]) < CACHE_TTL:
        return _movers_cache["data"]
    with ThreadPoolExecutor(max_workers=15) as pool:
        results = list(pool.map(_fetch_weekly_change, TOP_MOVERS_SYMBOLS))
    items = [r for r in results if r]
    items.sort(key=lambda x: x["change"], reverse=True)
    most_active = sorted(items, key=lambda x: x["volume"], reverse=True)[:8]
    data = {"gainers": items[:8], "losers": items[-8:][::-1], "active": most_active}
    _movers_cache["data"] = data
    _movers_cache["time"] = now
    return data


_xu100_cache = {"data": None, "time": 0}


def bist_xu100():
    now = time.time()
    if _xu100_cache["data"] and (now - _xu100_cache["time"]) < CACHE_TTL:
        return _xu100_cache["data"]
    try:
        t = bp.Ticker("XU100")
        info = t.info
        df = t.history(period="5g", interval="1h")
        closes = df["Close"].tolist() if not df.empty else []
        data = {
            "value": f"{info.get('last', 0):,.2f}",
            "change": info.get("change_percent", 0),
            "pos": info.get("change_percent", 0) >= 0,
            "high": f"{info.get('high', 0):,.2f}",
            "low": f"{info.get('low', 0):,.2f}",
            "spark": _spark_points(closes, width=200, height=40) if closes else "",
        }
        _xu100_cache["data"] = data
        _xu100_cache["time"] = now
        return data
    except Exception:
        return None


_sirket_cache = {"data": None, "time": 0}
SIRKET_TTL = 3600  # şirket listesi neredeyse hiç değişmez → 1 saat cache


def bist_sirketler():
    now = time.time()
    if _sirket_cache["data"] is not None and (now - _sirket_cache["time"]) < SIRKET_TTL:
        return _sirket_cache["data"]
    sirketler = bp.companies()
    df = pd.DataFrame(sirketler)
    _sirket_cache["data"] = df
    _sirket_cache["time"] = now
    return df


def bist_detay_veri(sembol):
    now = time.time()
    cached = _detay_cache.get(sembol)
    if cached and (now - cached["time"]) < CACHE_TTL:
        return cached["data"]

    result = {"info": None, "fast_info": None, "history": pd.DataFrame(), "hata": None}
    try:
        ticker = bp.Ticker(sembol)
    except Exception:
        result["hata"] = f"'{sembol}' için veri alınamadı."
        return result

    try:
        info = ticker.info
        info.get("last")  # force the lazy load; raises here if the ticker has no data
        result["info"] = info
    except Exception:
        result["info"] = None
        result["hata"] = f"'{sembol}' için veri alınamadı."
        return result

    try:
        result["fast_info"] = ticker.fast_info
    except Exception:
        pass

    # Every lazy field below triggers its own upstream call (netDebt alone is
    # ~5s), and the template touches them all while rendering. Warm them up
    # front and in parallel so the page pays the slowest one, not their sum.
    def _warm(fn):
        try:
            fn()
        except Exception:
            pass

    # Only the quote group (last/change/volume/open/high/low - one upstream call)
    # and the history are on the page's critical path. The fundamentals each cost
    # a separate 2-6s call and are loaded afterwards via bist_fundamentals().
    info = result["info"]
    warmers = [
        lambda: info and info.get("last"),
        lambda: result.__setitem__("history", ticker.history(period="5g", interval="1h")),
    ]
    with ThreadPoolExecutor(max_workers=len(warmers)) as pool:
        list(pool.map(_warm, warmers))

    _detay_cache[sembol] = {"data": result, "time": now}
    return result


def _fmt_big(v, suffix="TL"):
    if v is None:
        return None
    a = abs(v)
    if a >= 1e12:
        return f"{v / 1e12:.1f}T {suffix}"
    if a >= 1e9:
        return f"{v / 1e9:.1f}B {suffix}"
    if a >= 1e6:
        return f"{v / 1e6:.0f}M {suffix}"
    return f"{v:.0f} {suffix}"


def bist_fundamentals(sembol):
    """The fundamentals come from three separate upstream calls costing ~2-6s
    each, so they are fetched off the page-render path, in parallel, and cached.
    """
    now = time.time()
    cached = _mcap_cache.get(sembol)
    if cached and (now - cached["time"]) < CACHE_TTL:
        return cached["data"]

    detay = _detay_cache.get(sembol)
    if detay:
        info, fi = detay["data"]["info"], detay["data"]["fast_info"]
    else:
        tk = bp.Ticker(sembol)
        info, fi = tk.info, tk.fast_info

    def _warm(fn):
        try:
            fn()
        except Exception:
            pass

    # each lambda triggers one of the three distinct upstream fetches
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(_warm, [
            lambda: info and info.get("netDebt"),
            lambda: info and info.get("dividendYield"),
            lambda: fi and fi.pe_ratio,
        ]))

    def g(obj, key, attr=False):
        try:
            return getattr(obj, key) if attr else obj.get(key)
        except Exception:
            return None

    ev = g(info, "enterpriseToEbitda")
    dy = g(info, "dividendYield")
    pe, pb = g(fi, "pe_ratio", True), g(fi, "pb_ratio", True)
    yh, yl = g(fi, "year_high", True), g(fi, "year_low", True)

    data = {
        "market_cap": _fmt_big(g(fi, "market_cap", True)),
        "net_debt": _fmt_big(g(info, "netDebt")),
        "pe_ratio": f"{pe:.1f}" if pe else None,
        "pb_ratio": f"{pb:.1f}" if pb else None,
        "year_high": f"{yh:.2f}" if yh else None,
        "year_low": f"{yl:.2f}" if yl else None,
        "dividend_yield": f"{dy:.2f}%" if dy else None,
        "ev_ebitda": f"{ev:.1f}" if ev else None,
    }
    _mcap_cache[sembol] = {"data": data, "time": now}
    return data


def bist_ozet_getir():
    print("\n  BIST verileri yükleniyor...")
    sirketler = bp.companies()
    df = pd.DataFrame(sirketler)

    print(f"\n{'=' * 60}")
    print(f"  BIST PAY PİYASASI — {len(df)} şirket")
    print(f"{'=' * 60}")
    print(f"  {'#':>4}  {'Hisse':<10} {'Şirket Adı'}")
    print(f"  {'-' * 54}")

    for i, row in df.iterrows():
        isim = row["name"][:40]
        print(f"  {i + 1:>4}. {row['ticker']:<10} {isim}")

    print(f"{'=' * 60}")

    gecerli = set(df["ticker"].tolist())
    return df, gecerli


def detay_goster(sembol):
    print(f"\n  {sembol} verileri yükleniyor...")

    try:
        ticker = bp.Ticker(sembol)
    except Exception:
        print(f"  '{sembol}' için veri alınamadı.")
        return

    print(f"\n{'=' * 72}")
    print(f"  {sembol} — DETAYLI VERİLER")
    print(f"{'=' * 72}")

    try:
        info = ticker.info
        yon = "▲" if info.get("change", 0) >= 0 else "▼"
        print(f"  Fiyat: {info.get('last', 0):.2f} TL  |  "
              f"Değişim: {yon}{abs(info.get('change_percent', 0)):.2f}%  |  "
              f"Hacim: {info.get('volume', 0):,.0f}")
        print(f"  Açılış: {info.get('open', 0):.2f}  |  "
              f"Yüksek: {info.get('high', 0):.2f}  |  "
              f"Düşük: {info.get('low', 0):.2f}")
    except Exception:
        print(f"  Fiyat verisi alınamadı.")

    try:
        fi = ticker.fast_info
        mc = fi.market_cap
        if mc and mc > 0:
            if mc >= 1e12:
                mc_str = f"{mc / 1e12:.1f}T TL"
            elif mc >= 1e9:
                mc_str = f"{mc / 1e9:.1f}B TL"
            else:
                mc_str = f"{mc / 1e6:.0f}M TL"
        else:
            mc_str = "—"

        pe = f"{fi.pe_ratio:.1f}" if fi.pe_ratio else "—"
        pb = f"{fi.pb_ratio:.1f}" if fi.pb_ratio else "—"
        print(f"  Piy. Değeri: {mc_str}  |  F/K: {pe}  |  PD/DD: {pb}")
        print(f"  52H Yüksek: {fi.year_high:.2f}  |  52H Düşük: {fi.year_low:.2f}")
    except Exception:
        pass

    try:
        df = ticker.history(period="5g", interval="1h")
    except Exception:
        df = pd.DataFrame()

    if not df.empty:
        print(f"\n  ── Saatlik Veriler (son 20) ──")
        print(f"  {'Tarih/Saat':<18} {'Açılış':>10} {'Yüksek':>10} {'Düşük':>10} {'Kapanış':>10} {'Hacim':>12}")
        print(f"  {'-' * 72}")
        for idx, r in df.tail(20).iterrows():
            ts = str(idx)[:16] if hasattr(idx, "date") else str(idx)[:16]
            print(f"  {ts:<18} {r.get('Open', 0):>10.2f} {r.get('High', 0):>10.2f} "
                  f"{r.get('Low', 0):>10.2f} {r.get('Close', 0):>10.2f} {r.get('Volume', 0):>12,.0f}")

    print(f"\n{'=' * 72}")

    grafik_sec = input("\n  Grafik görmek ister misiniz? (e/h): ").strip().lower()
    if grafik_sec == "e":
        varsayilan_start = "2026-06-07"
        varsayilan_end = "2026-07-07"
        varsayilan_interval = "5m"
        start = input(f"  Başlangıç tarihi (YYYY-MM-DD) [{varsayilan_start}]: ").strip() or varsayilan_start
        end = input(f"  Bitiş tarihi (YYYY-MM-DD) [{varsayilan_end}]: ").strip() or varsayilan_end
        interval = input(f"  Interval (5m/15m/1h) [{varsayilan_interval}]: ").strip() or varsayilan_interval
        try:
            grafik_ciz_html(sembol, start, end, interval)
        except Exception as e:
            print(f"  Grafik oluşturulamadı: {e}")


def main():
    ozet_df, sirketler = bist_ozet_getir()

    if ozet_df.empty:
        print("Şirket verisi bulunamadı.")
        return

    while True:
        secim = input("\nDetay için hisse kodu girin (çıkış: q) [THYAO]: ").strip().upper() or "THYAO"

        if secim == "Q":
            print("Çıkış yapılıyor.")
            break

        if secim in sirketler:
            detay_goster(secim)
        else:
            ornek = ozet_df["ticker"].head(5).tolist()
            print(f"  '{secim}' geçerli bir hisse kodu değil. Örnek: {', '.join(ornek)}")


if __name__ == "__main__":
    main()
