import type { FleetKind, Technology } from './types'

/**
 * Does this design's technology permit drawing a fleet of this kind?
 *
 * `pv` permits only pv, `bess` permits only bess, `hybrid` permits both — the
 * table in docs/adr/0002-technology-declared-not-derived.md and the
 * Technology entry in CONTEXT.md. Every palette, inspector and settings
 * control specific to a fleet kind reads this rather than re-deriving it.
 *
 * A missing technology (the design hasn't loaded yet) permits everything: a
 * blank editor that hides its own palette is worse than one that briefly
 * shows too much.
 */
export function permitsFleetKind(technology: Technology | null | undefined, kind: FleetKind): boolean {
  if (technology == null) return true
  if (technology === 'hybrid') return true
  return technology === kind
}
