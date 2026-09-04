import { Link } from 'react-router-dom'
import { DisplayNameControl } from '../components/DisplayName'
import { EditorView } from './EditorView'

/** Unsaved scratch work: today's standalone editor behavior, unchanged — no
 * persistence, reachable from the Projects page as "Scratchpad". */
export function ScratchPage() {
  return (
    <EditorView
      title="Plant Sizing — Scratchpad"
      headerLeft={
        <Link to="/" className="header-link">
          ← Projects
        </Link>
      }
      headerRight={<DisplayNameControl />}
    />
  )
}
