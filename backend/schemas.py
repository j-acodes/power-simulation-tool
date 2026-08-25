"""Pydantic request/response models for the Stage-1 API.

Element shapes mirror ``st.session_state.elements`` in the frozen Streamlit
UI (see ``app/streamlit_app.py``): a discriminated union on ``type``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    s_rated_kva: float
    hv_kv: float | None
    lv_kv: float | None
    brand: str | None
    uk_percent: float
    pk_kw: float
    p0_kw: float
    i0_percent: float


class CableInfo(BaseModel):
    name: str
    cross_section_mm2: float | None
    rated_current_a: float | None


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


# --- Projects / Designs persistence (M4) ---------------------------------


class ProjectCreate(BaseModel):
    name: str


class DesignSummary(BaseModel):
    """A design as listed on a project page — no payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
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


class DesignCreate(BaseModel):
    name: str
    payload: dict
    last_edited_by: str


class DesignFull(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
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
