import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { usePromptDialog } from './Modal'
import { useStore } from '../store'

/** Blocks the app behind a small modal on first visit until a display name is
 * set (persisted in localStorage) — every design save is stamped with it. */
export function DisplayNameGate({ children }: { children: ReactNode }) {
  const displayName = useStore((s) => s.displayName)
  const setDisplayName = useStore((s) => s.setDisplayName)
  const [draft, setDraft] = useState('')

  if (displayName) return <>{children}</>

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = draft.trim()
    if (trimmed) setDisplayName(trimmed)
  }

  return (
    <div className="modal-overlay">
      <form className="modal" onSubmit={submit}>
        <h2>Who&rsquo;s editing?</h2>
        <p className="panel-hint">
          Your name is shown as the last editor of a design when it&rsquo;s saved.
        </p>
        <input
          autoFocus
          type="text"
          value={draft}
          placeholder="Display name"
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="modal-actions">
          <button type="submit" disabled={!draft.trim()}>
            Continue
          </button>
        </div>
      </form>
    </div>
  )
}

/** Header control showing the current display name; click to change it. */
export function DisplayNameControl() {
  const displayName = useStore((s) => s.displayName)
  const setDisplayName = useStore((s) => s.setDisplayName)
  const { prompt, dialog } = usePromptDialog()

  const edit = async () => {
    const next = await prompt({ title: 'Display name', initialValue: displayName ?? '' })
    if (next && next.trim()) setDisplayName(next.trim())
  }

  return (
    <>
      <button type="button" className="display-name-control" onClick={edit} title="Change display name">
        {displayName ?? 'Set name'}
      </button>
      {dialog}
    </>
  )
}
