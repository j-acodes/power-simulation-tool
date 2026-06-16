"""Example: size the inverters for an HV-interconnected PV plant.

Run from the project root with:

    python examples/pv_sizing_example.py
"""

import sys
from pathlib import Path

# Make the project root importable so this runs as `python examples/pv_sizing_example.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from powertool import (  # noqa: E402
    AutoCable,
    AuxLoad,
    Chain,
    ChainElement,
    ComponentDatabase,
    auto_hv_transformer,
    size_pv_inverters,
)


def main() -> None:
    db = ComponentDatabase.load()

    # A 45 MW PV plant connected at 132 kV.
    # Chain order: POC -> HV transformer -> MV collector -> MV/LV stations -> aux.
    # The HV transformer is auto-sized for the plant power; the MV collector cable
    # is auto-sized from the load at its worst-case (full loss budget) length.
    chain = Chain(
        [
            ChainElement(
                auto_hv_transformer(45_000 / 0.95, v_hv_kv=132, v_mv_kv=20),
                v_kv=132,
                label="MV/HV transformer (auto)",
            ),
            ChainElement(
                AutoCable(
                    candidates=db.cables_for_voltage(20),
                    max_utilization=0.80,
                    max_loss_percent_base=1.30,  # collection zone: <= 1.30% loss
                    max_loss_percent_per_km=0.0,
                ),
                v_kv=20,
                label="MV collector",  # no length -> worst case
            ),
            ChainElement(
                db.transformer("HUAWEI_JUPITER3000"),
                v_kv=20,
                n_parallel=14,
                label="MV/LV stations",
            ),
            ChainElement(
                AuxLoad("Substation aux", p_kw=120, q_kvar=40),
                v_kv=20,
                label="Substation aux",
            ),
        ],
        name="45 MW PV plant",
    )

    # Worst-case sizing: deliver 45 MW at PF 0.95, reactive injected at the POC.
    result = size_pv_inverters(chain, p_poc_kw=45_000, pf_target=0.95)
    print(result.report())


if __name__ == "__main__":
    main()
