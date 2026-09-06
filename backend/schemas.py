"""Pydantic request/response models for the Stage-1 API.

Element shapes are a discriminated union on ``type``, inherited from the
``st.session_state.elements`` list of the deleted Streamlit UI (read it at
b5fc748 if a field's origin is ever in question).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

# The set of fleet kinds a design is permitted to contain — declared at creation,
# authoritative over the diagram, changed only by cloning. See
# docs/adr/0002-technology-declared-not-derived.md and CONTEXT.md's Technology entry.
Technology = Literal["pv", "bess", "hybrid"]


class TransformerElement(BaseModel):
    type: Literal["Transformer"]
    component: str  # ComponentDatabase.transformers key
    v_kv: float
    n_parallel: int = 1
    label: str | None = None


class CableSectionElement(BaseModel):
    type: Literal["Cable section"]
    v_kv: float
    label: str | None = None


class AuxLoadElement(BaseModel):
    type: Literal["Aux load"]
    v_kv: float
    p_kw: float
    q_kvar: float = 0.0
    label: str | None = None


Element = Annotated[
    Union[TransformerElement, CableSectionElement, AuxLoadElement],
    Field(discriminator="type"),
]


class Stage1Request(BaseModel):
    p_poc_kw: float
    pf_target: float
    interconnection: Literal["HV", "MV"]
    v_export_kv: float
    export_m: float = 0.0
    elements: list[Element]


class LossItem(BaseModel):
    label: str
    dp_kw: float
    dq_kvar: float


class Stage1Response(BaseModel):
    p_inv_kw: float
    q_inv_kvar: float
    s_inv_kva: float
    pf_inv: float
    losses: list[LossItem]
    power_balance_ok: bool


class SeedRequest(BaseModel):
    """Wizard params for ``POST /api/seed`` — see backend.seed.seed_diagram.

    A response is the diagram dict it produces (no response_model: the diagram
    schema lives in ``powertool.graph``, not here).
    """

    p_poc_mw: float
    pf_target: float
    interconnection: Literal["HV", "MV"]
    v_hv_kv: float | None = None
    export_m: float = 0.0
    v_mv_kv: float
    station_model: str
    max_loading: float = 1.0
    trunk_m: float
    spacing_m: float
    max_circuit_current_a: float
    aux_p_kw: float = 0.0
    aux_q_kvar: float = 0.0

    @model_validator(mode="after")
    def _hv_needs_a_voltage(self) -> "SeedRequest":
        if self.interconnection == "HV" and not (self.v_hv_kv and self.v_hv_kv > 0):
            raise ValueError(
                "v_hv_kv is required (and must be positive) for an HV interconnection."
            )
        return self


class IssueItem(BaseModel):
    """One validation problem or result warning, pointing at the canvas element
    that carries it (see powertool.graph.GraphIssue)."""

    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None


class SolveResponse(BaseModel):
    """``issues`` non-empty means nothing was solved (``results`` is null).

    An invalid drawing is an ANSWER, not a failure: /api/solve always returns
    200 so the live editor can render the issues on the canvas.
    """

    issues: list[IssueItem]
    results: dict | None = None


class TransformerInfo(BaseModel):
    key: str
    display_name: str
    s_rated_kva_at_40c: float
    s_rated_kva_at_30c: float | None = None
    hv_kv: float | None
    lv_kv: float | None
    brand: str | None
    uk_percent: float
    pk_kw: float
    p0_kw: float
    i0_percent: float
    # Typed parameters (never computed with) — see CONTEXT.md's "Simulated
    # parameter / typed parameter" entry. Unset for every PV transformer and
    # for the placeholder BESS station transformers.
    model: str | None = None
    vector_group: str | None = None
    cooling: str | None = None
    datasheet_url: str | None = None
    mv_kv_min: float | None = None
    mv_kv_max: float | None = None
    lv_winding_count: int = 1
    insulation_level: str | None = None
    f_nominal: str | None = None
    uk_tolerance_pct: float | None = None
    winding_material_mv: str | None = None
    winding_material_lv: str | None = None
    ip_rating_transformer: str | None = None
    ip_rating_enclosure: str | None = None
    rmu_kv_min: float | None = None
    rmu_kv_max: float | None = None
    rmu_rated_current_a: float | None = None
    rmu_units: str | None = None
    rmu_relay_protection: str | None = None
    rmu_short_time_withstand: str | None = None
    cabinet_protection: str | None = None
    surge_protection: str | None = None
    ac_insulation_detection: str | None = None
    cabinet_temp_control: str | None = None
    ups: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    depth_mm: float | None = None
    weight_kg: float | None = None
    cable_entry: str | None = None
    corrosion_class: str | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humidity_min_pct: float | None = None
    humidity_max_pct: float | None = None
    altitude_max_m: float | None = None
    communication: str | None = None
    standards: str | None = None
    datasheet_version: str | None = None
    preliminary: bool = False
    # BESS solution key -> containers per station: the solutions this station
    # transformer is sold with (data/bess_transformers.yaml's paired_solutions).
    # Always empty for a PV transformer, which has no pairing to carry.
    paired_solutions: dict[str, int] = {}


class CableInfo(BaseModel):
    name: str
    cross_section_mm2: float | None
    rated_current_a: float | None


class BessSolutionInfo(BaseModel):
    key: str
    display_name: str
    brand: str
    series: str
    model: str
    e_nominal_kwh: float
    pcs_s_kva: float
    pcs_count: int
    pcs_lv_kv: float
    duration_h: float
    # None means the datasheet publishes no auxiliary figure — the engine
    # sums it as zero but raises an informational notice; 0.0 means the
    # datasheet states the draw as zero.
    aux_p_kw: float | None
    aux_q_kvar: float | None
    datasheet_version: str | None
    preliminary: bool
    datasheet_url: str | None
    # Typed specification (never computed with) — see CONTEXT.md's "Simulated
    # parameter / typed parameter" entry. All optional: None means the
    # datasheet is silent on that field, not that the value is zero.
    cell_type: str | None = None
    dc_v_min: float | None = None
    dc_v_max: float | None = None
    ac_v_min: float | None = None
    ac_v_max: float | None = None
    ac_i_a: float | None = None
    pf_at_nominal: float | None = None
    q_range_percent: float | None = None
    f_nominal_hz: str | None = None
    thdi_percent: float | None = None
    isolation: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    depth_mm: float | None = None
    weight_kg: float | None = None
    ip_rating: str | None = None
    corrosion_class: str | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humidity_min_pct: float | None = None
    humidity_max_pct: float | None = None
    altitude_max_m: float | None = None
    cooling: str | None = None


class TiersDefaults(BaseModel):
    lv_kv: float
    mv_kv: float
    hv_kv: float


class RulesDefaults(BaseModel):
    max_utilization: float
    collection_loss_pct: float
    export_loss_pct_per_km: float
    max_circuit_current_a: float


class CatalogueDefaults(BaseModel):
    tiers: TiersDefaults
    rules: RulesDefaults


class CatalogueResponse(BaseModel):
    transformers: list[TransformerInfo]
    cables: dict[str, list[CableInfo]]
    defaults: CatalogueDefaults
    bess_solutions: list[BessSolutionInfo]
    bess_transformers: list[TransformerInfo]


# --- Projects / Designs persistence (M4) ---------------------------------


class ProjectCreate(BaseModel):
    name: str


class DesignSummary(BaseModel):
    """A design as listed on a project page — no payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    technology: Technology
    version: int
    last_edited_by: str
    updated_at: datetime


class ProjectSummary(BaseModel):
    id: int
    name: str
    created_at: datetime
    design_count: int


class ProjectDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    designs: list[DesignSummary]


class RuleSettings(BaseModel):
    """The one rule setting with a genuinely closed set of legal values in a
    design's ``settings.rules`` — see ADR-0004 and CONTEXT.md's "AC power at
    ambient" entry. Every other rule is a free number the frontend renders
    with a plain number input; a value outside {30, 40} is never something
    the sizing engine's transformer catalogue could honor, so it is rejected
    here rather than accepted and silently mishandled downstream.

    Not a model of the whole ``rules`` dict — every other field stays
    untyped JSON on ``payload``, exactly as before this setting existed.
    """

    ambient_temp_c: Literal[30.0, 40.0] = 40.0


def _validate_rule_settings(payload: dict) -> None:
    """Raise (a Pydantic ``ValidationError``) if a design payload's
    ``settings.rules.ambient_temp_c`` is set to anything but 30 or 40.

    A payload silent on the field, or shaped unexpectedly (not yet a valid
    diagram at all), is left alone here — that is the engine's own
    ``validate_graph`` job, not this one's.
    """
    settings = payload.get("settings") if isinstance(payload, dict) else None
    rules = settings.get("rules") if isinstance(settings, dict) else None
    if isinstance(rules, dict) and "ambient_temp_c" in rules:
        RuleSettings(ambient_temp_c=rules["ambient_temp_c"])


class DesignCreate(BaseModel):
    name: str
    technology: Technology
    payload: dict
    last_edited_by: str

    @model_validator(mode="after")
    def _ambient_temp_c_is_legal(self) -> "DesignCreate":
        _validate_rule_settings(self.payload)
        return self


class DesignFull(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    technology: Technology
    payload: dict
    version: int
    last_edited_by: str
    created_at: datetime
    updated_at: datetime


class DesignUpdate(BaseModel):
    """Optimistic-locking save: ``version`` must match the server's current
    version or the update is rejected with a 409 (see ``PUT /api/designs/{id}``
    in main.py)."""

    name: str | None = None
    payload: dict
    version: int
    last_edited_by: str

    @model_validator(mode="after")
    def _ambient_temp_c_is_legal(self) -> "DesignUpdate":
        _validate_rule_settings(self.payload)
        return self
