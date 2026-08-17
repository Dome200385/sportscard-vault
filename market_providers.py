from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from statistics import median
from typing import Any
from datetime import date, timedelta
import re

import httpx

from .config import settings


def _norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(value))


def _bool(v: Any) -> bool:
    return bool(v)


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except Exception:
        return None


def _tokens(value: Any) -> list[str]:
    return [x for x in _norm(value).split() if x]


def _token_coverage(expected: Any, title: str, *, ignore: set[str] | None = None) -> float:
    toks = [t for t in _tokens(expected) if not ignore or t not in ignore]
    if not toks:
        return 1.0
    have = set(_tokens(title))
    return sum(1 for t in toks if t in have) / len(toks)


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

    def soldcomps_query(self) -> str:
        """Specific eBay query that avoids over-constraining season/copyright wording.

        When a printed card number exists it is a stronger identity anchor than a
        year string (sellers may write 2025-26 while the card copyright says 2026).
        """
        parts: list[Any] = []
        product = self.product_line or self.set_name
        if self.manufacturer and _norm(self.manufacturer) not in _norm(product):
            parts.append(self.manufacturer)
        if product:
            parts.append(product)
        if self.subject:
            parts.append(self.subject)
        if self.card_number:
            parts.append(self.card_number)
        elif self.release_year:
            parts.append(self.release_year)
        if self.parallel_name:
            parts.append(self.parallel_name)
        # Insert names are useful when no card number is available, but many sellers
        # omit them; local matching still checks the insert when it is present.
        if not self.card_number and self.insert_name:
            parts.append(self.insert_name)
        if self.raw_or_graded == "graded" and self.grading_company:
            parts.extend([self.grading_company, self.grade_numeric])
        return " ".join(str(x) for x in parts if x not in (None, ""))

    def soldcomps_fallback_query(self) -> str:
        """Broader discovery query for scarce cards.

        Used only after the normal exact SoldComps search produced no acceptable
        verified comps. Identity is still enforced locally before any sale can
        enter a valuation.
        """
        parts: list[Any] = []
        product = self.product_line or self.set_name
        if product:
            parts.append(product)
        elif self.manufacturer:
            parts.append(self.manufacturer)
        if self.subject:
            parts.append(self.subject)
        if self.card_number:
            parts.append(self.card_number)
        elif self.release_year:
            parts.append(self.release_year)
        if self.serial_print_run:
            parts.append(f"/{self.serial_print_run}")
        if self.raw_or_graded == "graded" and self.grading_company:
            parts.extend([self.grading_company, self.grade_numeric])
        return " ".join(str(x) for x in parts if x not in (None, ""))

    def soldcomps_queries(self) -> list[dict[str, Any]]:
        primary = self.soldcomps_query().strip()
        fallback = self.soldcomps_fallback_query().strip()
        out: list[dict[str, Any]] = []
        if primary:
            out.append({"query": primary, "exact_match": True, "strategy": "primary_exact"})
        if fallback:
            out.append({"query": fallback, "exact_match": False, "strategy": "fallback_broad"})
        return out

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["query_text"] = self.query_text()
        d["soldcomps_query"] = self.soldcomps_query()
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
    """Provider-neutral structured candidate matcher retained for future feeds."""
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
        if field == "grade_numeric":
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


def score_sold_listing(fp: MarketFingerprint, item: dict[str, Any]) -> dict[str, Any]:
    """Score an eBay sold-title against the exact scanned card identity.

    Card number, player, graded/raw state and explicit parallels are guarded more
    aggressively than generic words such as Basketball or Topps.
    """
    title = item.get("title") or ""
    tnorm = _norm(title)
    tcompact = _compact(title)
    hard: list[str] = []
    evidence: list[dict[str, Any]] = []

    # Exclude obvious non-single-card listings.
    bad_patterns = [r"\blot\b", r"\bcase break\b", r"\bbox break\b", r"\bpack\b", r"\bdigital\b", r"\breprint\b"]
    if any(re.search(p, tnorm) for p in bad_patterns):
        hard.append("non_single_card_listing")

    # Raw vs graded is economically material.
    graded_in_title = bool(re.search(r"\b(psa|bgs|sgc|cgc|hga|isa)\s*(?:gem\s*)?(?:mint\s*)?\d", tnorm))
    if (fp.raw_or_graded or "raw").lower() == "raw" and graded_in_title:
        hard.append("graded_listing_for_raw_card")
    if (fp.raw_or_graded or "raw").lower() == "graded":
        grader = _norm(fp.grading_company)
        if grader and grader not in tnorm:
            hard.append("grading_company")
        if fp.grade_numeric is not None and _compact(fp.grade_numeric) not in tcompact:
            hard.append("grade_numeric")

    subject_score = _token_coverage(fp.subject, title)
    evidence.append({"field": "subject", "score": round(subject_score, 3)})
    if fp.subject and subject_score < 0.99:
        hard.append("subject")

    card_score = 1.0
    if fp.card_number:
        expected = _compact(fp.card_number)
        card_score = 1.0 if expected and expected in tcompact else 0.0
        if card_score == 0.0:
            hard.append("card_number")
    evidence.append({"field": "card_number", "score": card_score})

    ignore = {"basketball", "football", "baseball", "hockey", "cards", "card", "trading"}
    product_score = _token_coverage(fp.product_line or fp.set_name, title, ignore=ignore)
    manufacturer_score = _token_coverage(fp.manufacturer, title)
    insert_score = _token_coverage(fp.insert_name, title, ignore=ignore) if fp.insert_name else 1.0
    parallel_score = _token_coverage(fp.parallel_name, title, ignore=ignore) if fp.parallel_name else 1.0

    serial_score = 1.0
    if fp.serial_print_run:
        n = int(fp.serial_print_run)
        raw_title = str(title).lower()
        serial_hit = bool(
            re.search(rf"\b\d+\s*/\s*0*{n}\b", raw_title)
            or re.search(rf"(?<!\d)/\s*0*{n}\b", raw_title)
            or re.search(rf"\bof\s+0*{n}\b", raw_title)
        )
        serial_score = 1.0 if serial_hit else 0.0

    if fp.parallel_name and parallel_score < 0.99:
        serial_identity_override = bool(
            fp.serial_print_run and serial_score == 1.0 and subject_score >= 0.99 and card_score == 1.0
        )
        if serial_identity_override:
            parallel_score = max(parallel_score, 0.75)
        else:
            hard.append("parallel_name")

    # Release year is useful but not hard: sellers frequently write 2025-26 while
    # the card copyright/release field is 2026.
    year_score = 1.0
    if fp.release_year:
        yr = str(fp.release_year)
        yr2 = yr[-2:]
        year_score = 1.0 if (yr in tnorm or re.search(rf"\b\d{{4}}[-/]?{re.escape(yr2)}\b", tnorm)) else 0.4

    trait_scores = []
    if fp.is_autograph:
        trait_scores.append(1.0 if re.search(r"\b(auto|autograph|signed)\b", tnorm) else 0.55)
    if fp.is_rookie:
        trait_scores.append(1.0 if re.search(r"\b(rc|rookie)\b", tnorm) else 0.65)
    if fp.is_relic:
        trait_scores.append(1.0 if re.search(r"\b(relic|patch|jersey|memorabilia)\b", tnorm) else 0.45)
    traits = sum(trait_scores) / len(trait_scores) if trait_scores else 1.0

    evidence += [
        {"field": "product_line", "score": round(product_score, 3)},
        {"field": "manufacturer", "score": round(manufacturer_score, 3)},
        {"field": "insert_name", "score": round(insert_score, 3)},
        {"field": "parallel_name", "score": round(parallel_score, 3)},
        {"field": "serial_print_run", "score": round(serial_score, 3)},
        {"field": "release_year", "score": round(year_score, 3)},
        {"field": "traits", "score": round(traits, 3)},
    ]

    weighted = (
        subject_score * 0.30 + card_score * 0.25 + product_score * 0.15 +
        manufacturer_score * 0.05 + insert_score * 0.08 + parallel_score * 0.10 +
        year_score * 0.03 + traits * 0.04
    )
    if hard:
        weighted *= 0.45
    score = round(max(0.0, min(1.0, weighted)), 4)
    return {
        "score": score,
        "hard_mismatches": sorted(set(hard)),
        "evidence": evidence,
        "acceptable_for_comp": bool(score >= 0.72 and not hard),
        "title": title,
    }


class SoldCompsError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def soldcomps_search(fp: MarketFingerprint, *, query_override: str | None = None, exact_match: bool = True) -> dict[str, Any]:
    if not settings.soldcomps_api_key:
        raise SoldCompsError("SOLDCOMPS_API_KEY is not configured")
    query = (query_override or fp.soldcomps_query()).strip()
    if not fp.subject or not (fp.product_line or fp.set_name) or not query:
        raise SoldCompsError("Fingerprint is too incomplete for an automatic sold-comps search")
    params: dict[str, Any] = {
        "keyword": query,
        "page": 1,
        "count": settings.soldcomps_count,
        "ebaySite": settings.soldcomps_ebay_site,
        "sortOrder": "endedRecently",
        "sold": "true",
        "exactMatch": "true" if exact_match else "false",
        "includeCompleteListing": "true",
        "soldAfter": (date.today() - timedelta(days=settings.soldcomps_days)).isoformat(),
    }
    headers = {"Authorization": f"Bearer {settings.soldcomps_api_key}", "Accept": "application/json"}
    try:
        with httpx.Client(timeout=settings.soldcomps_timeout_seconds, follow_redirects=True) as client:
            response = client.get(settings.soldcomps_api_base.rstrip("/") + "/v1/scrape", params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise SoldCompsError(f"SoldComps network error: {exc}") from exc
    if response.status_code != 200:
        try:
            body = response.json()
        except Exception:
            body = {"message": response.text[:500]}
        code = body.get("code") if isinstance(body, dict) else None
        message = body.get("message") or body.get("error") or str(body)
        raise SoldCompsError(f"SoldComps HTTP {response.status_code}: {message}", status_code=response.status_code, code=code)
    data = response.json()
    items = data.get("items") or []
    return {
        "provider": "soldcomps",
        "query": query,
        "items": items,
        "total_items": data.get("totalItems", len(items)),
        "total_results": data.get("totalResults"),
        "has_next_page": bool(data.get("hasNextPage")),
        "ebay_site": settings.soldcomps_ebay_site,
        "sold_after": params["soldAfter"],
        "exact_match": exact_match,
    }


def _robust_outlier_flags(values: list[float]) -> list[bool]:
    if len(values) < 4:
        return [True] * len(values)
    med = median(values)
    deviations = [abs(v - med) for v in values]
    mad = median(deviations)
    flags = []
    for v in values:
        ratio_ok = (med <= 0) or (v >= med * 0.35 and v <= med * 3.0)
        mad_ok = True if mad <= 0 else abs(v - med) / mad <= 3.5
        flags.append(bool(ratio_ok and mad_ok))
    return flags


def normalize_soldcomps_results(fp: MarketFingerprint, search: dict[str, Any]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in search.get("items") or []:
        match = score_sold_listing(fp, item)
        sold_price = _float(item.get("soldPrice"))
        shipping = _float(item.get("shippingPrice")) or 0.0
        total = _float(item.get("totalPrice"))
        if total is None and sold_price is not None:
            total = sold_price + shipping
        currency = (item.get("soldCurrency") or item.get("shippingCurrency") or "USD").upper()
        row = {"item": item, "match": match, "all_in_price": total, "currency": currency}
        if match["acceptable_for_comp"] and total is not None and total > 0:
            matches.append(row)
        else:
            rejected.append(row)

    # Never mix currencies in one valuation. For our default ebay.com feed this
    # should normally be USD; if mixed, retain the largest currency group.
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in matches:
        groups.setdefault(row["currency"], []).append(row)
    if groups:
        chosen_currency, selected = max(groups.items(), key=lambda kv: len(kv[1]))
    else:
        chosen_currency, selected = None, []

    values = [float(r["all_in_price"]) for r in selected]
    flags = _robust_outlier_flags(values)
    for row, include in zip(selected, flags):
        row["included_in_valuation"] = include
        row["exclusion_reason"] = None if include else "robust_price_outlier"

    return {
        "query": search.get("query"),
        "raw_count": len(search.get("items") or []),
        "matched_count": len(matches),
        "selected_currency": chosen_currency,
        "matches": selected,
        "rejected_count": len(rejected) + (len(matches) - len(selected)),
        "included_count": sum(1 for r in selected if r.get("included_in_valuation")),
        "rejected_preview": [
            {"title": r["item"].get("title"), "score": r["match"]["score"], "reasons": r["match"]["hard_mismatches"]}
            for r in rejected[:8]
        ],
    }


def provider_status() -> list[dict[str, Any]]:
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
            "id": "soldcomps",
            "name": "SoldComps / eBay Sold",
            "configured": bool(settings.soldcomps_api_key),
            "supports_individual_sales": True,
            "supports_aggregate_estimate": False,
            "mode": "live" if settings.soldcomps_api_key else "not-configured",
            "ebay_site": settings.soldcomps_ebay_site,
            "history_days": settings.soldcomps_days,
            "note": "Completed eBay sales only; asking prices are never used as market value.",
        },
        {
            "id": "sportscardspro",
            "name": "SportsCardsPro",
            "configured": False,
            "supports_individual_sales": False,
            "supports_aggregate_estimate": True,
            "mode": "adapter-ready",
            "note": "Optional paid aggregate provider; not enabled.",
        },
    ]
