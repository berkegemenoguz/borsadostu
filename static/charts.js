/* Borsa Dostu — canvas charts (lightweight-charts v5).
   Redraws cost a millisecond or two here, so zoom and pan need no preview
   tricks: the library handles them natively and every chart stays in step
   through a shared time scale. */
(function () {
    var LWC = window.LightweightCharts;

    var THEME = {
        bg: "#0c121b",
        text: "#8a98ab",
        grid: "#141b24",
        border: "#1a2230",
        up: "#26a69a",
        down: "#ef5350",
    };

    function baseOptions(height, el) {
        return {
            height: height,
            // Width comes from the container explicitly: relying on the default
            // measurement bit us when a wrapper was still hidden at build time.
            width: (el && el.clientWidth) || undefined,
            layout: {
                background: { color: THEME.bg },
                textColor: THEME.text,
                fontFamily: "'SF Mono', ui-monospace, monospace",
                fontSize: 11,
                attributionLogo: false,
            },
            grid: {
                vertLines: { color: THEME.grid },
                horzLines: { color: THEME.grid },
            },
            rightPriceScale: { borderColor: THEME.border },
            timeScale: { borderColor: THEME.border, timeVisible: true, secondsVisible: false },
            crosshair: {
                vertLine: { color: "#3a4553", labelBackgroundColor: "#1a2230" },
                horzLine: { color: "#3a4553", labelBackgroundColor: "#1a2230" },
            },
        };
    }

    // The payload ships one shared time axis plus bare value arrays, so rebuild
    // the {time, value} points here and let nulls stay gaps.
    function toLine(times, values) {
        var out = [];
        for (var i = 0; i < times.length; i++) {
            if (values[i] === null || values[i] === undefined) continue;
            out.push({ time: times[i], value: values[i] });
        }
        return out;
    }

    function toCandles(times, c) {
        var out = [];
        for (var i = 0; i < times.length; i++) {
            out.push({ time: times[i], open: c.o[i], high: c.h[i], low: c.l[i], close: c.c[i] });
        }
        return out;
    }

    function toVolume(times, vols, closes) {
        var out = [];
        for (var i = 0; i < times.length; i++) {
            var rising = i === 0 || closes[i] >= closes[i - 1];
            out.push({
                time: times[i], value: vols[i],
                color: rising ? "rgba(38,166,154,0.45)" : "rgba(239,83,80,0.45)",
            });
        }
        return out;
    }

    function addLines(chart, times, lines, paneIndex) {
        (lines || []).forEach(function (ln) {
            var s = chart.addSeries(LWC.LineSeries, {
                color: ln.color,
                lineWidth: ln.width || 2,
                lineStyle: ln.dashed ? 2 : 0,
                priceLineVisible: false,
                lastValueVisible: false,
                title: ln.title,
            }, paneIndex);
            s.setData(toLine(times, ln.data));
        });
    }

    function addGuides(series, guides) {
        (guides || []).forEach(function (g) {
            series.createPriceLine({
                price: g.value, color: g.color, lineWidth: 1,
                lineStyle: 1, axisLabelVisible: true, title: "",
            });
        });
    }

    /* Price chart: candles (or a line/area) with volume tucked underneath. */
    function buildPrice(el, data, opts) {
        opts = opts || {};
        var chart = LWC.createChart(el, baseOptions(opts.height || 460, el));
        var times = data.times;
        var main;

        if (opts.type === "line" || opts.type === "area") {
            var Type = opts.type === "area" ? LWC.AreaSeries : LWC.LineSeries;
            main = chart.addSeries(Type, {
                color: "#2196f3", lineWidth: 2,
                topColor: "rgba(33,150,243,0.20)", bottomColor: "rgba(33,150,243,0.02)",
                priceLineVisible: false,
            });
            main.setData(toLine(times, data.candles.c));
        } else {
            main = chart.addSeries(LWC.CandlestickSeries, {
                upColor: THEME.up, downColor: THEME.down, borderVisible: false,
                wickUpColor: THEME.up, wickDownColor: THEME.down,
                priceLineVisible: false,
            });
            main.setData(toCandles(times, data.candles));
        }

        if (opts.volume !== false) {
            var vol = chart.addSeries(LWC.HistogramSeries, {
                priceFormat: { type: "volume" },
                priceScaleId: "vol",
                lastValueVisible: false, priceLineVisible: false,
            });
            // keep volume in the bottom fifth so it never covers the price
            chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
            vol.setData(toVolume(times, data.volume, data.candles.c));
        }

        if (opts.overlays && data.overlays) {
            addLines(chart, times, data.overlays.lines);
            (data.overlays.levels || []).forEach(function (lv) {
                main.createPriceLine({
                    price: lv.price, color: lv.color, lineWidth: 1, lineStyle: 2,
                    axisLabelVisible: true, title: lv.title,
                });
            });
        }

        chart.timeScale().fitContent();
        return { chart: chart, series: main };
    }

    /* Oscillators, one pane each, in a single chart below the price charts. */
    function buildPanels(el, data) {
        var panels = data.panels || [];
        if (!panels.length) return null;

        var chart = LWC.createChart(el, baseOptions(Math.max(150, panels.length * 150), el));
        var times = data.times;

        panels.forEach(function (p, i) {
            if (i > 0) chart.addPane();
            var anchor = null;

            if (p.histogram) {
                anchor = chart.addSeries(LWC.HistogramSeries, {
                    priceLineVisible: false, lastValueVisible: false,
                }, i);
                var bars = [];
                for (var j = 0; j < times.length; j++) {
                    var v = p.histogram[j];
                    if (v === null || v === undefined) continue;
                    bars.push({
                        time: times[j], value: v,
                        color: v >= 0 ? "rgba(38,166,154,0.6)" : "rgba(239,83,80,0.6)",
                    });
                }
                anchor.setData(bars);
            }

            (p.lines || []).forEach(function (ln, n) {
                var s = chart.addSeries(LWC.LineSeries, {
                    color: ln.color, lineWidth: ln.width || 2,
                    lineStyle: ln.dashed ? 2 : 0,
                    priceLineVisible: false, lastValueVisible: false, title: ln.title,
                }, i);
                s.setData(toLine(times, ln.data));
                if (n === 0 && !anchor) anchor = s;
            });

            if (p.range && anchor) {
                anchor.applyOptions({ autoscaleInfoProvider: function () {
                    return { priceRange: { minValue: p.range[0], maxValue: p.range[1] } };
                } });
            }
            if (anchor) addGuides(anchor, p.guides);
        });

        chart.timeScale().fitContent();
        return { chart: chart };
    }

    /* Keep every chart showing the same slice of time. */
    function sync(charts) {
        var live = charts.filter(Boolean).map(function (c) { return c.chart; });
        if (live.length < 2) return;
        var applying = false;
        live.forEach(function (src) {
            src.timeScale().subscribeVisibleLogicalRangeChange(function (range) {
                if (!range || applying) return;
                applying = true;                    // guard against echoing back
                live.forEach(function (dst) {
                    if (dst !== src) dst.timeScale().setVisibleLogicalRange(range);
                });
                applying = false;
            });
        });
    }

    /* Funds price once a day, so there is no OHLC to draw — an area line for
       the unit price with fund size underneath. */
    function buildFund(el, data, opts) {
        var chart = LWC.createChart(el, baseOptions((opts && opts.height) || 420, el));
        var times = data.times;

        var price = chart.addSeries(LWC.AreaSeries, {
            lineColor: "#54d6ff", lineWidth: 2,
            topColor: "rgba(84,214,255,0.22)", bottomColor: "rgba(84,214,255,0.02)",
            priceFormat: { type: "price", precision: 6, minMove: 0.000001 },
        });
        price.setData(toLine(times, data.line));

        if (data.size && data.size.length) {
            var size = chart.addSeries(LWC.HistogramSeries, {
                priceFormat: { type: "volume" },
                priceScaleId: "size",
                color: "rgba(138,152,171,0.35)",
                lastValueVisible: false, priceLineVisible: false,
            });
            chart.priceScale("size").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
            size.setData(toLine(times, data.size));
        }

        if (data.overlays) { addLines(chart, times, data.overlays.lines); }

        chart.timeScale().fitContent();
        return { chart: chart, series: price };
    }

    window.BDCharts = {
        buildFund: function (cfg) {
            return fetch(cfg.url)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.error) throw new Error(data.error);
                    var made = [buildFund(document.getElementById(cfg.el), data, cfg)];
                    if (cfg.panels) {
                        var host = document.getElementById(cfg.panels);
                        var built = buildPanels(host, data);
                        made.push(built);
                        if (!built && host && host.parentElement) {
                            host.parentElement.classList.add("is-empty");
                        }
                    }
                    sync(made);
                    window.addEventListener("resize", function () {
                        made.forEach(function (m) {
                            if (!m) return;
                            var host = m.chart.chartElement().parentElement;
                            if (host) m.chart.applyOptions({ width: host.clientWidth });
                        });
                    });
                    return made;
                });
        },
        build: function (cfg) {
            return fetch(cfg.url)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.error) throw new Error(data.error);
                    var made = [];
                    if (cfg.main) {
                        made.push(buildPrice(document.getElementById(cfg.main), data, {
                            type: cfg.type, height: cfg.mainHeight,
                            overlays: !cfg.split,        // together mode draws them here
                        }));
                    }
                    if (cfg.overlay) {
                        made.push(buildPrice(document.getElementById(cfg.overlay), data, {
                            type: cfg.type, height: cfg.mainHeight,
                            overlays: true, volume: false,
                        }));
                    }
                    if (cfg.panels) {
                        var host = document.getElementById(cfg.panels);
                        var built = buildPanels(host, data);
                        made.push(built);
                        // collapse the strip only after building, so the chart
                        // is never measured inside a hidden box
                        if (!built && host && host.parentElement) {
                            host.parentElement.classList.add("is-empty");
                        }
                    }
                    sync(made);
                    window.addEventListener("resize", function () {
                        made.forEach(function (m) {
                            if (!m) return;
                            var el = m.chart.chartElement().parentElement;
                            if (el) m.chart.applyOptions({ width: el.clientWidth });
                        });
                    });
                    return made;
                });
        },
    };
})();
