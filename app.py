from flask import Flask, render_template, request, make_response, g, url_for
from bist import bist_sirketler, bist_detay_veri, bist_ticker_veri, bist_top_movers, bist_xu100, bist_fundamentals
from viop import viop_ozet_veri, viop_detay_veri, kontrat_tarih_araligi
from graphicgenerator import _fetch_history
from indicators import chart_payload, summary
from rates import get_rates
from translations import TRANSLATIONS
from concurrent.futures import ThreadPoolExecutor
import logging

logging.basicConfig(level=logging.INFO)
# borsapy's websocket layer logs every connect/close at INFO, which floods the
# logs and buries our own warnings. Keep its errors, drop the chatter.
logging.getLogger("websocket").setLevel(logging.ERROR)

app = Flask(__name__)


@app.before_request
def set_language():
    g.lang = request.cookies.get("lang", "en")
    g.t = TRANSLATIONS.get(g.lang, TRANSLATIONS["en"])


@app.context_processor
def inject_translations():
    return {"t": g.t, "lang": g.lang}


@app.route("/lang/<code>")
def set_lang(code):
    if code not in TRANSLATIONS:
        code = "en"
    resp = make_response("")
    resp.set_cookie("lang", code, max_age=365*24*3600)
    resp.headers["Location"] = request.referrer or "/"
    resp.status_code = 302
    return resp


@app.route("/health")
def health():
    # Keep-alive only: instant 200 so the uptime pinger resets Render's idle
    # timer and the service never sleeps. Deliberately does NOT fetch data —
    # warming from here hammered the quote endpoint and got the IP rate-limited.
    return "ok", 200


@app.route("/")
def home():
    # these four are independent upstream fetches (~13s combined when cold);
    # run them in parallel so a cold home page pays only the slowest one
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_ticker = pool.submit(bist_ticker_veri)
        f_movers = pool.submit(bist_top_movers)
        f_rates = pool.submit(get_rates)
        f_xu100 = pool.submit(bist_xu100)
        ticker_data = f_ticker.result()
        movers = f_movers.result()
        rates = f_rates.result()
        xu100 = f_xu100.result()
    return render_template("home.html", ticker_data=ticker_data, movers=movers, rates=rates, xu100=xu100)


@app.route("/bist")
def bist():
    df = bist_sirketler()
    sirketler = df.to_dict("records")
    movers = bist_top_movers()
    return render_template("bist.html", sirketler=sirketler, count=len(sirketler), movers=movers)


@app.route("/bist/<sembol>")
def bist_detay(sembol):
    sembol = sembol.upper()
    veri = bist_detay_veri(sembol)
    chart_html = None
    chart_summary = None

    indicators = request.args.getlist("ind")
    chart_type = request.args.get("chart_type", "candlestick")
    overlay_mode = request.args.get("overlay_mode", "on")
    start = request.args.get("start")
    # Both views are drawn in the browser on canvas: redraws are cheap enough
    # there that zooming stays fluid, and the panels get their own chart below.
    split = overlay_mode == "separate"
    if start:
        end = request.args.get("end", start)
        interval = request.args.get("interval", "5m")
        try:
            df = _fetch_history(sembol, start, end, interval)
            if df is None or df.empty:
                raise ValueError("no data")
            chart_summary = summary(df, interval)
            chart_html = True              # tells the template to place the canvases
        except Exception as e:
            app.logger.warning("Chart failed for %s: %s", sembol, e)
            veri["hata"] = g.t["data_unavailable"]
            chart_html = None

    history_rows = []
    if not veri["history"].empty:
        for idx, r in veri["history"].tail(20).iterrows():
            ts = str(idx)[:16]
            history_rows.append({
                "ts": ts,
                "open": f"{r.get('Open', 0):.2f}",
                "high": f"{r.get('High', 0):.2f}",
                "low": f"{r.get('Low', 0):.2f}",
                "close": f"{r.get('Close', 0):.2f}",
                "volume": f"{r.get('Volume', 0):,.0f}",
            })

    return render_template("bist_detay.html",
                           sembol=sembol, veri=veri, history=history_rows,
                           chart_html=chart_html, chart_summary=chart_summary,
                           start=request.args.get("start", "2026-06-07"),
                           end=request.args.get("end", "2026-07-07"),
                           interval=request.args.get("interval", "5m"),
                           active_indicators=indicators,
                           chart_type=chart_type,
                           overlay_mode=overlay_mode,
                           split=split)


@app.route("/api/chart/<sembol>")
def api_chart(sembol):
    """OHLC plus the selected indicator series, for the browser-side charts."""
    start = request.args.get("start")
    end = request.args.get("end", start)
    interval = request.args.get("interval", "5m")
    if not start:
        return {"error": "missing range"}, 400
    try:
        df = _fetch_history(sembol.upper(), start, end, interval)
        if df is None or df.empty:
            return {"error": g.t["data_unavailable"]}, 200
        return chart_payload(df, request.args.getlist("ind"))
    except Exception as e:
        app.logger.warning("Chart data failed for %s: %s", sembol, e)
        return {"error": g.t["data_unavailable"]}, 200


@app.route("/api/fundamentals/<sembol>")
def api_fundamentals(sembol):
    try:
        return bist_fundamentals(sembol.upper())
    except Exception as e:
        app.logger.warning("Fundamentals failed for %s: %s", sembol, e)
        return {}


@app.route("/viop")
def viop():
    ozet, _ = viop_ozet_veri()
    rows = ozet.to_dict("records")
    return render_template("viop.html", rows=rows, count=len(rows))


@app.route("/viop/<base>")
def viop_detay(base):
    base = base.upper()
    _, tum_df = viop_ozet_veri()
    veri = viop_detay_veri(base, tum_df)
    chart_html = None
    chart_summary = None

    indicators = request.args.getlist("ind")
    chart_type = request.args.get("chart_type", "candlestick")
    overlay_mode = request.args.get("overlay_mode", "on")
    sembol_param = request.args.get("sembol")
    split = overlay_mode == "separate"
    chart_url = None
    if sembol_param:
        kod = veri["kodlar"].get(sembol_param, "")
        start, end = kontrat_tarih_araligi(kod)
        interval = request.args.get("interval", "1h")
        if start and end:
            try:
                df = _fetch_history(sembol_param, start, end, interval)
                if df is None or df.empty:
                    raise ValueError("no data")
                chart_summary = summary(df, interval)
                chart_html = True
                # the contract's range is derived here, so hand the browser a
                # ready-made URL rather than re-deriving it client-side
                chart_url = url_for("api_chart", sembol=sembol_param, start=start,
                                    end=end, interval=interval, ind=indicators)
            except Exception as e:
                app.logger.warning("Chart failed for %s: %s", sembol_param, e)
                veri["hata"] = g.t["data_unavailable"]
                chart_html = None

    kontrat_rows = []
    for _, row in veri["kontratlar"].iterrows():
        arrow = "▲" if row["change"] >= 0 else "▼"
        kontrat_rows.append({
            "contract": row["contract"],
            "price": f"{row['price']:.2f}",
            "change": f"{arrow}{abs(row['change']):.2f}%",
            "change_pos": row["change"] >= 0,
            "volume": f"{row['volume_qty']:,.0f}",
        })

    return render_template("viop_detay.html",
                           base=base, veri=veri, kontratlar=kontrat_rows,
                           semboller=veri["semboller"], chart_html=chart_html, chart_summary=chart_summary,
                           interval=request.args.get("interval", "1h"),
                           chart_type=chart_type,
                           overlay_mode=overlay_mode,
                           active_indicators=indicators,
                           split=split, chart_url=chart_url)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
