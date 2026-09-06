"""FastAPI app: sizing API, wrapping the unchanged ``powertool`` engine.

M0/M1 scope: catalogue, Stage-1 solve and the diagram solve, plus serving the
built frontend (``frontend/dist``) when it exists. M4 adds Projects/Designs
persistence (SQLite by default, no auth yet).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from powertool import ComponentDatabase, size_generation

from .models import Base, Design, Project, check_schema, make_engine, make_session_factory
from .schemas import (
    BessSolutionInfo,
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
    report_pdf,
    solve_diagram,
)

# Stage-2 planning constant inherited from the deleted Streamlit UI — used only
# for the catalogue's default-rules payload in M0 (no /solve endpoint yet).
MAX_CIRCUIT_CURRENT_A = 400.0

db = ComponentDatabase.load()

engine = make_engine()
SessionLocal = make_session_factory(engine)
Base.metadata.create_all(engine)
check_schema(engine)

app = FastAPI(title="Plant Sizing API")

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


def _transformer_info(key: str, tx, paired_solutions: dict[str, int] | None = None) -> TransformerInfo:
    return TransformerInfo(
        key=key,
        display_name=tx.display_name,
        s_rated_kva_at_40c=tx.s_rated_kva_at_40c,
        s_rated_kva_at_30c=tx.s_rated_kva_at_30c,
        hv_kv=tx.hv_kv,
        lv_kv=tx.lv_kv,
        brand=tx.brand,
        uk_percent=tx.uk_percent,
        pk_kw=tx.pk_kw,
        p0_kw=tx.p0_kw,
        i0_percent=tx.i0_percent,
        model=tx.model,
        vector_group=tx.vector_group,
        cooling=tx.cooling,
        datasheet_url=tx.datasheet_url,
        mv_kv_min=tx.mv_kv_min,
        mv_kv_max=tx.mv_kv_max,
        lv_winding_count=tx.lv_winding_count,
        insulation_level=tx.insulation_level,
        f_nominal=tx.f_nominal,
        uk_tolerance_pct=tx.uk_tolerance_pct,
        winding_material_mv=tx.winding_material_mv,
        winding_material_lv=tx.winding_material_lv,
        ip_rating_transformer=tx.ip_rating_transformer,
        ip_rating_enclosure=tx.ip_rating_enclosure,
        rmu_kv_min=tx.rmu_kv_min,
        rmu_kv_max=tx.rmu_kv_max,
        rmu_rated_current_a=tx.rmu_rated_current_a,
        rmu_units=tx.rmu_units,
        rmu_relay_protection=tx.rmu_relay_protection,
        rmu_short_time_withstand=tx.rmu_short_time_withstand,
        cabinet_protection=tx.cabinet_protection,
        surge_protection=tx.surge_protection,
        ac_insulation_detection=tx.ac_insulation_detection,
        cabinet_temp_control=tx.cabinet_temp_control,
        ups=tx.ups,
        width_mm=tx.width_mm,
        height_mm=tx.height_mm,
        depth_mm=tx.depth_mm,
        weight_kg=tx.weight_kg,
        cable_entry=tx.cable_entry,
        corrosion_class=tx.corrosion_class,
        temp_min_c=tx.temp_min_c,
        temp_max_c=tx.temp_max_c,
        humidity_min_pct=tx.humidity_min_pct,
        humidity_max_pct=tx.humidity_max_pct,
        altitude_max_m=tx.altitude_max_m,
        communication=tx.communication,
        standards=tx.standards,
        datasheet_version=tx.datasheet_version,
        preliminary=tx.preliminary,
        paired_solutions=paired_solutions or {},
    )


@app.get("/api/catalogue", response_model=CatalogueResponse)
def get_catalogue() -> CatalogueResponse:
    transformers = [_transformer_info(key, tx) for key, tx in db.transformers.items()]
    bess_transformers = [
        _transformer_info(key, tx, db.bess_pairings.get(key))
        for key, tx in db.bess_transformers.items()
    ]
    bess_solutions = [
        BessSolutionInfo(
            key=key,
            display_name=sol.display_name,
            brand=sol.brand,
            series=sol.series,
            model=sol.model,
            e_nominal_kwh=sol.e_nominal_kwh,
            pcs_s_kva=sol.pcs_s_kva,
            pcs_count=sol.pcs_count,
            pcs_lv_kv=sol.pcs_lv_kv,
            duration_h=sol.duration_h,
            aux_p_kw=sol.aux_p_kw,
            aux_q_kvar=sol.aux_q_kvar,
            datasheet_version=sol.datasheet_version,
            preliminary=sol.preliminary,
            datasheet_url=sol.datasheet_url,
            cell_type=sol.cell_type,
            dc_v_min=sol.dc_v_min,
            dc_v_max=sol.dc_v_max,
            ac_v_min=sol.ac_v_min,
            ac_v_max=sol.ac_v_max,
            ac_i_a=sol.ac_i_a,
            pf_at_nominal=sol.pf_at_nominal,
            q_range_percent=sol.q_range_percent,
            f_nominal_hz=sol.f_nominal_hz,
            thdi_percent=sol.thdi_percent,
            isolation=sol.isolation,
            width_mm=sol.width_mm,
            height_mm=sol.height_mm,
            depth_mm=sol.depth_mm,
            weight_kg=sol.weight_kg,
            ip_rating=sol.ip_rating,
            corrosion_class=sol.corrosion_class,
            temp_min_c=sol.temp_min_c,
            temp_max_c=sol.temp_max_c,
            humidity_min_pct=sol.humidity_min_pct,
            humidity_max_pct=sol.humidity_max_pct,
            altitude_max_m=sol.altitude_max_m,
            cooling=sol.cooling,
        )
        for key, sol in db.bess_solutions.items()
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

    return CatalogueResponse(
        transformers=transformers, cables=cables, defaults=defaults,
        bess_solutions=bess_solutions, bess_transformers=bess_transformers,
    )


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
    result = size_generation(chain, p_poc_kw=req.p_poc_kw, pf_target=req.pf_target)

    return Stage1Response(
        p_inv_kw=result.p_inv_kw,
        q_inv_kvar=result.q_inv_kvar,
        s_inv_kva=result.s_inv_kva,
        pf_inv=result.pf_inv,
        losses=[LossItem(label=e.name or "", dp_kw=e.dp_kw, dq_kvar=e.dq_kvar) for e in result.losses],
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


def _filename_slug(name: str) -> str:
    """Filename-safe slug for the Content-Disposition header — the plant name
    reaches us from the client, so it never goes into a header verbatim."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    return (cleaned or "plant")[:60]


@app.post("/api/report")
def post_report(diagram: dict = Body(...), name: str = "Plant") -> Response:
    """Download the PDF sizing report for a drawn diagram.

    Body is the diagram payload (as for /api/solve); ``name`` titles the report
    and names the file. A diagram that cannot be solved is a 400 carrying the
    reason, since there is no partial report worth downloading.
    """
    try:
        pdf = report_pdf(diagram, db, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{_filename_slug(name)}-sizing-report.pdf"'
        },
    )


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
        technology=body.technology,
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


# Serve the built frontend, if present. Guarded so the API still works before
# the first `npm run build`. Catch-all route for SPA fallback: serves actual
# files when they exist, otherwise returns index.html for client-side routing.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():

    @app.get("/{path:path}")
    def serve_frontend(path: str) -> FileResponse:
        """Serve the built SPA frontend with fallback to index.html.

        For any GET request not matching /api routes and not an existing static
        asset, return the frontend's index.html to enable client-side routing.
        Protects against path traversal via Path.resolve().is_relative_to().
        """
        # API routes that don't exist should 404, not fall back to index.html
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        # Construct the full file path
        requested_path = (_FRONTEND_DIST / path).resolve()

        # Security: ensure the resolved path is within dist
        if not requested_path.is_relative_to(_FRONTEND_DIST):
            raise HTTPException(status_code=404, detail="Not found")

        # Serve the file if it exists
        if requested_path.is_file():
            return FileResponse(requested_path)

        # Otherwise, fall back to index.html for client-side routing
        return FileResponse(_FRONTEND_DIST / "index.html")
