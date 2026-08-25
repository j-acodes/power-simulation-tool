"""FastAPI app: sizing API, wrapping the unchanged ``powertool`` engine.

M0/M1 scope: catalogue, Stage-1 solve and the diagram solve, plus serving the
built frontend (``frontend/dist``) when it exists. M4 adds Projects/Designs
persistence (SQLite by default, no auth yet).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from powertool import ComponentDatabase, size_pv_inverters

from .models import Base, Design, Project, make_engine, make_session_factory
from .schemas import (
    CableInfo,
    CatalogueDefaults,
    CatalogueResponse,
    DesignCreate,
    DesignFull,
    DesignSummary,
    DesignUpdate,
    LossItem,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    RulesDefaults,
    SeedRequest,
    SolveResponse,
    Stage1Request,
    Stage1Response,
    TiersDefaults,
    TransformerInfo,
)
from .seed import seed_diagram
from .solve import (
    COLLECTION_LOSS_PCT,
    EXPORT_LOSS_PCT_PER_KM,
    MAX_UTILIZATION,
    build_chain,
    solve_diagram,
)

# Stage-2 planning constant mirrored from app/streamlit_app.py — used only for
# the catalogue's default-rules payload in M0 (no /solve endpoint yet).
MAX_CIRCUIT_CURRENT_A = 400.0

db = ComponentDatabase.load()

engine = make_engine()
SessionLocal = make_session_factory(engine)
Base.metadata.create_all(engine)

app = FastAPI(title="PV Plant Sizing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.get("/api/catalogue", response_model=CatalogueResponse)
def get_catalogue() -> CatalogueResponse:
    transformers = [
        TransformerInfo(
            key=key,
            display_name=tx.display_name,
            s_rated_kva=tx.s_rated_kva,
            hv_kv=tx.hv_kv,
            lv_kv=tx.lv_kv,
            brand=tx.brand,
            uk_percent=tx.uk_percent,
            pk_kw=tx.pk_kw,
            p0_kw=tx.p0_kw,
            i0_percent=tx.i0_percent,
        )
        for key, tx in db.transformers.items()
    ]

    cables: dict[str, list[CableInfo]] = {}
    for cable in sorted(
        db.cables.values(),
        key=lambda c: (c.rated_voltage_kv is None, c.rated_voltage_kv or 0.0, c.cross_section_mm2 or 0.0),
    ):
        if cable.rated_voltage_kv is None:
            continue
        group = f"{cable.rated_voltage_kv:g}"
        cables.setdefault(group, []).append(
            CableInfo(
                name=cable.name,
                cross_section_mm2=cable.cross_section_mm2,
                rated_current_a=cable.rated_current_a,
            )
        )

    defaults = CatalogueDefaults(
        tiers=TiersDefaults(lv_kv=0.8, mv_kv=20.0, hv_kv=132.0),
        rules=RulesDefaults(
            max_utilization=MAX_UTILIZATION,
            collection_loss_pct=COLLECTION_LOSS_PCT,
            export_loss_pct_per_km=EXPORT_LOSS_PCT_PER_KM,
            max_circuit_current_a=MAX_CIRCUIT_CURRENT_A,
        ),
    )

    return CatalogueResponse(transformers=transformers, cables=cables, defaults=defaults)


@app.post("/api/stage1", response_model=Stage1Response)
def post_stage1(req: Stage1Request) -> Stage1Response:
    elements = [el.model_dump() for el in req.elements]
    chain = build_chain(
        elements,
        db,
        interconnection=req.interconnection,
        v_export_kv=req.v_export_kv,
        export_m=req.export_m,
        p_poc_kw=req.p_poc_kw,
        pf_target=req.pf_target,
    )
    result = size_pv_inverters(chain, p_poc_kw=req.p_poc_kw, pf_target=req.pf_target)

    return Stage1Response(
        p_inv_kw=result.p_inv_kw,
        q_inv_kvar=result.q_inv_kvar,
        s_inv_kva=result.s_inv_kva,
        pf_inv=result.pf_inv,
        losses=[LossItem(label=e.name, dp_kw=e.dp_kw, dq_kvar=e.dq_kvar) for e in result.losses],
        power_balance_ok=result.power_balance_ok,
    )


@app.post("/api/solve", response_model=SolveResponse)
def post_solve(diagram: dict = Body(...)) -> SolveResponse:
    """Solve a drawn diagram — the request body IS the diagram payload.

    Serves both the live validation and the debounced auto-solve of the editor,
    so it always answers 200: a drawing that cannot be solved comes back as
    ``issues`` keyed to the offending nodes/edges. The diagram is taken as a
    plain dict on purpose — its schema is validated by ``powertool.graph``,
    which reports problems as issues instead of raising 422s at the user.
    """
    return SolveResponse(**solve_diagram(diagram, db))


@app.post("/api/seed")
def post_seed(req: SeedRequest) -> dict:
    """Seed wizard: POC-level params -> a proposed diagram the user rearranges.

    Returns the diagram dict itself (see ``powertool.graph`` for the schema),
    not a wrapped response — the editor loads it onto the canvas exactly as it
    would load a saved design.
    """
    return seed_diagram(req.model_dump(), db)


@app.get("/api/projects", response_model=list[ProjectSummary])
def list_projects(session: Session = Depends(get_session)) -> list[ProjectSummary]:
    rows = session.execute(
        select(Project, func.count(Design.id))
        .outerjoin(Design, Design.project_id == Project.id)
        .group_by(Project.id)
        .order_by(Project.id)
    ).all()
    return [
        ProjectSummary(id=p.id, name=p.name, created_at=p.created_at, design_count=count)
        for p, count in rows
    ]


@app.post("/api/projects", response_model=ProjectSummary, status_code=201)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)) -> ProjectSummary:
    project = Project(name=body.name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return ProjectSummary(id=project.id, name=project.name, created_at=project.created_at, design_count=0)


@app.get("/api/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, session: Session = Depends(get_session)) -> ProjectDetail:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    designs = session.execute(
        select(Design).where(Design.project_id == project_id).order_by(Design.id)
    ).scalars().all()
    return ProjectDetail(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        designs=[DesignSummary.model_validate(d) for d in designs],
    )


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, session: Session = Depends(get_session)) -> None:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    session.execute(delete(Design).where(Design.project_id == project_id))
    session.delete(project)
    session.commit()


@app.post("/api/projects/{project_id}/designs", response_model=DesignFull, status_code=201)
def create_design(
    project_id: int, body: DesignCreate, session: Session = Depends(get_session)
) -> DesignFull:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    design = Design(
        project_id=project_id,
        name=body.name,
        payload=body.payload,
        version=1,
        last_edited_by=body.last_edited_by,
    )
    session.add(design)
    session.commit()
    session.refresh(design)
    return DesignFull.model_validate(design)


@app.get("/api/designs/{design_id}", response_model=DesignFull)
def get_design(design_id: int, session: Session = Depends(get_session)) -> DesignFull:
    design = session.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")
    return DesignFull.model_validate(design)


@app.delete("/api/designs/{design_id}", status_code=204)
def delete_design(design_id: int, session: Session = Depends(get_session)) -> None:
    design = session.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")
    session.delete(design)
    session.commit()


@app.put("/api/designs/{design_id}", response_model=DesignFull)
def update_design(
    design_id: int, body: DesignUpdate, session: Session = Depends(get_session)
) -> DesignFull:
    """Optimistic-locking save: a single ``UPDATE ... WHERE id AND version``.

    0 rows matched means either the design is gone (404) or someone else saved
    first (409, with the server's current copy so the client can show a
    conflict dialog) — we never silently overwrite a concurrent edit.
    """
    existing = session.get(Design, design_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Design not found")

    values: dict = {
        "payload": body.payload,
        "version": Design.version + 1,
        "last_edited_by": body.last_edited_by,
        "updated_at": datetime.now(timezone.utc),
    }
    if body.name is not None:
        values["name"] = body.name

    result = session.execute(
        update(Design).where(Design.id == design_id, Design.version == body.version).values(**values)
    )
    if result.rowcount == 0:
        session.rollback()
        current = session.get(Design, design_id)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Design was modified by someone else — reload and retry.",
                "design": jsonable_encoder(DesignFull.model_validate(current)),
            },
        )

    session.commit()
    session.refresh(existing)
    return DesignFull.model_validate(existing)


# Serve the built frontend, if present. Mounted last so /api routes above take
# precedence; guarded so the API still works before the first `npm run build`.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
