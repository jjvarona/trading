import re

def parse_alert(text: str):
    """
    Parsea alertas BOS FORM del indicador SMBplus_v19_FINAL.pine

    Formato Pine:
      "BOS FORM LONG BTCUSDT 15 Score:75/100 ahora:84532.5 BOS:85100.0 0.6x ATR SL:83200.0 1:85300.0 2:86100.0 3:87500.0"
    """
    text = text.strip()

    m = re.search(
        r"BOS FORM (LONG|SHORT)\s+(\S+)\s+(\S+)\s+"
        r"Score:(\d+)/100\s+"
        r"ahora:([\d.]+)\s+"
        r"BOS:([\d.]+)\s+"
        r"[\d.]+x ATR\s+"
        r"SL:([\d.]+)\s+"
        r"1:([\d.]+)\s+"
        r"2:([\d.]+)\s+"
        r"3:([\d.]+)",
        text
    )
    if m:
        return {
            "signal_type": "BOS_FORM",
            "direction":   m.group(1),           # LONG / SHORT
            "symbol":      m.group(2),            # BTCUSDT
            "timeframe":   m.group(3),            # 15 / 30
            "score":       int(m.group(4)),        # 0-100
            "entry_price": float(m.group(5)),      # ahora: → entrada límite
            "bos_level":   float(m.group(6)),      # nivel BOS
            "sl":          float(m.group(7)),
            "tp1":         float(m.group(8)),
            "tp2":         float(m.group(9)),
            "tp3":         float(m.group(10)),
        }
    return None
