import { useStore } from '../store'
import type { Issue } from '../types'

export function IssuesBanner() {
  const issues = useStore((s) => s.issues)
  const results = useStore((s) => s.results)
  const setSelection = useStore((s) => s.setSelection)
  const all: Issue[] = [...issues, ...(results?.warnings ?? [])]

  if (all.length === 0) return null

  const select = (issue: Issue) => {
    if (issue.node_id) setSelection({ type: 'node', id: issue.node_id })
    else if (issue.edge_id) setSelection({ type: 'edge', id: issue.edge_id })
  }

  return (
    <div className="issues-banner">
      {all.map((issue, i) => (
        <button
          type="button"
          key={`${issue.code}-${i}`}
          className={`issue-item${issue.node_id || issue.edge_id ? ' clickable' : ''}`}
          onClick={() => select(issue)}
        >
          <strong>{issue.code}</strong> — {issue.message}
        </button>
      ))}
    </div>
  )
}
