import { useState } from 'react'
import type { ReactNode } from 'react'

/** Side panel shell with a collapse toggle — collapsed it shrinks to a rail
 * with a chevron, giving the canvas the width back. The state is local and
 * deliberately not persisted: it's a per-session working preference. */
export function CollapsiblePanel({
  title,
  side,
  className,
  children,
}: {
  title: string
  /** Which edge the panel sits on — decides which way the chevrons point. */
  side: 'left' | 'right'
  className: string
  children: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  const expandChevron = side === 'left' ? '›' : '‹'

  if (collapsed) {
    return (
      <aside className={`panel panel-collapsed ${className}`}>
        <button
          type="button"
          className="panel-toggle"
          onClick={() => setCollapsed(false)}
          title={`Show ${title}`}
          aria-label={`Show ${title}`}
        >
          {expandChevron}
        </button>
      </aside>
    )
  }

  return (
    <aside className={`panel ${className}`}>
      <div className="panel-header">
        <h2>{title}</h2>
        <button
          type="button"
          className="panel-toggle"
          onClick={() => setCollapsed(true)}
          title={`Hide ${title}`}
          aria-label={`Hide ${title}`}
        >
          {side === 'left' ? '‹' : '›'}
        </button>
      </div>
      {children}
    </aside>
  )
}
