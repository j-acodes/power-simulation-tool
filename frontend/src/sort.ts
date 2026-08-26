/** Column sorting for the projects/designs tables. */

export type SortDir = 'asc' | 'desc'

export interface Sort {
  key: string
  dir: SortDir
}

/** Sort by any column, blanks always last so half-loaded rows don't jump to the
 * top. Numbers compare numerically, booleans true-first, everything else by
 * locale. */
export function sortRows<T extends object>(rows: T[], sort: Sort): T[] {
  return [...rows].sort((x, y) => {
    const a = (x as Record<string, unknown>)[sort.key]
    const b = (y as Record<string, unknown>)[sort.key]
    if (a == null || b == null) return a == null ? (b == null ? 0 : 1) : -1
    let cmp: number
    if (typeof a === 'number' && typeof b === 'number') cmp = a - b
    else if (typeof a === 'boolean' && typeof b === 'boolean') cmp = a === b ? 0 : a ? -1 : 1
    else cmp = String(a).localeCompare(String(b))
    return sort.dir === 'asc' ? cmp : -cmp
  })
}
