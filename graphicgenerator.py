import borsapy as bp
import time
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
    "displayModeBar": True,
    "doubleClick": "reset",
}

FIB_SCRIPT_EMBED = """<script>
(function waitForPlot(){
  var gd = document.getElementById("grafik-container");
  if(!gd || !gd.data){ setTimeout(waitForPlot, 200); return; }

  var mb = gd.querySelector(".modebar");
  if(mb){
    mb.style.transform = window.innerWidth <= 768 ? "scale(1.6)" : "scale(1.3)";
    mb.style.transformOrigin = "top right";
  }

  if(window.innerWidth <= 768){
    var upd = {
      "title.text": "",
      "legend.orientation": "h",
      "legend.x": 0, "legend.y": 1, "legend.xanchor": "left", "legend.yanchor": "bottom",
      "legend.bgcolor": "rgba(0,0,0,0)", "legend.bordercolor": "rgba(0,0,0,0)",
      "margin.l": 46, "margin.r": 10, "margin.t": 58
    };
    Object.keys(gd.layout).forEach(function(k){
      if(k.indexOf("xaxis") !== 0) return;
      var tv = gd.layout[k].tickvals, tt = gd.layout[k].ticktext;
      if(!tv || !tv.length) return;
      var step = Math.ceil(tv.length / 4), nv = [], nt = [];
      for(var i = 0; i < tv.length; i += step){ nv.push(tv[i]); nt.push(tt[i]); }
      upd[k + ".tickvals"] = nv;
      upd[k + ".ticktext"] = nt;
      upd[k + ".tickangle"] = -45;
    });
    Plotly.relayout(gd, upd);
  }

  var fibLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
  var fibColors = ["#ef5350","#ff9800","#ffeb3b","#4caf50","#2196f3","#9c27b0","#26a69a"];
  var clicks = [];

  var dropdown = document.createElement("div");
  dropdown.style.cssText = "position:relative;display:inline-block;";

  var toggle = document.createElement("a");
  toggle.className = "modebar-btn";
  toggle.setAttribute("data-title","Tools");
  toggle.style.cssText = "cursor:pointer;color:#8a98ab;font-size:13px;padding:4px 8px;user-select:none;";
  toggle.textContent = "Tools ▾";

  var menu = document.createElement("div");
  menu.style.cssText = "display:none;position:absolute;right:0;top:100%;background:#0c121b;border:1px solid #1a2230;min-width:140px;z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,0.5);";

  var fibBtn = document.createElement("a");
  fibBtn.style.cssText = "display:block;padding:8px 12px;color:#cfd6e0;cursor:pointer;font-size:13px;white-space:nowrap;text-decoration:none;";
  fibBtn.textContent = "Fibonacci";
  fibBtn.onmouseenter = function(){ fibBtn.style.background="#141b24"; };
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
    gd._trendMode = false;
  };
  menu.appendChild(fibBtn);

  var trendBtn = document.createElement("a");
  trendBtn.style.cssText = "display:block;padding:8px 12px;color:#cfd6e0;cursor:pointer;font-size:13px;white-space:nowrap;text-decoration:none;";
  trendBtn.textContent = "Trend Line";
  trendBtn.onmouseenter = function(){ trendBtn.style.background="#141b24"; };
  trendBtn.onmouseleave = function(){ trendBtn.style.background="transparent"; };
  trendBtn.onclick = function(){
    menu.style.display = "none";
    clicks = [];
    toggle.style.color = "#4fc3f7";
    toggle.textContent = "Trend: pick 1st";
    gd._trendMode = true;
    gd._fibMode = false;
  };
  menu.appendChild(trendBtn);

  var clearBtn = document.createElement("a");
  clearBtn.style.cssText = "display:block;padding:8px 12px;color:#dc2626;cursor:pointer;font-size:13px;white-space:nowrap;text-decoration:none;border-top:1px solid #eee;";
  clearBtn.textContent = "Clear All";
  clearBtn.onmouseenter = function(){ clearBtn.style.background="#141b24"; };
  clearBtn.onmouseleave = function(){ clearBtn.style.background="transparent"; };
  clearBtn.onclick = function(){
    menu.style.display = "none";
    var shapes = (gd.layout.shapes||[]).filter(function(s){return !s._fib && !s._trend;});
    var annots = (gd.layout.annotations||[]).filter(function(a){return !a._fib && !a._trend;});
    Plotly.relayout(gd, {shapes:shapes, annotations:annots});
  };
  menu.appendChild(clearBtn);

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
    if(!gd._fibMode && !gd._trendMode) return;
    var pt = data.points[0];
    // accept a click from any trace drawn in the price panel (row 1); with
    // "x unified" hovermode Plotly may resolve the click to an overlay line
    // rather than the candles, so anchor by bar index instead of by trace.
    var tr = gd.data[pt.curveNumber] || {};
    if((tr.yaxis || "y") !== "y") return;

    var xVal = pt.pointIndex;
    var bar = (gd.calcdata[0] || [])[xVal];
    if(!bar) return;
    // candlestick calcdata carries max/min/yc; line & area charts only carry y
    var barHi = bar.max != null ? bar.max : bar.y;
    var barLo = bar.min != null ? bar.min : bar.y;
    var yVal  = bar.yc  != null ? bar.yc  : bar.y;
    if(yVal == null || isNaN(yVal)) return;

    if(gd._trendMode){
      clicks.push({x: xVal, y: yVal});
      if(clicks.length === 1){
        toggle.textContent = "Trend: pick 2nd";
      }
      if(clicks.length === 2){
        gd._trendMode = false;
        toggle.style.color = "#8a98ab";
        toggle.textContent = "Tools ▾";
        var shapes = gd.layout.shapes ? gd.layout.shapes.slice() : [];
        shapes.push({type:"line", x0:clicks[0].x, x1:clicks[1].x, y0:clicks[0].y, y1:clicks[1].y,
          xref:"x", yref:"y", line:{color:"#4fc3f7", width:2}, opacity:0.9, _trend:true});
        Plotly.relayout(gd, {shapes:shapes});
        clicks = [];
      }
      return;
    }

    if(gd._fibMode){
      clicks.push({hi: barHi, lo: barLo});
      if(clicks.length === 1){
        toggle.textContent = "Fib: pick low";
      }
      if(clicks.length === 2){
        gd._fibMode = false;
        toggle.style.color = "#8a98ab";
        toggle.textContent = "Tools ▾";
        // anchor to the true extremes of the two picked bars, whatever order they were picked in
        var high = Math.max(clicks[0].hi, clicks[1].hi);
        var low = Math.min(clicks[0].lo, clicks[1].lo);
        var diff = high - low;
        var shapes = gd.layout.shapes ? gd.layout.shapes.slice() : [];
        var annots = gd.layout.annotations ? gd.layout.annotations.slice() : [];
        for(var i=0; i<fibLevels.length; i++){
          var lvl = high - diff * fibLevels[i];
          shapes.push({type:"line", x0:0, x1:1, xref:"paper", y0:lvl, y1:lvl,
            yref:"y", line:{color:fibColors[i], width:1.5, dash:"dot"}, opacity:0.8, _fib:true});
          annots.push({x:0.01, xref:"paper", y:lvl, yref:"y",
            text:(fibLevels[i]*100).toFixed(1)+"% "+lvl.toFixed(2),
            showarrow:false, font:{color:fibColors[i], size:10, family:"monospace"},
            bgcolor:"rgba(12,18,27,0.92)", borderpad:2, xanchor:"left", _fib:true});
        }
        Plotly.relayout(gd, {shapes:shapes, annotations:annots});
        clicks = [];
      }
    }
  });

  gd.addEventListener("wheel", function(e){ e.preventDefault(); }, {passive: false});
})();
</script>"""


SMA_EMA_COLORS = {
    "sma20": ("#ffeb3b", "SMA 20"),
    "sma50": ("#ff9800", "SMA 50"),
    "sma200": ("#e91e63", "SMA 200"),
    "ema20": ("#00bcd4", "EMA 20"),
    "ema50": ("#7c4dff", "EMA 50"),
}


def _fetch_history(sembol, start, end, interval, attempts=3):
    """Fetch OHLC data, retrying transient upstream failures (the data provider
    drops the websocket under load, which otherwise surfaces as a raw error)."""
    last_err = None
    for i in range(attempts):
        try:
            return bp.Ticker(sembol).history(start=start, end=end, interval=interval)
        except Exception as e:
            last_err = e
            # a bad ticker will never succeed, so don't burn retries on it
            if "invalid symbol" in str(e).lower():
                break
            if i < attempts - 1:
                time.sleep(0.6 * (i + 1))
    raise last_err


OVERLAY_INDS = {"sma20", "sma50", "sma200", "ema20", "ema50", "bb", "sr", "vwap", "supertrend"}


def _build_figure(sembol, start, end, interval="5m", indicators=None, chart_type="candlestick", df=None):
    if df is None:
        df = _fetch_history(sembol, start, end, interval)
    else:
        df = df.copy()

    if df.empty:
        return None

    if df.index.dtype != "int64":
        df["Datetime"] = pd.to_datetime(df.index)
        df = df.reset_index(drop=True)
    else:
        df["Datetime"] = pd.to_datetime(df["Datetime"])

    df = df.sort_values("Datetime").reset_index(drop=True)
    df["Idx"] = range(len(df))
    tick_step = max(1, len(df) // 10)
    tick_positions = list(range(0, len(df), tick_step))
    tick_fmt = "%Y-%m-%d" if interval == "1d" else "%m-%d %H:%M"
    tick_labels = [df["Datetime"].iloc[i].strftime(tick_fmt) for i in tick_positions]

    acilis = df.iloc[0]["Open"]
    kapanis = df.iloc[-1]["Close"]
    en_yuksek = df["High"].max()
    en_dusuk = df["Low"].min()
    stamp_fmt = "%d.%m" if interval == "1d" else "%H:%M"
    en_yuksek_saat = df.loc[df["High"].idxmax(), "Datetime"].strftime(stamp_fmt)
    en_dusuk_saat = df.loc[df["Low"].idxmin(), "Datetime"].strftime(stamp_fmt)
    fark_tl = kapanis - acilis
    degisim = (kapanis - acilis) / acilis * 100
    toplam_hacim = df["Volume"].sum()

    hacim_renk = [
        "#26a69a" if c >= o else "#ef5350"
        for c, o in zip(df["Close"], df["Open"])
    ]

    has_rsi = bool(indicators and "rsi" in indicators)
    has_macd = bool(indicators and "macd" in indicators)
    has_atr = bool(indicators and "atr" in indicators)
    has_adx = bool(indicators and "adx" in indicators)
    has_obv = bool(indicators and "obv" in indicators)
    extra_panels = int(has_rsi) + int(has_macd) + int(has_atr) + int(has_adx) + int(has_obv)

    # Fixed pixel heights: the price panel never shrinks — each extra panel
    # extends the chart downward instead of compressing the candlesticks.
    PRICE_PX, VOL_PX, PANEL_PX = 450, 130, 130
    total_rows = 2 + extra_panels
    row_heights = [PRICE_PX, VOL_PX] + [PANEL_PX] * extra_panels

    fig = make_subplots(
        rows=total_rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    rsi_row = macd_row = atr_row = adx_row = obv_row = next_row = 3

    if chart_type == "line":
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=df["Close"],
            mode="lines", name="Price",
            line=dict(color="#2196f3", width=1.5),
        ), row=1, col=1)
    elif chart_type == "area":
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=df["Close"],
            mode="lines", name="Price",
            line=dict(color="#2196f3", width=1.5),
            fill="tozeroy", fillcolor="rgba(33,150,243,0.08)",
        ), row=1, col=1)
    else:
        fig.add_trace(go.Candlestick(
            x=df["Idx"],
            open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            increasing_line_color="#26a69a", increasing_fillcolor="#26a69a",
            decreasing_line_color="#ef5350", decreasing_fillcolor="#ef5350",
            name="Price",
        ), row=1, col=1)

    if indicators and "bb" in indicators:
        bb_mid = df["Close"].rolling(window=20).mean()
        bb_std = df["Close"].rolling(window=20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=bb_upper,
            mode="lines", name="BB Upper",
            line=dict(color="#9e9e9e", width=1, dash="dot"),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=bb_lower,
            mode="lines", name="BB Lower",
            line=dict(color="#9e9e9e", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(158,158,158,0.08)",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=bb_mid,
            mode="lines", name="BB Mid",
            line=dict(color="#9e9e9e", width=1),
        ), row=1, col=1)

    sr_annotations = []
    if indicators and "sr" in indicators:
        window = max(5, len(df) // 20)
        sr_points = []
        for i in range(window, len(df) - window):
            if df["High"].iloc[i] == df["High"].iloc[i - window:i + window + 1].max():
                sr_points.append((df["High"].iloc[i], i, "r"))
            if df["Low"].iloc[i] == df["Low"].iloc[i - window:i + window + 1].min():
                sr_points.append((df["Low"].iloc[i], i, "s"))
        clustered = []
        for lvl, idx, kind in sorted(sr_points):
            merged = False
            for c in clustered:
                if abs(lvl - c[0]) / c[0] < 0.005:
                    c[1].append(idx)
                    merged = True
                    break
            if not merged:
                clustered.append((lvl, [idx], kind))
        sr_colors = {"r": "#ef5350", "s": "#26a69a"}
        current = df["Close"].iloc[-1]
        seg_len = max(8, len(df) // 8)
        for lvl, indices, kind in clustered:
            kind = "r" if lvl > current else "s"
            center = int(sum(indices) / len(indices))
            x0 = max(0, center - seg_len // 2)
            x1 = min(len(df) - 1, center + seg_len // 2)
            fig.add_shape(
                type="line", x0=x0, x1=x1, y0=lvl, y1=lvl,
                xref="x", yref="y",
                line=dict(color=sr_colors[kind], width=1.5, dash="dash"),
                opacity=0.7, row=1, col=1,
            )
            sr_annotations.append(dict(
                x=x1, y=lvl, xref="x", yref="y",
                text=f" {'R' if kind == 'r' else 'S'} {lvl:.2f}",
                showarrow=False,
                font=dict(color=sr_colors[kind], size=9, family="monospace"),
                xanchor="left",
            ))

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

    if indicators and "supertrend" in indicators:
        st_period, st_mult = 10, 3.0
        st_tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ], axis=1).max(axis=1)
        st_atr = st_tr.rolling(window=st_period).mean()
        hl2 = (df["High"] + df["Low"]) / 2

        upper_l = (hl2 + st_mult * st_atr).tolist()
        lower_l = (hl2 - st_mult * st_atr).tolist()
        close_l = df["Close"].tolist()
        n = len(df)
        nan = float("nan")
        f_up, f_lo, trend = [nan] * n, [nan] * n, [1] * n

        for i in range(1, n):
            if upper_l[i] != upper_l[i]:
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

        st_up = [f_lo[i] if trend[i] == 1 else nan for i in range(n)]
        st_dn = [f_up[i] if trend[i] == -1 else nan for i in range(n)]
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=st_up,
            mode="lines", name="Supertrend ↑",
            line=dict(color="#26a69a", width=2),
            connectgaps=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=st_dn,
            mode="lines", name="Supertrend ↓",
            line=dict(color="#ef5350", width=2),
            connectgaps=False,
        ), row=1, col=1)

    if indicators and "vwap" in indicators:
        cumvol = df["Volume"].cumsum()
        cumtp = ((df["High"] + df["Low"] + df["Close"]) / 3 * df["Volume"]).cumsum()
        vwap = cumtp / cumvol
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=vwap,
            mode="lines", name="VWAP",
            line=dict(color="#ff6f00", width=1.5, dash="dash"),
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["Idx"], y=(df["High"] + df["Low"]) / 2,
        mode="markers", marker=dict(size=12, opacity=0),
        showlegend=False, hoverinfo="none", name="_click_helper",
        customdata=df[["High", "Low"]].values.tolist(),
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=df["Idx"], y=df["Volume"],
        marker_color=hacim_renk, opacity=0.8,
        name="Volume",
    ), row=2, col=1)

    if has_rsi:
        rsi_row = next_row
        next_row += 1
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=rsi,
            mode="lines", name="RSI 14",
            line=dict(color="#e040fb", width=1.5),
        ), row=rsi_row, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#f85149",
                      line_width=1, opacity=0.5, row=rsi_row, col=1,
                      annotation_text="70", annotation_font_color="#f85149",
                      annotation_font_size=9)
        fig.add_hline(y=30, line_dash="dot", line_color="#3fb950",
                      line_width=1, opacity=0.5, row=rsi_row, col=1,
                      annotation_text="30", annotation_font_color="#3fb950",
                      annotation_font_size=9)

    if has_macd:
        macd_row = next_row
        next_row += 1
        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in macd_hist.fillna(0)]
        fig.add_trace(go.Bar(
            x=df["Idx"], y=macd_hist,
            marker_color=hist_colors, opacity=0.6,
            name="MACD Hist",
        ), row=macd_row, col=1)
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=macd_line,
            mode="lines", name="MACD",
            line=dict(color="#2196f3", width=1.5),
        ), row=macd_row, col=1)
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=signal_line,
            mode="lines", name="Signal",
            line=dict(color="#ff9800", width=1.5),
        ), row=macd_row, col=1)

    if has_atr:
        atr_row = next_row
        next_row += 1
        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=atr,
            mode="lines", name="ATR 14",
            line=dict(color="#f57c00", width=1.5),
        ), row=atr_row, col=1)

    if has_adx:
        adx_row = next_row
        next_row += 1
        plus_dm = df["High"].diff()
        minus_dm = -df["Low"].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ], axis=1).max(axis=1)
        atr14 = tr.rolling(window=14).mean()
        plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr14)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr14)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
        adx = dx.rolling(window=14).mean()
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=adx,
            mode="lines", name="ADX 14",
            line=dict(color="#7c4dff", width=1.5),
        ), row=adx_row, col=1)
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=plus_di,
            mode="lines", name="+DI",
            line=dict(color="#26a69a", width=1, dash="dot"),
        ), row=adx_row, col=1)
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=minus_di,
            mode="lines", name="-DI",
            line=dict(color="#ef5350", width=1, dash="dot"),
        ), row=adx_row, col=1)
        fig.add_hline(y=25, line_dash="dot", line_color="#999",
                      line_width=1, opacity=0.5, row=adx_row, col=1,
                      annotation_text="25", annotation_font_color="#999",
                      annotation_font_size=9)

    if has_obv:
        obv_row = next_row
        next_row += 1
        chg = df["Close"].diff()
        direction = (chg > 0).astype(int) - (chg < 0).astype(int)
        obv = (direction * df["Volume"]).fillna(0).cumsum()
        fig.add_trace(go.Scatter(
            x=df["Idx"], y=obv,
            mode="lines", name="OBV",
            line=dict(color="#0288d1", width=1.5),
            fill="tozeroy", fillcolor="rgba(2,136,209,0.08)",
        ), row=obv_row, col=1)

    degisim_renk = "#26a69a" if degisim >= 0 else "#ef5350"
    fig.add_hline(
        y=kapanis, line_dash="dash", line_color=degisim_renk,
        line_width=1, opacity=0.7, row=1, col=1,
        annotation_text=f" {kapanis:.2f}",
        annotation_font_color=degisim_renk,
        annotation_font_size=10,
    )

    fark_isaret = "+" if fark_tl >= 0 else ""

    fig.update_layout(
        title=f"{sembol}  |  {start} → {end}  |  {interval} candlestick",
        plot_bgcolor="#0c121b",
        paper_bgcolor="#05080d",
        font_color="#8a98ab",
        xaxis_rangeslider_visible=False,
        yaxis_title="Price (TL)",
        yaxis2_title="Volume",
        **({"yaxis" + str(rsi_row) + "_title": "RSI",
            "yaxis" + str(rsi_row): dict(range=[0, 100])} if has_rsi else {}),
        **({"yaxis" + str(macd_row) + "_title": "MACD"} if has_macd else {}),
        **({"yaxis" + str(atr_row) + "_title": "ATR"} if has_atr else {}),
        **({"yaxis" + str(adx_row) + "_title": "ADX"} if has_adx else {}),
        **({"yaxis" + str(obv_row) + "_title": "OBV"} if has_obv else {}),
        legend=dict(bgcolor="#0c121b", bordercolor="#1a2230"),
        height=700 + extra_panels * 130,
        margin=dict(b=100),
        annotations=sr_annotations,
        newshape=dict(line_color="#ffab00", line_width=2),
        dragmode="pan",
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#0c121b",
            bordercolor="#1a2230",
            font=dict(size=12, family="monospace", color="#eef2f7"),
        ),
    )

    fig.update_xaxes(
        spikemode="across", spikethickness=1,
        spikecolor="#3a4553", spikedash="dot",
        tickvals=tick_positions,
        ticktext=tick_labels,
    )
    fig.update_yaxes(
        spikemode="across", spikethickness=1,
        spikecolor="#3a4553", spikedash="dot",
        fixedrange=False,
    )

    total_rows = 2 + extra_panels
    axes = []
    for i in range(1, total_rows + 1):
        suffix = "" if i == 1 else str(i)
        axes += ["xaxis" + suffix, "yaxis" + suffix]
    for ax in axes:
        fig.update_layout(**{ax: dict(gridcolor="#141b24", zeroline=False)})

    summary = {
        "open": f"{acilis:.2f}",
        "close": f"{kapanis:.2f}",
        "high": f"{en_yuksek:.2f}",
        "high_time": en_yuksek_saat,
        "low": f"{en_dusuk:.2f}",
        "low_time": en_dusuk_saat,
        "change_tl": f"{fark_isaret}{fark_tl:.2f}",
        "change_pct": f"{degisim:+.2f}",
        "volume": hacim_format(toplam_hacim),
        "pos": degisim >= 0,
    }

    return fig, summary

OVERLAY_MB_SCRIPT = """<script>
(function waitMB(){
  var gd = document.getElementById("grafik-overlay");
  if(!gd){ setTimeout(waitMB, 200); return; }
  var mb = gd.querySelector(".modebar");
  if(!mb){ setTimeout(waitMB, 200); return; }
  mb.style.transform = window.innerWidth <= 768 ? "scale(1.6)" : "scale(1.3)";
  mb.style.transformOrigin = "top right";
  gd.addEventListener("wheel", function(e){ e.preventDefault(); }, {passive: false});
})();
</script>"""


def _fig_to_div(fig, div_id):
    return fig.to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id=div_id)


def grafik_ciz_html(sembol, start, end, interval="5m", indicators=None,
                    chart_type="candlestick", overlay_mode="on"):
    indicators = indicators or []
    overlays = [i for i in indicators if i in OVERLAY_INDS]

    # separate mode only makes sense when there are overlays to pull out
    if overlay_mode == "separate" and overlays:
        df = _fetch_history(sembol, start, end, interval)
        panels = [i for i in indicators if i not in OVERLAY_INDS]
        main = _build_figure(sembol, start, end, interval, panels or None, chart_type, df=df)
        if main is None:
            return None, None, None
        main_fig, summary = main
        ov = _build_figure(sembol, start, end, interval, overlays, "line", df=df)
        ov_fig = ov[0]
        # overlay is the right-hand chart, so put its y-axis numbers on the
        # right (outer) side instead of the seam between the two charts
        ov_fig.update_layout(height=main_fig.layout.height,
                             title=f"{sembol}  |  Overlays",
                             paper_bgcolor="rgba(0,0,0,0)",
                             margin_l=12, margin_r=54,
                             legend=dict(x=0.005, y=0.99, xanchor="left", yanchor="top",
                                         bgcolor="rgba(12,18,27,0.6)", bordercolor="#1a2230"))
        ov_fig.update_yaxes(side="right", title_text="")
        # transparent paper on the main too, so neither shows a black margin band
        main_fig.update_layout(paper_bgcolor="rgba(0,0,0,0)")
        main_html = _fig_to_div(main_fig, "grafik-container") + FIB_SCRIPT_EMBED
        overlay_html = _fig_to_div(ov_fig, "grafik-overlay") + OVERLAY_MB_SCRIPT
        return main_html, summary, overlay_html

    result = _build_figure(sembol, start, end, interval, indicators or None, chart_type)
    if result is None:
        return None, None, None
    fig, summary = result
    return _fig_to_div(fig, "grafik-container") + FIB_SCRIPT_EMBED, summary, None
