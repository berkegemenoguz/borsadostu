import borsapy as bp
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


def hacim_format(v):
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(int(v))


PLOTLY_CONFIG = {
    "modeBarButtons": [
        ["zoomIn2d", "zoomOut2d"],
        ["zoom2d", "pan2d", "select2d"],
        ["resetScale2d", "autoScale2d"],
        ["toImage"],
    ],
    "scrollZoom": True,
    "displaylogo": False,
    "responsive": True,
}

FIB_SCRIPT_EMBED = """<script>
(function waitForPlot(){
  var gd = document.getElementById("grafik-container");
  if(!gd || !gd.data){ setTimeout(waitForPlot, 200); return; }

  var mb = gd.querySelector(".modebar");
  if(mb){ mb.style.transform="scale(1.3)"; mb.style.transformOrigin="top right"; }

  var fibLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
  var fibColors = ["#ef5350","#ff9800","#ffeb3b","#4caf50","#2196f3","#9c27b0","#26a69a"];
  var clicks = [];

  var dropdown = document.createElement("div");
  dropdown.style.cssText = "position:relative;display:inline-block;";

  var toggle = document.createElement("a");
  toggle.className = "modebar-btn";
  toggle.setAttribute("data-title","Tools");
  toggle.style.cssText = "cursor:pointer;color:#999;font-size:13px;padding:4px 8px;user-select:none;";
  toggle.textContent = "Tools ▾";

  var menu = document.createElement("div");
  menu.style.cssText = "display:none;position:absolute;right:0;top:100%;background:#161b22;border:1px solid #333;border-radius:4px;min-width:140px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.5);";

  var fibBtn = document.createElement("a");
  fibBtn.style.cssText = "display:block;padding:8px 12px;color:#999;cursor:pointer;font-size:13px;white-space:nowrap;text-decoration:none;";
  fibBtn.textContent = "Fibonacci";
  fibBtn.onmouseenter = function(){ fibBtn.style.background="#1e2a38"; };
  fibBtn.onmouseleave = function(){ fibBtn.style.background="transparent"; };
  fibBtn.onclick = function(){
    menu.style.display = "none";
    clicks = [];
    var shapes = (gd.layout.shapes||[]).filter(function(s){return !s._fib;});
    var annots = (gd.layout.annotations||[]).filter(function(a){return !a._fib;});
    Plotly.relayout(gd, {shapes:shapes, annotations:annots});
    toggle.style.color = "#4fc3f7";
    toggle.textContent = "Fib: pick high";
    gd._fibMode = true;
  };
  menu.appendChild(fibBtn);

  toggle.onclick = function(e){
    e.stopPropagation();
    menu.style.display = menu.style.display === "none" ? "block" : "none";
  };
  document.addEventListener("click", function(){ menu.style.display = "none"; });

  dropdown.appendChild(toggle);
  dropdown.appendChild(menu);
  var group = gd.querySelector(".modebar-group");
  if(group) group.appendChild(dropdown);

  gd.on("plotly_click", function(data){
    if(!gd._fibMode) return;
    var pt = data.points[0];
    if(pt.curveNumber > 1) return;
    var yVal = pt.y != null ? pt.y : (pt.close != null ? pt.close : pt.high);
    if(yVal == null || isNaN(yVal)) return;
    clicks.push(yVal);
    if(clicks.length === 1){
      toggle.textContent = "Fib: pick low";
    }
    if(clicks.length === 2){
      gd._fibMode = false;
      toggle.style.color = "#999";
      toggle.textContent = "Tools ▾";
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
})();
</script>"""


SMA_EMA_COLORS = {
    "sma20": ("#ffeb3b", "SMA 20"),
    "sma50": ("#ff9800", "SMA 50"),
    "sma200": ("#e91e63", "SMA 200"),
    "ema20": ("#00bcd4", "EMA 20"),
    "ema50": ("#7c4dff", "EMA 50"),
}


def _build_figure(sembol, start, end, interval="5m", indicators=None):
    hisse = bp.Ticker(sembol)
    df = hisse.history(start=start, end=end, interval=interval)

    if df.empty:
        return None

    if df.index.dtype != "int64":
        df["Datetime"] = pd.to_datetime(df.index)
        df = df.reset_index(drop=True)
    else:
        df["Datetime"] = pd.to_datetime(df["Datetime"])

    df = df.sort_values("Datetime").reset_index(drop=True)
    df["Idx"] = range(len(df))
    tick_positions = list(range(0, len(df), max(1, len(df) // 10)))
    tick_labels = [df["Datetime"].iloc[i].strftime("%m-%d %H:%M") for i in tick_positions]

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
        x=df["Idx"],
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color="#26a69a", increasing_fillcolor="#26a69a",
        decreasing_line_color="#ef5350", decreasing_fillcolor="#ef5350",
        name="Price",
    ), row=1, col=1)

    if indicators:
        for ind in indicators:
            if ind in SMA_EMA_COLORS:
                color, label = SMA_EMA_COLORS[ind]
                if ind.startswith("sma"):
                    period = int(ind[3:])
                    series = df["Close"].rolling(window=period).mean()
                else:
                    period = int(ind[3:])
                    series = df["Close"].ewm(span=period, adjust=False).mean()
                fig.add_trace(go.Scatter(
                    x=df["Idx"], y=series,
                    mode="lines", name=label,
                    line=dict(color=color, width=1.5),
                ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["Idx"], y=(df["High"] + df["Low"]) / 2,
        mode="markers", marker=dict(size=12, opacity=0),
        showlegend=False, hoverinfo="skip", name="_click_helper",
        customdata=df[["High", "Low"]].values.tolist(),
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=df["Idx"], y=df["Volume"],
        marker_color=hacim_renk, opacity=0.8,
        name="Volume",
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
        f"Open: {acilis:.2f} TL  |  Close: {kapanis:.2f} TL  |  "
        f"High: {en_yuksek:.2f} ({en_yuksek_saat})  |  "
        f"Low: {en_dusuk:.2f} ({en_dusuk_saat})  |  "
        f"Change: {fark_isaret}{fark_tl:.2f} TL  |  "
        f"Vol: {hacim_format(toplam_hacim)}  |  "
        f"{degisim_ok} {degisim:+.2f}%"
    )

    fig.update_layout(
        title=f"{sembol}  |  {start} → {end}  |  {interval} candlestick",
        plot_bgcolor="#0d1117",
        paper_bgcolor="#0d1117",
        font_color="#aaaaaa",
        xaxis_rangeslider_visible=False,
        yaxis_title="Price (TL)",
        yaxis2_title="Volume",
        legend=dict(bgcolor="#161b22", bordercolor="#333333"),
        height=700,
        margin=dict(b=100),
        annotations=[dict(
            text=ozet, xref="paper", yref="paper",
            x=0.5, y=-0.15, showarrow=False,
            font=dict(size=10, family="monospace", color="white"),
            bgcolor="#161b22", bordercolor="#333333", borderpad=6,
        )],
        newshape=dict(line_color="#ffab00", line_width=2),
        dragmode="pan",
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#161b22",
            bordercolor="#333333",
            font=dict(size=12, family="monospace", color="#ffffff"),
        ),
    )

    fig.update_xaxes(
        spikemode="across", spikethickness=1,
        spikecolor="#555555", spikedash="dot",
        tickvals=tick_positions,
        ticktext=tick_labels,
    )
    fig.update_yaxes(
        spikemode="across", spikethickness=1,
        spikecolor="#555555", spikedash="dot",
        fixedrange=False,
    )

    for ax in ["xaxis", "xaxis2", "yaxis", "yaxis2"]:
        fig.update_layout(**{ax: dict(gridcolor="#1e2a38", zeroline=False)})

    return fig


def grafik_ciz_html(sembol, start, end, interval="5m", indicators=None):
    fig = _build_figure(sembol, start, end, interval, indicators)
    if fig is None:
        return None

    chart_div = fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config=PLOTLY_CONFIG,
        div_id="grafik-container",
    )
    return chart_div + FIB_SCRIPT_EMBED


