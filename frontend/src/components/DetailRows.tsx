/** Read-only "label: value" row idiom, shared by the Inspector's catalogue
 * preview / Results sections and the full-screen specification view
 * (SpecView.tsx). Markup and class names are load-bearing — existing CSS
 * targets `.kv-row`, `.k`, `.v`. */
export function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="kv-row">
      <span className="k">{label}</span>
      <span className="v">{value}</span>
    </div>
  )
}

export function SectionTitle({ children }: { children: string }) {
  return <h3 className="inspector-section-title">{children}</h3>
}
