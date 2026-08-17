from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field

class CardIdentityIn(BaseModel):
    sport: str
    league: str | None = None
    season: str | None = None
    release_year: int | None = None
    manufacturer: str | None = None
    brand: str | None = None
    product_line: str | None = None
    set_name: str | None = None
    subset_name: str | None = None
    insert_name: str | None = None
    checklist_group: str | None = None
    card_number_printed: str | None = None
    card_number_normalized: str | None = None
    primary_subject_name: str
    secondary_subject_names: list[str] = Field(default_factory=list)
    team_name: str | None = None
    team_city: str | None = None
    country: str | None = None
    position: str | None = None
    parallel_name: str | None = None
    parallel_family: str | None = None
    parallel_color: str | None = None
    variation_name: str | None = None
    variation_code: str | None = None
    refractor_prizm_type: str | None = None
    is_rookie: bool = False
    rookie_label_text: str | None = None
    is_insert: bool = False
    is_short_print: bool = False
    is_super_short_print: bool = False
    is_case_hit: bool = False
    is_autograph: bool = False
    autograph_type: str | None = None
    is_relic: bool = False
    relic_type: str | None = None
    is_rpa: bool = False
    is_booklet: bool = False
    is_die_cut: bool = False
    is_redemption: bool = False
    is_serial_numbered: bool = False
    serial_print_run: int | None = None
    known_print_run: int | None = None
    stated_odds: str | None = None
    orientation: str | None = None
    card_stock_notes: str | None = None
    finish_notes: str | None = None

class OwnedInstanceIn(BaseModel):
    quantity: int = Field(default=1, ge=1)
    raw_or_graded: str = "raw"
    raw_condition: str | None = None
    grading_company: str | None = None
    grade_numeric: float | None = None
    grade_label: str | None = None
    cert_number: str | None = None
    serial_number_actual: str | None = None
    acquired_date: date | None = None
    acquired_price: float | None = None
    acquired_currency: str | None = None
    acquired_from: str | None = None
    storage_location: str | None = None
    personal_tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    favorite: bool = False
    front_image_path: str | None = None
    back_image_path: str | None = None

class CardCreateRequest(BaseModel):
    identity: CardIdentityIn
    instance: OwnedInstanceIn = Field(default_factory=OwnedInstanceIn)

class ManualCompIn(BaseModel):
    source: str
    source_url: str | None = None
    sold_at: datetime | None = None
    price: float = Field(gt=0)
    currency: str
    shipping_price: float | None = None
    raw_or_graded: str = "raw"
    grading_company: str | None = None
    grade_numeric: float | None = None
    title_raw: str | None = None
    matched_identity_confidence: float = Field(default=1.0, ge=0, le=1)
    included_in_valuation: bool = True
    exclusion_reason: str | None = None

class FieldGuess(BaseModel):
    value: Any | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: str | None = None

class Candidate(BaseModel):
    card_identity_id: str | None = None
    display_name: str
    score: float = Field(ge=0, le=1)
    differences: list[str] = Field(default_factory=list)
    field_overrides: dict[str, Any] = Field(default_factory=dict)

class ScanResponse(BaseModel):
    scan_id: str
    overall_confidence: float
    extracted: dict[str, FieldGuess]
    instance_extracted: dict[str, FieldGuess] = Field(default_factory=dict)
    candidates: list[Candidate]
    requires_confirmation: list[str]
    warnings: list[str] = Field(default_factory=list)
    mode: str
    catalog_matches: list[dict] = Field(default_factory=list)

class ConfirmScanRequest(BaseModel):
    scan_id: str
    identity: CardIdentityIn
    instance: OwnedInstanceIn = Field(default_factory=OwnedInstanceIn)

class AutoConfirmScanRequest(BaseModel):
    scan_id: str
    allow_uncertain: bool = False

class ValuationOut(BaseModel):
    reliable: bool
    comp_count: int
    currency: str | None = None
    median_value: float | None = None
    mean_value: float | None = None
    low_value: float | None = None
    high_value: float | None = None
    reason: str
