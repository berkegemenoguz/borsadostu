/* Borsa Dostu — shared client-side search helpers.
   Turkish-aware normalization, relevance scoring, fuzzy match, highlight. */
(function () {
    window.BD = window.BD || {};

    // Fold Turkish letters to ASCII, then lowercase. Length-preserving:
    // every replacement is 1 char -> 1 char, so normalized indices stay
    // aligned with the original string (needed for highlight slicing).
    BD.norm = function (s) {
        return (s || "")
            .replace(/İ/g, "i").replace(/I/g, "i").replace(/ı/g, "i")
            .replace(/Ş/g, "s").replace(/ş/g, "s")
            .replace(/Ğ/g, "g").replace(/ğ/g, "g")
            .replace(/Ü/g, "u").replace(/ü/g, "u")
            .replace(/Ö/g, "o").replace(/ö/g, "o")
            .replace(/Ç/g, "c").replace(/ç/g, "c")
            .toLowerCase().trim();
    };

    // Do the characters of q appear in order inside s? (typo tolerance)
    BD.subseq = function (q, s) {
        var i = 0;
        for (var j = 0; j < s.length && i < q.length; j++) {
            if (s[j] === q[i]) i++;
        }
        return i === q.length;
    };

    BD.esc = function (s) {
        return String(s)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    };

    // Highlight the first contiguous match of q inside orig.
    // normed must be BD.norm(orig) (same length) so indices line up.
    BD.hl = function (orig, normed, q) {
        if (!q) return BD.esc(orig);
        var pos = normed.indexOf(q);
        if (pos < 0) return BD.esc(orig);
        return BD.esc(orig.slice(0, pos)) +
            '<span class="hl">' + BD.esc(orig.slice(pos, pos + q.length)) + "</span>" +
            BD.esc(orig.slice(pos + q.length));
    };

    // Popular-name -> ticker aliases (keys already normalized).
    BD.ALIAS = {
        "thy": "THYAO", "turkhavayollari": "THYAO",
        "isbank": "ISCTR", "isbankasi": "ISCTR", "isbankc": "ISCTR",
        "garanti": "GARAN", "garantibankasi": "GARAN",
        "akbank": "AKBNK",
        "koc": "KCHOL", "kocholding": "KCHOL",
        "sabanci": "SAHOL", "sabanciholding": "SAHOL",
        "bim": "BIMAS",
        "sise": "SISE", "sisecam": "SISE",
        "eregli": "EREGL", "erdemir": "EREGL",
        "tupras": "TUPRS",
        "aselsan": "ASELS",
        "turkcell": "TCELL",
        "pegasus": "PGSUS",
        "ford": "FROTO", "fordotosan": "FROTO",
        "tofas": "TOASO",
        "yapikredi": "YKBNK", "ykb": "YKBNK",
        "halkbank": "HALKB",
        "vakifbank": "VAKBN",
        "petkim": "PETKM",
        "sasa": "SASA",
        "as.": "ASELS"
    };
})();
