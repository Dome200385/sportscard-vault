from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from .config import settings
from .image_utils import prepare_for_vision

CRITICAL_FIELDS = [
    "sport", "season", "manufacturer", "product_line", "set_name",
    "card_number_printed", "primary_subject_name", "parallel_name",
]

AUTO_ACCEPT_THRESHOLDS = {
    "sport": 0.98,
    "season": 0.97,
    "manufacturer": 0.97,
    "product_line": 0.97,
    "set_name": 0.96,
    "card_number_printed": 0.98,
    "primary_subject_name": 0.98,
    "parallel_name": 0.94,
    "variation_name": 0.94,
    "serial_print_run": 0.98,
    "serial_number_actual": 0.99,
}

# Fields the model may extract. Price/value fields are deliberately absent.
INSTANCE_SCAN_FIELDS = ["raw_or_graded", "grading_company", "grade_numeric", "grade_label", "cert_number", "serial_number_actual"]

IDENTITY_FIELDS = [
    "sport", "league", "season", "release_year", "manufacturer", "brand",
    "product_line", "set_name", "subset_name", "insert_name", "checklist_group",
    "card_number_printed", "card_number_normalized", "primary_subject_name",
    "secondary_subject_names", "team_name", "team_city", "country", "position",
    "parallel_name", "parallel_family", "parallel_color", "variation_name",
    "variation_code", "refractor_prizm_type", "is_rookie", "rookie_label_text",
    "is_insert", "is_short_print", "is_super_short_print", "is_case_hit",
    "is_autograph", "autograph_type", "is_relic", "relic_type", "is_rpa",
    "is_booklet", "is_die_cut", "is_redemption", "is_serial_numbered",
    "serial_print_run", "known_print_run", "stated_odds", "orientation",
    "card_stock_notes", "finish_notes",
]


def _guess(value: Any = None, confidence: float = 0.0, evidence: str | None = None) -> dict[str, Any]:
    return {"value": value, "confidence": max(0.0, min(1.0, confidence)), "evidence": evidence}


def analyze_locked_context(locked: dict[str, Any]) -> dict[str, Any]:
    """Safe fallback: never invents card identity when no vision provider is configured."""
    extracted: dict[str, dict[str, Any]] = {}
    for field in IDENTITY_FIELDS:
        if field in locked and locked[field] not in (None, ""):
            extracted[field] = _guess(locked[field], 1.0, "Vom Nutzer im Fast-Scan-Kontext festgelegt.")
        else:
            extracted[field] = _guess(None, 0.0, "Nicht sicher erkannt; Bestätigung erforderlich.")

    required = _requires_confirmation(extracted)
    known = [f for f in CRITICAL_FIELDS if extracted.get(f, {}).get("confidence", 0) >= AUTO_ACCEPT_THRESHOLDS.get(f, 0.95)]
    return {
        "overall_confidence": round(len(known) / len(CRITICAL_FIELDS), 3),
        "extracted": extracted,
        "instance_extracted": {f: _guess(None, 0.0, "Nicht sicher erkannt; Bestätigung erforderlich.") for f in INSTANCE_SCAN_FIELDS},
        "candidates": [],
        "requires_confirmation": required,
        "warnings": ["Vision-Provider nicht aktiv. Es werden keine Kartendetails geraten."],
        "mode": "safe-scaffold",
    }


def _requires_confirmation(extracted: dict[str, dict[str, Any]]) -> list[str]:
    required: list[str] = []
    for field in CRITICAL_FIELDS + ["variation_name", "serial_print_run"]:
        item = extracted.get(field) or {}
        value = item.get("value")
        conf = float(item.get("confidence") or 0)
        threshold = AUTO_ACCEPT_THRESHOLDS.get(field, 0.95)
        # Variation can legitimately be empty; critical identity fields cannot.
        if field == "variation_name" and value in (None, ""):
            continue
        if value in (None, "") or conf < threshold:
            required.append(field)
    return sorted(set(required))


def _data_url(path: str) -> str:
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _json_schema() -> dict[str, Any]:
    string_fields = {
        "sport", "league", "season", "manufacturer", "brand", "product_line", "set_name",
        "subset_name", "insert_name", "checklist_group", "card_number_printed", "card_number_normalized",
        "primary_subject_name", "team_name", "team_city", "country", "position", "parallel_name",
        "parallel_family", "parallel_color", "variation_name", "variation_code", "refractor_prizm_type",
        "rookie_label_text", "autograph_type", "relic_type", "stated_odds", "orientation",
        "card_stock_notes", "finish_notes",
    }
    bool_fields = {
        "is_rookie", "is_insert", "is_short_print", "is_super_short_print", "is_case_hit",
        "is_autograph", "is_relic", "is_rpa", "is_booklet", "is_die_cut", "is_redemption",
        "is_serial_numbered",
    }
    int_fields = {"release_year", "serial_print_run", "known_print_run"}

    def value_schema(field: str) -> dict[str, Any]:
        if field == "secondary_subject_names":
            return {"type": ["array", "null"], "items": {"type": "string"}}
        if field in bool_fields:
            return {"type": ["boolean", "null"]}
        if field in int_fields:
            return {"type": ["integer", "null"]}
        if field in string_fields:
            return {"type": ["string", "null"]}
        return {"type": ["string", "number", "boolean", "null"]}

    def guess_schema(field: str) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "value": value_schema(field),
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": ["string", "null"]},
            },
            "required": ["value", "confidence", "evidence"],
        }

    props = {f: guess_schema(f) for f in IDENTITY_FIELDS}
    instance_types = {
        "raw_or_graded": {"type": ["string", "null"]},
        "grading_company": {"type": ["string", "null"]},
        "grade_numeric": {"type": ["number", "null"]},
        "grade_label": {"type": ["string", "null"]},
        "cert_number": {"type": ["string", "null"]},
        "serial_number_actual": {"type": ["string", "null"]},
    }
    instance_props = {}
    for field in INSTANCE_SCAN_FIELDS:
        instance_props[field] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "value": instance_types[field],
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": ["string", "null"]},
            },
            "required": ["value", "confidence", "evidence"],
        }

    # Strict Structured Outputs: every declared object property is required and unknown values are null.
    return {
        "name": "sports_card_identification",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "extracted": {
                    "type": "object", "additionalProperties": False,
                    "properties": props, "required": IDENTITY_FIELDS,
                },
                "instance_extracted": {
                    "type": "object", "additionalProperties": False,
                    "properties": instance_props, "required": INSTANCE_SCAN_FIELDS,
                },
                "candidates": {
                    "type": "array", "maxItems": 5,
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "properties": {
                            "card_identity_id": {"type": ["string", "null"]},
                            "display_name": {"type": "string"},
                            "score": {"type": "number", "minimum": 0, "maximum": 1},
                            "differences": {"type": "array", "items": {"type": "string"}},
                            # JSON schema strict mode cannot safely allow arbitrary properties here.
                            # Store overrides as JSON text and normalize after parsing.
                            "field_overrides_json": {"type": "string"},
                        },
                        "required": ["card_identity_id", "display_name", "score", "differences", "field_overrides_json"],
                    },
                },
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["overall_confidence", "extracted", "instance_extracted", "candidates", "warnings"],
        },
    }


def _prompt(locked: dict[str, Any]) -> str:
    return f"""You identify physical sports trading cards from front/back photos.
Accuracy is more important than filling every field. Never invent a market price or monetary value.

Rules:
1. Treat locked_context as user-confirmed facts. Copy them with confidence 1.0 and do not contradict them.
2. Use visible text on BOTH sides as primary evidence: card number, copyright/release text, brand/product/set names, player/team, RC logos, serial numbering, autograph/relic labels.
3. Distinguish Base vs Parallel vs Variation conservatively. If a color/finish/parallel cannot be proven, return null or low confidence instead of guessing.
4. For serial-numbered cards, distinguish print run (e.g. /99) from the owned copy number (e.g. 17/99). serial_print_run is only the denominator; serial_number_actual belongs in instance_extracted (e.g. 17/99).
5. If the card is in a visible grading slab, extract grading company, numeric/label grade and certificate number into instance_extracted. Otherwise raw_or_graded should be raw when clearly unslabbed.
6. Do not infer a season from copyright year alone if ambiguous.
7. Keep insert_name/subset_name/set_name/product_line separate.
8. Candidate list should contain plausible alternate identities only when ambiguity is real, especially parallel/variation ambiguity. Each candidate must put only differing fields into field_overrides_json as a compact JSON string (for example {"parallel_name":"Silver Prizm"}).
9. Evidence should be short and concrete (e.g. 'back shows #123', 'front RC shield', 'back copyright 2024 Panini').
10. Unknown values must be null, not placeholders.
11. Boolean fields default false only when absence is reasonably observable; otherwise use low confidence.

locked_context:
{json.dumps(locked, ensure_ascii=False)}
"""


def analyze_with_openai(front_path: str, back_path: str | None, locked: dict[str, Any]) -> dict[str, Any]:
    """Calls OpenAI vision using a strict JSON schema. Requires OPENAI_API_KEY."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed") from exc

    client = OpenAI(api_key=settings.openai_api_key)
    content: list[dict[str, Any]] = [{"type": "input_text", "text": _prompt(locked)}]
    front_for_vision = prepare_for_vision(front_path)
    detail = "original" if settings.openai_vision_model.startswith("gpt-5.6") else "high"
    content.append({"type": "input_image", "image_url": _data_url(front_for_vision), "detail": detail})
    if back_path:
        back_for_vision = prepare_for_vision(back_path)
        content.append({"type": "input_image", "image_url": _data_url(back_for_vision), "detail": detail})

    response = client.responses.create(
        model=settings.openai_vision_model,
        input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_schema", **_json_schema()}},
    )
    raw = response.output_text
    data = json.loads(raw)
    for candidate in data.get("candidates", []):
        raw_overrides = candidate.pop("field_overrides_json", "{}")
        try:
            candidate["field_overrides"] = json.loads(raw_overrides) if raw_overrides else {}
        except json.JSONDecodeError:
            candidate["field_overrides"] = {}

    # Enforce user locks regardless of provider output.
    for field, value in locked.items():
        if field in data.get("extracted", {}) and value not in (None, ""):
            data["extracted"][field] = _guess(value, 1.0, "Vom Nutzer im Fast-Scan-Kontext festgelegt.")

    data["requires_confirmation"] = _requires_confirmation(data.get("extracted", {}))
    data["mode"] = "openai-vision"
    return data


def analyze_images(front_path: str, back_path: str | None, locked: dict[str, Any]) -> dict[str, Any]:
    provider = (settings.recognition_provider or "safe").lower()
    if provider == "openai" and settings.openai_api_key:
        try:
            return analyze_with_openai(front_path, back_path, locked)
        except Exception as exc:
            fallback = analyze_locked_context(locked)
            msg = str(exc).replace(settings.openai_api_key or "", "[REDACTED]")[:500]
            fallback["warnings"].append(f"Vision-Analyse fehlgeschlagen; Safe-Modus aktiv: {type(exc).__name__}: {msg}")
            fallback["mode"] = "safe-fallback"
            return fallback
    return analyze_locked_context(locked)
