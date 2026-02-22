import math
import hashlib
from decimal import Decimal, ROUND_HALF_UP

def _hash_to_unit(seed: int, symbol: str, day: int) -> float:
    h = hashlib.sha256(f"{seed}:{symbol}:{day}".encode("utf-8")).hexdigest()
    x = int(h[:8], 16)
    return (x % 1_000_000) / 1_000_000.0

def price_for(symbol: str, day: int, seed: int, base: float = 100.0) -> Decimal:
    """Precio determinístico simple (solo entrenamiento)."""
    symbol = symbol.upper().strip()
    u = _hash_to_unit(seed, symbol, day)
    drift = 0.0003
    vol = 0.015
    shock = (u - 0.5) * 2.0
    factor = math.exp(drift * day + vol * shock * math.sqrt(max(day, 1)))
    p = Decimal(str(base * factor)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    if p <= 0:
        p = Decimal("0.000001")
    return p
