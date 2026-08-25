import { useEffect, useState } from 'react'
import { getCatalogue } from '../api'
import type { CatalogueResponse } from '../types'

/** Fetches GET /api/catalogue once; null while loading or on failure. Shared
 * by the Palette (drag sources) and the Inspector (model/cable dropdowns). */
export function useCatalogue(): CatalogueResponse | null {
  const [catalogue, setCatalogue] = useState<CatalogueResponse | null>(null)
  useEffect(() => {
    getCatalogue()
      .then(setCatalogue)
      .catch(() => setCatalogue(null))
  }, [])
  return catalogue
}
