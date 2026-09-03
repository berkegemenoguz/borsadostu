"""Indicator maths, independent of any charting library.

The same formulas previously lived inline in graphicgenerator._build_figure,
tangled with Plotly trace construction. Pulling them out lets the browser-side
chart request plain series over JSON while the calculations stay in pandas.

Every series is returned as a list of {"time": <epoch seconds>, "value": ...},
which is the shape lightweight-charts consumes. NaNs are dropped rather than
sent as nulls so gaps stay gaps.
"""
import math

import pandas as pd


# Panel indicators get their own chart; everything else is drawn over the price.
OVERLAY_INDS = {"sma20", "sma50", "sma200", "ema20", "ema50", "bb", "sr", "vwap", "supertrend"}
PANEL_INDS = {"rsi", "macd", "atr", "adx", "obv"}

LINE_STYLE = {
    "sma20": {"color": "#ffeb3b", "title": "SMA 20"},
    "sma50": {"color": "#ff9800", "title": "SMA 50"},
    "sma200": {"color": "#e91e63", "title": "SMA 200"},
    "ema20": {"color": "#00e5ff", "title": "EMA 20"},
    "ema50": {"color": "#7c4dff", "title": "EMA 50"},
}


def _times(df):
    return [int(ts.timestamp()) for ts in df.index]


def _series(df, values, digits=4):
    """Bare value list aligned to the shared time axis; None marks a gap.

    Every series shares one timestamp array sent once at the top level — with a
    {"time": ..., "value": ...} object per point the payload was five times
    larger, which is a real cost on a slow connection.
    """
    out = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        out.append(None if (math.isnan(f) or math.isinf(f)) else round(f, digits))
    return out


def _true_range(df):
    return pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs(),
    ], axis=1).max(axis=1)


def candles(df):
    # Same NaN care as _series: one NaN anywhere makes the whole JSON payload
    # unparseable in the browser.
    return {
        "o": _series(df, df["Open"]),
        "h": _series(df, df["High"]),
        "l": _series(df, df["Low"]),
        "c": _series(df, df["Close"]),
    }


def volume(df):
    # The client colours each bar from the close direction, so no per-bar colour
    # string has to travel.
    return _series(df, df["Volume"], digits=0)


def supertrend(df, period=10, mult=3.0):
    """Returns (uptrend_series, downtrend_series) — the flipping stop line."""
    atr = _true_range(df).rolling(window=period).mean()
    hl2 = (df["High"] + df["Low"]) / 2
    upper_l = (hl2 + mult * atr).tolist()
    lower_l = (hl2 - mult * atr).tolist()
    close_l = df["Close"].tolist()
    n = len(df)
    nan = float("nan")
    f_up, f_lo, trend = [nan] * n, [nan] * n, [1] * n

    for i in range(1, n):
        if upper_l[i] != upper_l[i]:      # NaN during the warm-up window
            continue
        pu = f_up[i - 1] if f_up[i - 1] == f_up[i - 1] else upper_l[i]
        pl = f_lo[i - 1] if f_lo[i - 1] == f_lo[i - 1] else lower_l[i]
        f_up[i] = upper_l[i] if (upper_l[i] < pu or close_l[i - 1] > pu) else pu
        f_lo[i] = lower_l[i] if (lower_l[i] > pl or close_l[i - 1] < pl) else pl
        if close_l[i] > f_up[i]:
            trend[i] = 1
        elif close_l[i] < f_lo[i]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

    up = [f_lo[i] if trend[i] == 1 else nan for i in range(n)]
    dn = [f_up[i] if trend[i] == -1 else nan for i in range(n)]
    return up, dn


def support_resistance(df):
    """Swing highs/lows, clustered into levels near the current price."""
    window = max(5, len(df) // 20)
    points = []
    for i in range(window, len(df) - window):
        if df["High"].iloc[i] == df["High"].iloc[i - window:i + window + 1].max():
            points.append((df["High"].iloc[i], i, "r"))
        if df["Low"].iloc[i] == df["Low"].iloc[i - window:i + window + 1].min():
            points.append((df["Low"].iloc[i], i, "s"))

    clustered = []
    for lvl, idx, kind in sorted(points):
        for c in clustered:
            if abs(lvl - c[0]) / c[0] < 0.005:
                c[1].append(idx)
                break
        else:
            clustered.append((lvl, [idx], kind))

    current = df["Close"].iloc[-1]
    levels = []
    for lvl, _idx, _kind in clustered:
        kind = "r" if lvl > current else "s"
        levels.append({
            "price": round(float(lvl), 4),
            "kind": kind,
            "color": "#ef5350" if kind == "r" else "#26a69a",
            "title": f"{'R' if kind == 'r' else 'S'} {lvl:.2f}",
        })
    return levels


def overlays(df, selected):
    """Series drawn on top of the price chart, ready for the client."""
    out = {"lines": [], "levels": []}
    if not selected:
        return out

    for ind in selected:
        if ind in LINE_STYLE:
            period = int(ind[3:])
            if ind.startswith("sma"):
                values = df["Close"].rolling(window=period).mean()
            else:
                values = df["Close"].ewm(span=period, adjust=False).mean()
            out["lines"].append({**LINE_STYLE[ind], "width": 2,
                                 "data": _series(df, values)})

    if "bb" in selected:
        mid = df["Close"].rolling(window=20).mean()
        std = df["Close"].rolling(window=20).std()
        out["lines"] += [
            {"title": "BB Upper", "color": "#9e9e9e", "width": 1, "dashed": True,
             "data": _series(df, mid + 2 * std)},
            {"title": "BB Mid", "color": "#9e9e9e", "width": 1, "dashed": True,
             "data": _series(df, mid)},
            {"title": "BB Lower", "color": "#9e9e9e", "width": 1, "dashed": True,
             "data": _series(df, mid - 2 * std)},
        ]

    if "vwap" in selected:
        cumvol = df["Volume"].cumsum()
        cumtp = ((df["High"] + df["Low"] + df["Close"]) / 3 * df["Volume"]).cumsum()
        out["lines"].append({"title": "VWAP", "color": "#ff6f00", "width": 2,
                             "dashed": True, "data": _series(df, cumtp / cumvol)})

    if "supertrend" in selected:
        up, dn = supertrend(df)
        out["lines"] += [
            {"title": "Supertrend ↑", "color": "#26a69a", "width": 2, "data": _series(df, up)},
            {"title": "Supertrend ↓", "color": "#ef5350", "width": 2, "data": _series(df, dn)},
        ]

    if "sr" in selected:
        out["levels"] = support_resistance(df)

    return out


def panels(df, selected):
    """Oscillators, each as its own pane for the chart below the price charts."""
    out = []
    if not selected:
        return out

    if "rsi" in selected:
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        out.append({
            "id": "rsi", "title": "RSI 14", "range": [0, 100],
            "lines": [{"title": "RSI 14", "color": "#e040fb", "width": 2,
                       "data": _series(df, rsi)}],
            "guides": [{"value": 70, "color": "#f85149"}, {"value": 30, "color": "#3fb950"}],
        })

    if "macd" in selected:
        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - signal
        out.append({
            "id": "macd", "title": "MACD",
            "histogram": _series(df, hist),
            "lines": [{"title": "MACD", "color": "#2196f3", "width": 2,
                       "data": _series(df, macd_line)},
                      {"title": "Signal", "color": "#ff9800", "width": 2,
                       "data": _series(df, signal)}],
        })

    if "atr" in selected:
        out.append({
            "id": "atr", "title": "ATR 14",
            "lines": [{"title": "ATR 14", "color": "#f57c00", "width": 2,
                       "data": _series(df, _true_range(df).rolling(window=14).mean())}],
        })

    if "adx" in selected:
        plus_dm = df["High"].diff()
        minus_dm = -df["Low"].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
        atr14 = _true_range(df).rolling(window=14).mean()
        plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr14)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr14)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
        out.append({
            "id": "adx", "title": "ADX 14",
            "lines": [{"title": "ADX 14", "color": "#7c4dff", "width": 2,
                       "data": _series(df, dx.rolling(window=14).mean())},
                      {"title": "+DI", "color": "#26a69a", "width": 1, "dashed": True,
                       "data": _series(df, plus_di)},
                      {"title": "-DI", "color": "#ef5350", "width": 1, "dashed": True,
                       "data": _series(df, minus_di)}],
            "guides": [{"value": 25, "color": "#999999"}],
        })

    if "obv" in selected:
        chg = df["Close"].diff()
        direction = (chg > 0).astype(int) - (chg < 0).astype(int)
        out.append({
            "id": "obv", "title": "OBV",
            "lines": [{"title": "OBV", "color": "#0288d1", "width": 2,
                       "data": _series(df, (direction * df["Volume"]).fillna(0).cumsum())}],
        })

    return out


def _fmt_volume(v):
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(int(v))


def summary(df, interval="5m"):
    """The figures shown in the chart-summary card, without building a figure."""
    acilis = float(df["Open"].iloc[0])
    kapanis = float(df["Close"].iloc[-1])
    en_yuksek = float(df["High"].max())
    en_dusuk = float(df["Low"].min())
    stamp = "%d.%m" if interval == "1d" else "%H:%M"
    fark = kapanis - acilis
    degisim = (kapanis - acilis) / acilis * 100 if acilis else 0.0
    return {
        "open": f"{acilis:.2f}",
        "close": f"{kapanis:.2f}",
        "high": f"{en_yuksek:.2f}",
        "high_time": df["High"].idxmax().strftime(stamp),
        "low": f"{en_dusuk:.2f}",
        "low_time": df["Low"].idxmin().strftime(stamp),
        "change_tl": f"{'+' if fark >= 0 else '-'}{abs(fark):.2f}",
        "change_pct": f"{degisim:+.2f}",
        "volume": _fmt_volume(float(df["Volume"].sum())),
        "pos": degisim >= 0,
    }


def fund_payload(df):
    """Fund price series for the chart.

    No technical indicators here on purpose: a fund publishes one NAV a day and
    cannot be traded intraday, so RSI/MACD-style signals read as noise rather
    than something anyone can act on. Fund analysis lives in flows, peer rank
    and drawdown instead.

    NaN is not valid JSON, and a single one makes the browser's JSON.parse
    reject the whole payload — funds routinely have gaps in FundSize.
    """
    return {
        "times": _times(df),
        "line": _series(df, df["Price"], digits=6),   # unit prices run to six places
        "size": _series(df, df["FundSize"]) if "FundSize" in df else [],
    }


def chart_payload(df, selected=None):
    """Everything the browser needs to draw the three charts."""
    selected = selected or []
    return {
        "times": _times(df),
        "candles": candles(df),
        "volume": volume(df),
        "overlays": overlays(df, [i for i in selected if i in OVERLAY_INDS]),
        "panels": panels(df, [i for i in selected if i in PANEL_INDS]),
    }
