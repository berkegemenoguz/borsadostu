from flask import Flask, render_template, request, make_response, g
from bist import bist_sirketler, bist_detay_veri, bist_ticker_veri
from viop import viop_ozet_veri, viop_detay_veri, kontrat_tarih_araligi
from graphicgenerator import grafik_ciz_html
from translations import TRANSLATIONS

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


@app.route("/")
def home():
    ticker_data = bist_ticker_veri()
    return render_template("home.html", ticker_data=ticker_data)


@app.route("/bist")
def bist():
    df = bist_sirketler()
    sirketler = df.to_dict("records")
    return render_template("bist.html", sirketler=sirketler, count=len(sirketler))


@app.route("/bist/<sembol>")
def bist_detay(sembol):
    sembol = sembol.upper()
    veri = bist_detay_veri(sembol)
    chart_html = None

    indicators = request.args.getlist("ind")
    start = request.args.get("start")
    if start:
        end = request.args.get("end", start)
        interval = request.args.get("interval", "5m")
        try:
            chart_html = grafik_ciz_html(sembol, start, end, interval, indicators or None)
        except Exception as e:
            veri["hata"] = f"Chart error: {e}"

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
                           chart_html=chart_html,
                           start=request.args.get("start", "2026-06-07"),
                           end=request.args.get("end", "2026-07-07"),
                           interval=request.args.get("interval", "5m"),
                           active_indicators=indicators)


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

    indicators = request.args.getlist("ind")
    sembol_param = request.args.get("sembol")
    if sembol_param:
        kod = veri["kodlar"].get(sembol_param, "")
        start, end = kontrat_tarih_araligi(kod)
        interval = request.args.get("interval", "1h")
        if start and end:
            try:
                chart_html = grafik_ciz_html(sembol_param, start, end, interval, indicators or None)
            except Exception as e:
                veri["hata"] = f"Chart error: {e}"

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
                           semboller=veri["semboller"], chart_html=chart_html,
                           interval=request.args.get("interval", "1h"),
                           active_indicators=indicators)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
