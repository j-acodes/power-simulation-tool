"""Command-line wrapper around :func:`powertool.efficiency.run_efficiency`.

Reads a CSV of ``timestamp, ambient °C`` (one header row, first two columns
used), writes the four-column efficiency CSV, and prints warnings to stderr,
never into the CSV. Example::

    python -m powertool.efficiency_cli ambient.csv rte.csv \\
        --solution sungrow-st6900ux-4h --station-transformer SUNGROW_MVS7400_LS \\
        --stations 16 --containers 64 --poc-capacity-kw 100000 \\
        --load-loss-pct 1.0 --no-load-loss-pct 0.1 --cycles-per-day 1
"""

from __future__ import annotations

import argparse
import csv
import sys

from .database import ComponentDatabase
from .efficiency import EfficiencyRunError, TypedConfiguration, run_efficiency

OUTPUT_HEADER = ["timestamp", "operating RTE %", "idle loss %", "PCS power % of rated"]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m powertool.efficiency_cli",
        description="BESS efficiency run without a design: RTE at the POC per timestamp.")
    p.add_argument("input", help="CSV of timestamp, ambient °C (with a header row)")
    p.add_argument("output", help="CSV to write")
    p.add_argument("--solution", required=True, help="BESS solution catalogue key")
    p.add_argument("--station-transformer", required=True,
                   help="paired BESS station transformer catalogue key")
    p.add_argument("--stations", type=int, required=True)
    p.add_argument("--containers", type=int, required=True)
    p.add_argument("--poc-capacity-kw", type=float, required=True)
    p.add_argument("--load-loss-pct", type=float, required=True,
                   help="load loss at full power, %% of fleet rated active power")
    p.add_argument("--no-load-loss-pct", type=float, required=True,
                   help="no-load loss, %% of fleet rated active power")
    p.add_argument("--cycles-per-day", type=float)
    p.add_argument("--cell-rte-pct", type=float,
                   help="override the solution's catalogue cell RTE")
    return p


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{round(value, 4):g}"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = TypedConfiguration(
        solution=args.solution,
        station_transformer=args.station_transformer,
        stations=args.stations,
        containers=args.containers,
        poc_capacity_kw=args.poc_capacity_kw,
        load_loss_pct=args.load_loss_pct,
        no_load_loss_pct=args.no_load_loss_pct,
        cycles_per_day=args.cycles_per_day,
        cell_rte_pct=args.cell_rte_pct,
    )
    with open(args.input, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)                     # header
        rows = [(r[0], float(r[1])) for r in reader if r]

    try:
        result = run_efficiency(rows, config, ComponentDatabase.load())
    except EfficiencyRunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(OUTPUT_HEADER)
        for row in result.rows:
            writer.writerow([row.timestamp, _fmt(row.operating_rte_pct),
                             _fmt(row.idle_loss_pct), _fmt(row.pcs_power_pct)])
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
