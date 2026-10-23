"""The BESS efficiency run: weather-dependent round-trip efficiency at the POC.

For each ``(timestamp, ambient °C)`` row this evaluates one efficiency run
(CONTEXT.md's "Efficiency run") and reports the operating round-trip efficiency
at the point of connection, the idle loss and the PCS power available. Each row
is evaluated independently; timestamps are echoed verbatim. Warnings are
returned separately from the rows.

Spec: .scratch/rte-efficiency/spec.md. Curve lookup follows ADR-0009.

This module has no web or UI dependency. Not yet implemented (later tickets):
the idle figure (``idle_loss_pct`` is None), interpolation between
cycles-per-day references, and a run from a solved design.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from .components import AuxConsumptionTable, BessSolution, DeratingCurve, mvs_aux_band
from .database import ComponentDatabase


class EfficiencyRunError(ValueError):
    """The efficiency run's configuration is invalid; nothing was computed."""


@dataclass(frozen=True)
class TypedConfiguration:
    """An efficiency run's configuration when there is no design: everything
    typed by the caller. Loss percentages are of the fleet's rated active power
    (containers x Pn); the load loss is at full power and scales with the
    square of power below it."""

    solution: str                      # BESS solution catalogue key
    station_transformer: str           # paired BESS station transformer key
    stations: int
    containers: int
    poc_capacity_kw: float
    load_loss_pct: float
    no_load_loss_pct: float
    cycles_per_day: float | None = None
    cell_rte_pct: float | None = None  # None: the solution's catalogue default


@dataclass(frozen=True)
class EfficiencyRow:
    """One output row. ``idle_loss_pct`` is None until the idle figure is
    implemented; ``pcs_power_pct`` is the PCS power available at the row's
    ambient (100 unless derated), a power cap, never a loss."""

    timestamp: str
    operating_rte_pct: float
    idle_loss_pct: float | None
    pcs_power_pct: float


@dataclass
class EfficiencyResult:
    rows: list[EfficiencyRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Fleet:
    """The resolved, validated configuration the per-row physics runs on."""

    solution: BessSolution
    containers: int
    stations: int
    poc_capacity_kw: float
    rated_kw: float           # fleet rated active power, N x Pn
    load_loss_coeff: float    # a in load loss = a x P^2 [1/kW]
    no_load_kw: float
    eta: float                # one-way conversion efficiency
    rho: float                # cell round-trip efficiency
    aux_table: AuxConsumptionTable
    mvs_bands: tuple          # empty: no MVS table, counted as zero
    derating: DeratingCurve | None  # None: no curve, 100 % of rated power
    ambient_range_c: tuple[float, float]  # published range every curve covers

    def derating_at(self, ambient_c: float) -> float:
        """Fraction of rated active power available at ``ambient_c``."""
        return self.derating.fraction_at(ambient_c) if self.derating else 1.0


def _resolve(config: TypedConfiguration, db: ComponentDatabase) -> tuple[_Fleet, list[str]]:
    warnings: list[str] = []
    try:
        solution = db.bess_solution(config.solution)
        transformer = db.bess_transformer(config.station_transformer)
    except KeyError as exc:
        raise EfficiencyRunError(exc.args[0]) from None

    pn = solution.rated_active_power_kw
    if pn is None:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} publishes no rated active power; "
            "it cannot be used in an efficiency run (ADR-0008 amendment)")
    per_station = db.bess_pairings.get(config.station_transformer, {}).get(config.solution)
    if per_station is None:
        raise EfficiencyRunError(
            f"station transformer {config.station_transformer!r} is not paired with "
            f"BESS solution {config.solution!r}")
    if config.stations < 1 or config.containers < 1:
        raise EfficiencyRunError("station and container counts must be at least 1")
    if config.containers > config.stations * per_station:
        raise EfficiencyRunError(
            f"{config.containers} containers exceed {config.stations} stations x "
            f"{per_station} containers per station")
    rated_kw = config.containers * pn
    if config.poc_capacity_kw <= 0:
        raise EfficiencyRunError("POC capacity must be positive")
    if config.poc_capacity_kw >= rated_kw:
        raise EfficiencyRunError(
            f"POC capacity {config.poc_capacity_kw:g} kW must be below the installed "
            f"rated active power {rated_kw:g} kW")
    if config.load_loss_pct < 0 or config.no_load_loss_pct < 0:
        raise EfficiencyRunError("loss percentages must not be negative")

    if not solution.aux_consumption:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} publishes no auxiliary-consumption table")
    eta = solution.conversion_efficiency
    if eta is None:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} publishes no conversion efficiency")
    rho_pct = config.cell_rte_pct if config.cell_rte_pct is not None else solution.cell_rte_pct
    if rho_pct is None:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} has no cell RTE default; give one")
    if not 0 < rho_pct <= 100:
        raise EfficiencyRunError("cell RTE must be in (0, 100] %")

    # Nearest published cycles-per-day reference (interpolation between
    # references is a later ticket).
    cycles = config.cycles_per_day
    aux_table = min(solution.aux_consumption,
                    key=lambda t: abs(t.cycles_per_day - cycles) if cycles is not None else 0)

    if not transformer.mvs_aux_consumption:
        warnings.append(
            f"station transformer {config.station_transformer!r} publishes no MVS "
            "auxiliary-consumption table; counted as zero")

    # The published ambient range: where the container tables and the
    # derating curve all have points. Outside it the run clamps (ADR-0009).
    curves = [t.ambient_c for t in solution.aux_consumption]
    if solution.derating is not None:
        curves.append(solution.derating.ambient_c)
    ambient_range_c = (max(c[0] for c in curves), min(c[-1] for c in curves))

    if solution.derating is None:
        warnings.append(
            f"BESS solution {config.solution!r} publishes no PCS derating curve; "
            "run at 100 % of rated active power at every ambient")

    return _Fleet(
        solution=solution,
        containers=config.containers,
        stations=config.stations,
        poc_capacity_kw=float(config.poc_capacity_kw),
        rated_kw=rated_kw,
        load_loss_coeff=config.load_loss_pct / 100.0 / rated_kw,
        no_load_kw=config.no_load_loss_pct / 100.0 * rated_kw,
        eta=eta,
        rho=rho_pct / 100.0,
        aux_table=aux_table,
        mvs_bands=transformer.mvs_aux_consumption,
        derating=solution.derating,
        ambient_range_c=ambient_range_c,
    ), warnings


def _ac_for_export(a: float, export_kw: float) -> float:
    """AC power at the container terminals whose output, after load losses
    a x P^2, is ``export_kw``: the smaller root of a P^2 - P + export = 0."""
    if a == 0:
        return export_kw
    return (1 - math.sqrt(1 - 4 * a * export_kw)) / (2 * a)


def _ac_from_import(a: float, available_kw: float) -> float:
    """AC power into the containers when ``available_kw`` enters the loss
    chain from the POC side: the root of P + a x P^2 = available."""
    if a == 0:
        return available_kw
    return (-1 + math.sqrt(1 + 4 * a * available_kw)) / (2 * a)


def _operating_rte(fleet: _Fleet, ambient_c: float) -> float:
    """One efficiency run at the full power available at ``ambient_c``
    (rated, or derated: same energy over a longer cycle); returns RTE at the
    POC as a fraction. Derating is never counted as a loss (ticket 04)."""
    a = fleet.load_loss_coeff
    aux_kw = fleet.containers * fleet.aux_table.operating_kw_at(ambient_c)
    if fleet.mvs_bands:
        aux_kw += fleet.stations * mvs_aux_band(fleet.mvs_bands, ambient_c).operating_kw
    fixed_kw = fleet.no_load_kw + aux_kw            # drawn over both legs
    energy_dc_kwh = fleet.containers * fleet.solution.e_nominal_kwh

    # Discharge: rated power at the AC terminals, unless the export would
    # exceed the POC capacity (ticket 11); then AC power drops until it equals it.
    p_full = fleet.rated_kw * fleet.derating_at(ambient_c)
    p_ac = p_full
    export_kw = p_ac - a * p_ac ** 2 - fixed_kw
    if export_kw > fleet.poc_capacity_kw:
        p_ac = _ac_for_export(a, fleet.poc_capacity_kw + fixed_kw)
        export_kw = fleet.poc_capacity_kw
    discharge_h = energy_dc_kwh * fleet.eta / p_ac

    # Charge: import the lesser of the POC capacity and what drives the PCS at
    # its (derated) power; walk inward to the AC power into the containers. The
    # cycle closes: the DC side takes back the discharged energy over cell RTE.
    import_kw = min(fleet.poc_capacity_kw, p_full + a * p_full ** 2 + fixed_kw)
    p_in = _ac_from_import(a, import_kw - fixed_kw)
    charge_h = (energy_dc_kwh / fleet.rho) / (p_in * fleet.eta)

    return (export_kw * discharge_h) / (import_kw * charge_h)


@dataclass
class _AmbientClamp:
    """Clamps each row's ambient to the published range once, so every figure
    of the row reads the same clamped ambient, and reports the clamping as one
    warning for the whole run."""

    low_c: float
    high_c: float
    clamped: list[float] = field(default_factory=list)

    def __call__(self, ambient_c: float) -> float:
        if self.low_c <= ambient_c <= self.high_c:
            return ambient_c
        self.clamped.append(ambient_c)
        return min(max(ambient_c, self.low_c), self.high_c)

    def warning(self) -> str | None:
        if not self.clamped:
            return None
        n = len(self.clamped)
        return (f"{n} timestamp{'s' if n != 1 else ''} had an ambient outside the "
                f"published range {self.low_c:g} to {self.high_c:g} °C (coldest seen "
                f"{min(self.clamped):g} °C, hottest seen {max(self.clamped):g} °C); "
                "clamped to the nearest edge")


def run_efficiency(
    rows: Iterable[tuple[str, float]],
    config: TypedConfiguration,
    db: ComponentDatabase,
) -> EfficiencyResult:
    """Evaluate one efficiency run per ``(timestamp, ambient °C)`` row.

    Raises :class:`EfficiencyRunError` for an invalid configuration. Warnings
    (e.g. a missing MVS table) are returned on the result, never in the rows.
    """
    fleet, warnings = _resolve(config, db)
    result = EfficiencyResult(warnings=warnings)
    clamp = _AmbientClamp(*fleet.ambient_range_c)
    for timestamp, ambient_c in rows:
        ambient_c = clamp(float(ambient_c))
        result.rows.append(EfficiencyRow(
            timestamp=timestamp,
            operating_rte_pct=_operating_rte(fleet, ambient_c) * 100.0,
            idle_loss_pct=None,
            pcs_power_pct=fleet.derating_at(ambient_c) * 100.0,
        ))
    clamp_warning = clamp.warning()
    if clamp_warning is not None:
        result.warnings.append(clamp_warning)
    return result
