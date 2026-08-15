from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from typing import Any
import re


def _norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _bool(v: Any) -> bool:
    return bool(v)


@dataclass
class MarketFingerprint:
    sport: str | None
    subject: str | None
    season: str | None
    release_year: int | None
    manufacturer: str | None
    product_line: str | None
    set_name: str | None
    insert_name: str | None
    card_number: str | None
    parallel_name: str | None
    variation_name: str | None
    serial_print_run: int | None
    is_rookie: bool
    is_autograph: bool
    is_relic: bool
    raw_or_graded: str | None
    grading_company: str | None
    grade_numeric: float | None

    def query_text(self) -> str:
        parts = [
            self.release_year or self.season,
            self.manufacturer,
            self.product_line,
            self.subject,
            self.card_number,
            self.insert_name,
            self.parallel_name,
            self.variation_name,
        ]
        if self.serial_print_run:
            parts.append(f"/{self.serial_print_run}")
        if self.is_rookie:
            parts.append("rookie")
        if self.is_autograph:
            parts.append("auto")
        if self.is_relic:
            parts.append("relic")
        if self.raw_or_graded == "graded" and self.grading_company:
            parts.extend([self.grading_company, self.grade_numeric])
        return " ".join(str(x) for x in parts if x not in (None, ""))

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["query_text"] = self.query_text()
        return d


def build_fingerprint(card: dict) -> MarketFingerprint:
    identity = card.get("identity") or {}
    inst = (card.get("instances") or [{}])[0] or {}
    return MarketFingerprint(
        sport=identity.get("sport"),
        subject=identity.get("primary_subject_name"),
        season=identity.get("season"),
        release_year=identity.get("release_year"),
        manufacturer=identity.get("manufacturer"),
        product_line=identity.get("product_line"),
        set_name=identity.get("set_name"),
        insert_name=identity.get("insert_name"),
        card_number=identity.get("card_number_printed") or identity.get("card_number_normalized"),
        parallel_name=identity.get("parallel_name"),
        variation_name=identity.get("variation_name"),
        serial_print_run=identity.get("serial_print_run"),
        is_rookie=_bool(identity.get("is_rookie")),
        is_autograph=_bool(identity.get("is_autograph")),
        is_relic=_bool(identity.get("is_relic")),
        raw_or_graded=inst.get("raw_or_graded") or "raw",
        grading_company=inst.get("grading_company"),
        grade_numeric=inst.get("grade_numeric"),
    )


def score_candidate(fp: MarketFingerprint, candidate: dict[str, Any]) -> dict[str, Any]:
    """Return explainable 0..1 identity match score.

    Hard identity fields (subject/card number/parallel) dominate. The function is
    provider-neutral and can later score SportsCardsPro, Card Ladder exports, or
    another licensed feed without changing valuation logic.
    """
    weights = {
        "subject": 0.24,
        "card_number": 0.18,
        "product_line": 0.12,
        "season": 0.08,
        "manufacturer": 0.07,
        "parallel_name": 0.15,
        "insert_name": 0.06,
        "variation_name": 0.04,
        "raw_or_graded": 0.03,
        "grading_company": 0.015,
        "grade_numeric": 0.015,
    }
    aliases = {
        "subject": ["subject", "player", "primary_subject_name", "name"],
        "card_number": ["card_number", "card_number_printed", "number"],
        "product_line": ["product_line", "product", "brand"],
        "season": ["season", "year", "release_year"],
        "manufacturer": ["manufacturer", "maker"],
        "parallel_name": ["parallel_name", "parallel"],
        "insert_name": ["insert_name", "insert", "subset"],
        "variation_name": ["variation_name", "variation"],
        "raw_or_graded": ["raw_or_graded", "condition_type"],
        "grading_company": ["grading_company", "grader"],
        "grade_numeric": ["grade_numeric", "grade"],
    }
    fp_dict = fp.as_dict()
    total = 0.0
    possible = 0.0
    evidence: list[dict[str, Any]] = []
    hard_mismatches: list[str] = []

    for field, weight in weights.items():
        expected = fp_dict.get(field)
        if expected in (None, ""):
            continue
        actual = None
        for key in aliases[field]:
            if candidate.get(key) not in (None, ""):
                actual = candidate.get(key)
                break
        possible += weight
        if actual in (None, ""):
            evidence.append({"field": field, "expected": expected, "actual": None, "score": 0.0})
            continue
        if field in {"grade_numeric"}:
            try:
                sim = 1.0 if abs(float(expected) - float(actual)) < 0.01 else 0.0
            except Exception:
                sim = 0.0
        else:
            a, b = _norm(expected), _norm(actual)
            sim = 1.0 if a == b and a else SequenceMatcher(None, a, b).ratio()
        total += weight * sim
        evidence.append({"field": field, "expected": expected, "actual": actual, "score": round(sim, 3)})
        if field in {"subject", "card_number", "parallel_name"} and sim < 0.55:
            hard_mismatches.append(field)

    score = total / possible if possible else 0.0
    if hard_mismatches:
        score *= 0.55
    return {
        "score": round(max(0.0, min(1.0, score)), 4),
        "hard_mismatches": hard_mismatches,
        "evidence": evidence,
        "acceptable_for_comp": bool(score >= 0.82 and not hard_mismatches),
    }


def provider_status() -> list[dict[str, Any]]:
    # V0.19.1 deliberately remains provider-neutral. External paid feeds can be
    # enabled later without altering card/valuation data structures.
    return [
        {
            "id": "manual",
            "name": "Verified Manual Comps",
            "configured": True,
            "supports_individual_sales": True,
            "supports_aggregate_estimate": False,
            "mode": "active",
        },
        {
            "id": "sportscardspro",
            "name": "SportsCardsPro",
            "configured": False,
            "supports_individual_sales": False,
            "supports_aggregate_estimate": True,
            "mode": "adapter-ready",
            "note": "Provider adapter prepared; API credentials/integration not enabled yet.",
        },
    ]
