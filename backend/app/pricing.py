from dataclasses import dataclass
from statistics import median, mean
from typing import Iterable

@dataclass(frozen=True)
class Comp:
    price: float
    currency: str
    raw_or_graded: str = "raw"
    included: bool = True

@dataclass(frozen=True)
class Valuation:
    reliable: bool
    comp_count: int
    currency: str | None
    median_value: float | None
    mean_value: float | None
    low_value: float | None
    high_value: float | None
    reason: str

def calculate_valuation(comps: Iterable[Comp], minimum_comps: int = 3) -> Valuation:
    included = [c for c in comps if c.included]
    if not included:
        return Valuation(False, 0, None, None, None, None, None, "Keine passenden Verkaufspreise vorhanden.")
    currencies = {c.currency.upper() for c in included}
    if len(currencies) != 1:
        return Valuation(False, len(included), None, None, None, None, None, "Währungen müssen vor der Bewertung vereinheitlicht werden.")
    values = [float(c.price) for c in included]
    currency = next(iter(currencies))
    if len(values) < minimum_comps:
        return Valuation(False, len(values), currency, None, None, min(values), max(values), f"Nur {len(values)} passende Comps; mindestens {minimum_comps} erforderlich.")
    return Valuation(True, len(values), currency, float(median(values)), float(mean(values)), min(values), max(values), "Wert basiert auf nachvollziehbaren, eingeschlossenen Comps.")
