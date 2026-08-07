import borsapy as bp
import pandas as pd
from datetime import date
from graphicgenerator import grafik_ciz


def bist_sirketler():
    sirketler = bp.companies()
    df = pd.DataFrame(sirketler)
    return df


def bist_detay_veri(sembol):
    result = {"info": None, "fast_info": None, "history": pd.DataFrame(), "hata": None}
    try:
        ticker = bp.Ticker(sembol)
    except Exception:
        result["hata"] = f"'{sembol}' için veri alınamadı."
        return result

    try:
        result["info"] = ticker.info
    except Exception:
        pass

    try:
        result["fast_info"] = ticker.fast_info
    except Exception:
        pass

    try:
        result["history"] = ticker.history(period="5g", interval="1h")
    except Exception:
        pass

    return result


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
            grafik_ciz(sembol, start, end, interval)
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
