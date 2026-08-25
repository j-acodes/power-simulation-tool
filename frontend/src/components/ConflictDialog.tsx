import type { DesignFull } from '../types'

interface ConflictDialogProps {
  serverDesign: DesignFull
  onReloadTheirs: () => void
  onSaveAsNew: () => void
  onCancel: () => void
}

/** Shown when a PUT /api/designs/{id} comes back 409: someone else saved
 * first. Never silently overwrites — the user picks reload-theirs or
 * save-as-new-design (or cancels and keeps editing locally). */
export function ConflictDialog({ serverDesign, onReloadTheirs, onSaveAsNew, onCancel }: ConflictDialogProps) {
  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Save conflict</h2>
        <p className="panel-hint">
          {serverDesign.last_edited_by} saved version {serverDesign.version} of this design while
          you were editing. Your changes have not been saved.
        </p>
        <div className="modal-actions">
          <button type="button" onClick={onReloadTheirs}>
            Reload their version
          </button>
          <button type="button" onClick={onSaveAsNew}>
            Save as new design
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
