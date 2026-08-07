import borsapy as bp
import pandas as pd
import re
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from graphicgenerator import grafik_ciz_html

AY_MAP = {
    "01": "F", "02": "G", "03": "H", "04": "J", "05": "K", "06": "M",
    "07": "N", "08": "Q", "09": "U", "10": "V", "11": "X", "12": "Z",
}


def hisse_kodu_ayikla(code):
    m = re.match(r"F_([A-Z]+)\d", code)
    return m.group(1) if m else code


def viop_sembol(code):
    m = re.match(r"F_([A-Z]+)(\d{2})(\d{2})", code)
    if not m:
        return None
    base, ay, yil = m.group(1), m.group(2), m.group(3)
    ay_harf = AY_MAP.get(ay)
    if not ay_harf:
        return None
    return f"{base}{ay_harf}20{yil}"


def gecmis_getir(sembol):
    try:
        df = bp.Ticker(sembol).history(period="5g", interval="1h")
        return sembol, df
    except Exception:
        return sembol, None


def viop_ozet_veri():
    v = bp.VIOP()
    df = v.stock_futures.copy()
    df["base"] = df["code"].apply(hisse_kodu_ayikla)
    ozet = (
        df.groupby("base")
        .agg(kontrat=("code", "count"), hacim=("volume_qty", "sum"))
        .sort_values("hacim", ascending=False)
        .reset_index()
    )
    return ozet, df


def viop_detay_veri(base, tum_df):
    filtre = tum_df[tum_df["base"] == base].sort_values("volume_qty", ascending=False)
    if filtre.empty:
        return {"kontratlar": pd.DataFrame(), "semboller": {}, "tarihsel": {}, "hata": f"'{base}' için kontrat bulunamadı."}

    semboller = {}
    for _, row in filtre.iterrows():
        s = viop_sembol(row["code"])
        if s and s not in semboller:
            semboller[s] = row["contract"]

    sonuclar = {}
    with ThreadPoolExecutor(max_workers=max(len(semboller), 1)) as pool:
        futures = {pool.submit(gecmis_getir, s): s for s in semboller}
        for f in as_completed(futures):
            sembol, df = f.result()
            if df is not None and len(df) > 0:
                sonuclar[sembol] = df

    return {"kontratlar": filtre, "semboller": semboller, "tarihsel": sonuclar, "hata": None}


def viop_ozet_getir():
    print("\n  VIOP verileri yükleniyor...")
    v = bp.VIOP()
    df = v.stock_futures.copy()

    df["base"] = df["code"].apply(hisse_kodu_ayikla)

    ozet = (
        df.groupby("base")
        .agg(
            kontrat=("code", "count"),
            hacim=("volume_qty", "sum"),
        )
        .sort_values("hacim", ascending=False)
        .reset_index()
    )

    print(f"\n{'=' * 60}")
    print(f"  VIOP HİSSE VADELİ — {len(df)} kontrat, {len(ozet)} hisse")
    print(f"{'=' * 60}")
    print(f"  {'#':>3}  {'Hisse':<8} {'Kontrat':>8} {'Toplam Hacim':>18}")
    print(f"  {'-' * 52}")

    for i, row in ozet.iterrows():
        print(f"  {i + 1:>3}. {row['base']:<8} {row['kontrat']:>8} {row['hacim']:>18,.0f}")

    print(f"{'=' * 60}")
    return ozet, df


def detay_goster(base, tum_df):
    filtre = tum_df[tum_df["base"] == base].sort_values("volume_qty", ascending=False)

    if filtre.empty:
        print(f"  '{base}' için kontrat bulunamadı.")
        return

    print(f"\n{'=' * 72}")
    print(f"  {base} — DETAYLI VIOP VERİLERİ ({len(filtre)} kontrat)")
    print(f"{'=' * 72}")
    print(f"  {'Kontrat':<30} {'Fiyat':>10} {'Değişim':>10} {'Hacim':>16}")
    print(f"  {'-' * 68}")

    for _, row in filtre.iterrows():
        yon = "▲" if row["change"] >= 0 else "▼"
        print(f"  {row['contract']:<30} {row['price']:>10.2f} {yon}{abs(row['change']):>7.2f}% {row['volume_qty']:>16,.0f}")

    semboller = {}
    for _, row in filtre.iterrows():
        s = viop_sembol(row["code"])
        if s and s not in semboller:
            semboller[s] = row["contract"]

    print(f"\n  Saatlik veri yükleniyor ({len(semboller)} kontrat)...")

    sonuclar = {}
    with ThreadPoolExecutor(max_workers=max(len(semboller), 1)) as pool:
        futures = {pool.submit(gecmis_getir, s): s for s in semboller}
        for f in as_completed(futures):
            sembol, df = f.result()
            if df is not None and len(df) > 0:
                sonuclar[sembol] = df

    for sembol, kontrat_adi in semboller.items():
        df = sonuclar.get(sembol)
        if df is None:
            continue

        print(f"\n  ── {kontrat_adi} — Saatlik Veriler (son 20) ──")
        print(f"  {'Tarih/Saat':<18} {'Açılış':>10} {'Yüksek':>10} {'Düşük':>10} {'Kapanış':>10} {'Hacim':>10}")
        print(f"  {'-' * 70}")
        for idx, r in df.tail(20).iterrows():
            ts = str(idx)[:16] if hasattr(idx, "date") else str(idx)[:16]
            print(f"  {ts:<18} {r.get('Open',0):>10.2f} {r.get('High',0):>10.2f} "
                  f"{r.get('Low',0):>10.2f} {r.get('Close',0):>10.2f} {r.get('Volume',0):>10.0f}")

    print(f"\n{'=' * 72}")

    grafik_sec = input("\n  Grafik görmek ister misiniz? (e/h): ").strip().lower()
    if grafik_sec == "e":
        sembol_listesi = list(semboller.keys())
        if len(sembol_listesi) == 1:
            secilen = sembol_listesi[0]
        else:
            print(f"  Kontratlar: {', '.join(sembol_listesi)}")
            secilen = input(f"  Sembol seçin [{sembol_listesi[0]}]: ").strip().upper() or sembol_listesi[0]

        bugun = date.today().isoformat()
        start = input(f"  Başlangıç tarihi (YYYY-MM-DD) [{bugun}]: ").strip() or bugun
        end = input(f"  Bitiş tarihi (YYYY-MM-DD) [{bugun}]: ").strip() or bugun
        interval = input(f"  Interval (5m/15m/1h) [5m]: ").strip() or "5m"
        try:
            grafik_ciz_html(secilen, start, end, interval)
        except Exception as e:
            print(f"  Grafik oluşturulamadı: {e}")


def main():
    ozet, tum_df = viop_ozet_getir()

    if ozet.empty:
        print("Aktif VIOP kontratı bulunamadı.")
        return

    hisseler = ozet["base"].tolist()

    while True:
        secim = input("\nDetay için hisse kodu girin (çıkış: q): ").strip().upper()

        if secim == "Q":
            print("Çıkış yapılıyor.")
            break

        if secim in hisseler:
            detay_goster(secim, tum_df)
        else:
            print(f"  '{secim}' listede yok. Örnek: {', '.join(hisseler[:5])}")


if __name__ == "__main__":
    main()