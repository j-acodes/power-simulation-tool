import { useCallback, useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { technologyLabel } from '../technology'
import type { Technology } from '../types'

const TECHNOLOGY_OPTIONS: { value: Technology; label: string }[] = (
  ['pv', 'bess', 'hybrid'] as const
).map((value) => ({ value, label: technologyLabel(value) }))

/** Shared overlay/panel shell for every in-app modal (same markup/classes as
 * the original DisplayNameGate / ConflictDialog overlays). Escape always
 * cancels; when `onEnter` is given, Enter anywhere in the modal triggers it
 * (used by ConfirmDialog, which has no form to submit on Enter natively). */
/** Exported so other in-app modals (e.g. SeedWizard) can build on the same
 * overlay/Escape-to-cancel shell without duplicating it. */
export function ModalShell({
  children,
  onEscape,
  onEnter,
  size,
}: {
  children: ReactNode
  onEscape: () => void
  onEnter?: () => void
  /** Wider variants for content-heavy modals — 'wide' for a form (SeedWizard),
   * 'xl' for the full results tables. The default is sized for prompt/confirm
   * dialogs only. */
  size?: 'wide' | 'xl'
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onEscape()
      } else if (e.key === 'Enter' && onEnter) {
        e.preventDefault()
        onEnter()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onEscape, onEnter])

  return (
    <div className="modal-overlay">
      <div className={size ? `modal modal-${size}` : 'modal'}>{children}</div>
    </div>
  )
}

interface PromptDialogProps {
  title: string
  label?: string
  initialValue?: string
  /** When given, the dialog also collects a required technology alongside
   *  the name — one step, not a wizard (see ADR-0002 / ticket 02). */
  technologyLabel?: string
  initialTechnology?: Technology
  onSubmit: (value: string, technology?: Technology) => void
  onCancel: () => void
}

/** In-app replacement for `window.prompt`, optionally extended with a
 * required technology picker. Enter (native form submit) confirms with the
 * trimmed input (and the chosen technology, if asked for); Escape or the
 * Cancel button cancels. */
export function PromptDialog({
  title,
  label,
  initialValue = '',
  technologyLabel,
  initialTechnology,
  onSubmit,
  onCancel,
}: PromptDialogProps) {
  const [value, setValue] = useState(initialValue)
  const [technology, setTechnology] = useState<Technology | ''>(initialTechnology ?? '')
  const needsTechnology = technologyLabel !== undefined

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed) return
    if (needsTechnology && !technology) return
    onSubmit(trimmed, needsTechnology ? (technology as Technology) : undefined)
  }

  return (
    <ModalShell onEscape={onCancel}>
      <form onSubmit={submit}>
        <h2>{title}</h2>
        {label && <p className="panel-hint">{label}</p>}
        <input autoFocus type="text" value={value} onChange={(e) => setValue(e.target.value)} />
        {needsTechnology && (
          <>
            <p className="panel-hint">{technologyLabel}</p>
            <select value={technology} onChange={(e) => setTechnology(e.target.value as Technology)}>
              <option value="" disabled>
                Select technology…
              </option>
              {TECHNOLOGY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </>
        )}
        <div className="modal-actions">
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" disabled={!value.trim() || (needsTechnology && !technology)}>
            OK
          </button>
        </div>
      </form>
    </ModalShell>
  )
}

interface ConfirmDialogProps {
  title: string
  message: ReactNode
  danger?: boolean
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel: () => void
}

/** In-app replacement for `window.confirm`. Enter or the confirm button
 * confirms, Escape or the cancel button cancels. */
export function ConfirmDialog({
  title,
  message,
  danger,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <ModalShell onEscape={onCancel} onEnter={onConfirm}>
      <h2>{title}</h2>
      <p className="panel-hint">{message}</p>
      <div className="modal-actions">
        <button type="button" onClick={onCancel}>
          {cancelLabel}
        </button>
        <button type="button" className={danger ? 'danger' : undefined} onClick={onConfirm} autoFocus>
          {confirmLabel}
        </button>
      </div>
    </ModalShell>
  )
}

interface PromptOptions {
  title: string
  label?: string
  initialValue?: string
  /** When given, the dialog also collects a required technology; the
   *  resolved result carries it. */
  technologyLabel?: string
  initialTechnology?: Technology
}

export interface PromptResult {
  value: string
  /** Present only when the options asked for a technology. */
  technology?: Technology
}

/** Promise-based ergonomics over PromptDialog, mirroring `window.prompt`:
 * `const result = await prompt({ title: 'Project name' })` resolves
 * `{ value, technology? }`, or `null` on cancel. Render the returned
 * `dialog` node wherever the caller renders other modals. */
export function usePromptDialog() {
  const [pending, setPending] = useState<{
    options: PromptOptions
    resolve: (value: PromptResult | null) => void
  } | null>(null)

  const prompt = useCallback((options: PromptOptions) => {
    return new Promise<PromptResult | null>((resolve) => {
      setPending({ options, resolve })
    })
  }, [])

  const dialog = pending && (
    <PromptDialog
      title={pending.options.title}
      label={pending.options.label}
      initialValue={pending.options.initialValue}
      technologyLabel={pending.options.technologyLabel}
      initialTechnology={pending.options.initialTechnology}
      onSubmit={(value, technology) => {
        pending.resolve({ value, technology })
        setPending(null)
      }}
      onCancel={() => {
        pending.resolve(null)
        setPending(null)
      }}
    />
  )

  return { prompt, dialog }
}

interface ConfirmOptions {
  title: string
  message: ReactNode
  danger?: boolean
  confirmLabel?: string
  cancelLabel?: string
}

/** Promise-based ergonomics over ConfirmDialog, mirroring `window.confirm`:
 * `const ok = await confirm({ title: 'Delete project', message: '…' })`
 * resolves `true`/`false`. Render the returned `dialog` node wherever the
 * caller renders other modals. */
export function useConfirmDialog() {
  const [pending, setPending] = useState<{ options: ConfirmOptions; resolve: (value: boolean) => void } | null>(null)

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setPending({ options, resolve })
    })
  }, [])

  const dialog = pending && (
    <ConfirmDialog
      title={pending.options.title}
      message={pending.options.message}
      danger={pending.options.danger}
      confirmLabel={pending.options.confirmLabel}
      cancelLabel={pending.options.cancelLabel}
      onConfirm={() => {
        pending.resolve(true)
        setPending(null)
      }}
      onCancel={() => {
        pending.resolve(false)
        setPending(null)
      }}
    />
  )

  return { confirm, dialog }
}

interface TechnologyDialogProps {
  title: string
  /** The legal targets to offer — never the full set (see legalCloneTargets). */
  options: Technology[]
  /** Words to show under the picker for the selected target, e.g. what a
   *  narrowing conversion will not copy. Returns null/undefined for no note. */
  note?: (value: Technology) => ReactNode
  onSubmit: (value: Technology) => void
  onCancel: () => void
}

/** A restricted technology picker with no name field — used by the projects
 * page's Clone action, where the target's diagram already dictates the copy's
 * name (see docs/adr/0002 and CONTEXT.md's Technology entry). Unlike
 * PromptDialog, `options` is caller-supplied so only legal clone targets are
 * ever selectable. */
export function TechnologyDialog({ title, options, note, onSubmit, onCancel }: TechnologyDialogProps) {
  const [value, setValue] = useState<Technology | ''>(options.length === 1 ? options[0] : '')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!value) return
    onSubmit(value)
  }

  return (
    <ModalShell onEscape={onCancel}>
      <form onSubmit={submit}>
        <h2>{title}</h2>
        <select value={value} onChange={(e) => setValue(e.target.value as Technology)}>
          <option value="" disabled>
            Select technology…
          </option>
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {technologyLabel(opt)}
            </option>
          ))}
        </select>
        {value && note?.(value) && <p className="panel-hint">{note(value)}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" disabled={!value}>
            OK
          </button>
        </div>
      </form>
    </ModalShell>
  )
}

interface TechnologyDialogOptions {
  title: string
  options: Technology[]
  note?: (value: Technology) => ReactNode
}

/** Promise-based ergonomics over TechnologyDialog: `await pickTechnology({...})`
 * resolves the chosen Technology, or `null` on cancel. Render the returned
 * `dialog` node wherever the caller renders other modals. */
export function useTechnologyDialog() {
  const [pending, setPending] = useState<{
    options: TechnologyDialogOptions
    resolve: (value: Technology | null) => void
  } | null>(null)

  const pickTechnology = useCallback((options: TechnologyDialogOptions) => {
    return new Promise<Technology | null>((resolve) => {
      setPending({ options, resolve })
    })
  }, [])

  const dialog = pending && (
    <TechnologyDialog
      title={pending.options.title}
      options={pending.options.options}
      note={pending.options.note}
      onSubmit={(value) => {
        pending.resolve(value)
        setPending(null)
      }}
      onCancel={() => {
        pending.resolve(null)
        setPending(null)
      }}
    />
  )

  return { pickTechnology, dialog }
}
