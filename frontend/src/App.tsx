import { useEffect, useState } from 'react'
import './App.css'

interface TransformerInfo {
  key: string
  display_name: string
  s_rated_kva: number
}

interface CatalogueResponse {
  transformers: TransformerInfo[]
  cables: Record<string, unknown[]>
}

function App() {
  const [catalogue, setCatalogue] = useState<CatalogueResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/catalogue')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json() as Promise<CatalogueResponse>
      })
      .then(setCatalogue)
      .catch((err) => setError(String(err)))
  }, [])

  const cableTypeCount = catalogue
    ? Object.values(catalogue.cables).reduce((sum, group) => sum + group.length, 0)
    : 0

  return (
    <main>
      <h1>PV Plant Sizing</h1>
      {error && <p role="alert">Could not load catalogue: {error}</p>}
      {!catalogue && !error && <p>Loading catalogue…</p>}
      {catalogue && (
        <>
          <p>{cableTypeCount} cable type(s) across {Object.keys(catalogue.cables).length} voltage class(es).</p>
          <h2>Transformers</h2>
          <ul>
            {catalogue.transformers.map((tx) => (
              <li key={tx.key}>
                {tx.display_name} — {tx.s_rated_kva} kVA
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  )
}

export default App
