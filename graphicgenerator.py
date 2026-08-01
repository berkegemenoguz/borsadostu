import os
import webbrowser
import borsapy as bp
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

GRAFIK_KLASORU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grafikler")
os.makedirs(GRAFIK_KLASORU, exist_ok=True)


def hacim_format(v):
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(int(v))


def grafik_ciz(sembol, start, end, interval="5m"):
    hisse = bp.Ticker(sembol)
    df = hisse.history(start=start, end=end, interval=interval)

    if df.empty:
        print(f"  '{sembol}' için veri bulunamadı.")
        return

    if df.index.dtype != "int64":
        df["Datetime"] = pd.to_datetime(df.index)
        df = df.reset_index(drop=True)
    else:
        df["Datetime"] = pd.to_datetime(df["Datetime"])

    df = df.sort_values("Datetime").reset_index(drop=True)

    acilis = df.iloc[0]["Open"]
    kapanis = df.iloc[-1]["Close"]
    en_yuksek = df["High"].max()
    en_dusuk = df["Low"].min()
    en_yuksek_saat = df.loc[df["High"].idxmax(), "Datetime"].strftime("%H:%M")
    en_dusuk_saat = df.loc[df["Low"].idxmin(), "Datetime"].strftime("%H:%M")
    fark_tl = kapanis - acilis
    degisim = (kapanis - acilis) / acilis * 100
    toplam_hacim = df["Volume"].sum()

    hacim_renk = [
        "#26a69a" if c >= o else "#ef5350"
        for c, o in zip(df["Close"], df["Open"])
    ]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    fig.add_trace(go.Candlestick(
        x=df["Datetime"],
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color="#26a69a", increasing_fillcolor="#26a69a",
        decreasing_line_color="#ef5350", decreasing_fillcolor="#ef5350",
        name="Fiyat",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=(df["High"] + df["Low"]) / 2,
        mode="markers", marker=dict(size=12, opacity=0),
        showlegend=False, hoverinfo="skip", name="_click_helper",
        customdata=df[["High", "Low"]].values.tolist(),
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=df["Datetime"], y=df["Volume"],
        marker_color=hacim_renk, opacity=0.8,
        name="Hacim",
    ), row=2, col=1)

    degisim_renk = "#26a69a" if degisim >= 0 else "#ef5350"
    fig.add_hline(
        y=kapanis, line_dash="dash", line_color=degisim_renk,
        line_width=1, opacity=0.7, row=1, col=1,
        annotation_text=f" {kapanis:.2f}",
        annotation_font_color=degisim_renk,
        annotation_font_size=10,
    )

    degisim_ok = "▲" if degisim >= 0 else "▼"
    fark_isaret = "+" if fark_tl >= 0 else ""
    ozet = (
        f"Açılış: {acilis:.2f} TL  |  Kapanış: {kapanis:.2f} TL  |  "
        f"En Yüksek: {en_yuksek:.2f} ({en_yuksek_saat})  |  "
        f"En Düşük: {en_dusuk:.2f} ({en_dusuk_saat})  |  "
        f"Fark: {fark_isaret}{fark_tl:.2f} TL  |  "
        f"Hacim: {hacim_format(toplam_hacim)}  |  "
        f"{degisim_ok} {degisim:+.2f}%"
    )

    fig.update_layout(
        title=f"{sembol}  |  {start} → {end}  |  {interval} mum grafik",
        plot_bgcolor="#0d1117",
        paper_bgcolor="#0d1117",
        font_color="#aaaaaa",
        xaxis_rangeslider_visible=False,
        yaxis_title="Fiyat (TL)",
        yaxis2_title="Hacim",
        legend=dict(bgcolor="#161b22", bordercolor="#333333"),
        margin=dict(b=80),
        annotations=[dict(
            text=ozet, xref="paper", yref="paper",
            x=0.5, y=-0.12, showarrow=False,
            font=dict(size=10, family="monospace", color="white"),
            bgcolor="#161b22", bordercolor="#333333", borderpad=6,
        )],
        newshape=dict(line_color="#ffab00", line_width=2),
    )

    for ax in ["xaxis", "xaxis2", "yaxis", "yaxis2"]:
        fig.update_layout(**{ax: dict(gridcolor="#1e2a38", zeroline=False)})

    grafik_adi = f"Z{sembol}_{start}_{end}.html"
    grafik_yolu = os.path.join(GRAFIK_KLASORU, grafik_adi)

    fig.write_html(
        grafik_yolu,
        config={
            "modeBarButtons": [
                ["zoomIn2d", "zoomOut2d"],
                ["zoom2d", "pan2d", "select2d"],
                ["drawline", "drawrect", "eraseshape"],
                ["resetScale2d", "autoScale2d"],
                ["toImage"],
            ],
            "scrollZoom": True,
            "displaylogo": False,
        },
    )

    ek_script = """<script>
window.addEventListener("load", function(){
  var mb = document.querySelector(".modebar");
  if(mb){ mb.style.transform="scale(1.5)"; mb.style.transformOrigin="top right"; }

  var fibLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
  var fibColors = ["#ef5350","#ff9800","#ffeb3b","#4caf50","#2196f3","#9c27b0","#26a69a"];
  var clicks = [];
  var gd = document.querySelector(".js-plotly-plot");
  if(!gd) return;

  var btn = document.createElement("a");
  btn.className = "modebar-btn";
  btn.setAttribute("data-title","Fibonacci Ciz");
  btn.style.cssText = "cursor:pointer;font-weight:bold;color:#ffab00;font-size:14px;padding:4px 8px;";
  btn.textContent = "Fib";
  btn.onclick = function(){
    clicks = [];
    var shapes = (gd.layout.shapes||[]).filter(function(s){return !s._fib;});
    var annots = (gd.layout.annotations||[]).filter(function(a){return !a._fib;});
    Plotly.relayout(gd, {shapes:shapes, annotations:annots});
    btn.style.color = "#ff5722";
    btn.textContent = "Fib: tepe sec";
    gd._fibMode = true;
  };
  var group = document.querySelector(".modebar-group");
  if(group) group.appendChild(btn);

  gd.on("plotly_click", function(data){
    if(!gd._fibMode) return;
    var pt = data.points[0];
    if(pt.curveNumber > 1) return;
    var yVal = pt.y != null ? pt.y : (pt.close != null ? pt.close : pt.high);
    if(yVal == null || isNaN(yVal)) return;
    clicks.push(yVal);
    if(clicks.length === 1){
      btn.textContent = "Fib: dip sec";
    }
    if(clicks.length === 2){
      gd._fibMode = false;
      btn.style.color = "#ffab00";
      btn.textContent = "Fib";
      var high = Math.max(clicks[0], clicks[1]);
      var low = Math.min(clicks[0], clicks[1]);
      var diff = high - low;
      var shapes = gd.layout.shapes ? gd.layout.shapes.slice() : [];
      var annots = gd.layout.annotations ? gd.layout.annotations.slice() : [];
      for(var i=0; i<fibLevels.length; i++){
        var yVal = high - diff * fibLevels[i];
        shapes.push({type:"line", x0:0, x1:1, xref:"paper", y0:yVal, y1:yVal,
          yref:"y", line:{color:fibColors[i], width:1.5, dash:"dot"}, opacity:0.8, _fib:true});
        annots.push({x:0.01, xref:"paper", y:yVal, yref:"y",
          text:(fibLevels[i]*100).toFixed(1)+"% "+yVal.toFixed(2),
          showarrow:false, font:{color:fibColors[i], size:10, family:"monospace"},
          bgcolor:"rgba(13,17,23,0.8)", borderpad:2, xanchor:"left", _fib:true});
      }
      Plotly.relayout(gd, {shapes:shapes, annotations:annots});
      clicks = [];
    }
  });
});
</script></body>"""

    with open(grafik_yolu, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", ek_script)
    with open(grafik_yolu, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Grafik kaydedildi: {grafik_yolu}")
    webbrowser.open(f"file://{grafik_yolu}")


if __name__ == "__main__":
    sembol = input("Hisse kodu: ").strip().upper()
    start = input("Başlangıç tarihi (YYYY-MM-DD): ").strip()
    end = input("Bitiş tarihi (YYYY-MM-DD): ").strip()
    interval = input("Interval (5m/15m/1h) [5m]: ").strip() or "5m"
    grafik_ciz(sembol, start, end, interval)
