import { useState } from 'react'
import { Link } from 'react-router-dom'
import '../App.css'
import { groupByBrand } from '../catalogueGrouping'
import { DisplayNameControl } from '../components/DisplayName'
import { Row } from '../components/DetailRows'
import { ModalShell } from '../components/Modal'
import { SpecView } from '../components/SpecView'
import type { SpecViewTarget } from '../components/SpecView'
import { useCatalogue } from '../hooks/useCatalogue'
import { fmt } from '../format'
import { LABEL } from '../labels'
import type { BessSolutionInfo, CableInfo, TransformerInfo } from '../types'

/** A transformer with no datasheet behind it (every PV station transformer,
 * today's cables) — shown with what it already carries, not made to look
 * clickable, because there is no specification a click would open. */
function StaticTransformerRow({ tx }: { tx: TransformerInfo }) {
  return (
    <div className="catalogue-row catalogue-row-static">
      <div className="catalogue-row-header">{tx.display_name}</div>
      <Row label={LABEL.sRatedKva} value={fmt(tx.s_rated_kva)} />
      <Row label={LABEL.ukPercent} value={fmt(tx.uk_percent, 2)} />
      <Row label={LABEL.hvKv} value={tx.hv_kv != null ? fmt(tx.hv_kv, 2) : '—'} />
      <Row label={LABEL.lvKv} value={tx.lv_kv != null ? fmt(tx.lv_kv, 2) : '—'} />
    </div>
  )
}

function CableRow({ cable }: { cable: CableInfo }) {
  return (
    <div className="catalogue-row catalogue-row-static">
      <div className="catalogue-row-header">{cable.name}</div>
      <Row label={LABEL.crossSectionMm2} value={fmt(cable.cross_section_mm2)} />
      <Row label={LABEL.ratedCurrentA} value={fmt(cable.rated_current_a)} />
    </div>
  )
}

/** A catalogue-backed BESS entry — clicking it opens its full specification
 * (ticket 04's SpecView), exactly as selecting it in the palette or the
 * Inspector does. */
function ClickableRow({ target, onSelect }: { target: SpecViewTarget; onSelect: (target: SpecViewTarget) => void }) {
  const item = target.item
  return (
    <button type="button" className="catalogue-row catalogue-row-clickable" onClick={() => onSelect(target)}>
      <span className="catalogue-brand">{item.brand}</span> <span>{item.display_name}</span>
    </button>
  )
}

/** `/catalogue` — every catalogue component the tool knows about, browsable
 * without opening a project (ticket 05). No technology filter: the page
 * belongs to no design, so there is no technology to filter by. */
export function CataloguePage() {
  const catalogue = useCatalogue()
  const [specTarget, setSpecTarget] = useState<SpecViewTarget | null>(null)

  const pvBrandGroups = catalogue ? groupByBrand(catalogue.transformers) : []
  const bessBrandGroups = catalogue ? groupByBrand(catalogue.bess_transformers) : []

  return (
    <div className="app catalogue-page">
      <header className="app-header">
        <h1>Catalogue</h1>
        <div className="app-header-actions">
          <Link to="/" className="header-link">
            ← Projects
          </Link>
          <DisplayNameControl />
        </div>
      </header>

      {!catalogue ? (
        <p className="panel-hint">Loading catalogue…</p>
      ) : (
        <div className="app-body catalogue-body">
          <section>
            <h2>PV station transformers</h2>
            {pvBrandGroups.map(([brand, transformers]) => (
              <details key={brand} className="palette-group" open>
                <summary>{brand}</summary>
                {transformers.map((tx) => (
                  <StaticTransformerRow key={tx.key} tx={tx} />
                ))}
              </details>
            ))}
          </section>

          <section>
            <h2>Cables</h2>
            {Object.entries(catalogue.cables).map(([kv, cables]) => (
              <details key={kv} className="palette-group" open>
                <summary>{kv} kV</summary>
                {cables.map((cable) => (
                  <CableRow key={cable.name} cable={cable} />
                ))}
              </details>
            ))}
          </section>

          <section>
            <h2>BESS solutions</h2>
            {catalogue.bess_solutions.map((sol: BessSolutionInfo) => (
              <ClickableRow key={sol.key} target={{ kind: 'bess_solution', item: sol }} onSelect={setSpecTarget} />
            ))}
          </section>

          <section>
            <h2>BESS station transformers</h2>
            {bessBrandGroups.map(([brand, transformers]) => (
              <details key={brand} className="palette-group" open>
                <summary>{brand}</summary>
                {transformers.map((tx) => (
                  <ClickableRow key={tx.key} target={{ kind: 'bess_transformer', item: tx }} onSelect={setSpecTarget} />
                ))}
              </details>
            ))}
          </section>
        </div>
      )}

      {specTarget && (
        <ModalShell size="full" onEscape={() => setSpecTarget(null)}>
          <SpecView
            target={specTarget}
            solutions={catalogue?.bess_solutions ?? []}
            transformers={catalogue?.bess_transformers ?? []}
          />
        </ModalShell>
      )}
    </div>
  )
}
