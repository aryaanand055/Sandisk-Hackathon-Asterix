// Shared presentation helpers. Plain objects rather than styled-jsx, which
// React does not support without the babel plugin.

export const card = {
  background: '#fff',
  padding: 20,
  borderRadius: 8,
  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
}

export const th = {
  padding: 12,
  textAlign: 'left',
  fontWeight: 600,
  fontSize: 13,
  color: '#374151',
  borderBottom: '2px solid #e5e7eb',
  whiteSpace: 'nowrap',
}

export const td = {
  padding: '10px 12px',
  fontSize: 13,
  borderBottom: '1px solid #e5e7eb',
  color: '#4b5563',
}

export const badge = (bg, fg) => ({
  padding: '3px 8px',
  borderRadius: 4,
  fontSize: 12,
  fontWeight: 600,
  background: bg,
  color: fg,
  whiteSpace: 'nowrap',
})

export const PASS_BADGE = badge('#d1fae5', '#065f46')
export const FAIL_BADGE = badge('#fee2e2', '#991b1b')
export const WARN_BADGE = badge('#fef3c7', '#92400e')
export const INFO_BADGE = badge('#dbeafe', '#1e40af')

/** Locale-grouped integer, tolerant of null/undefined. */
export const num = (v) =>
  v == null || Number.isNaN(v) ? '—' : Number(v).toLocaleString()

/** Fraction (0-1) as a percentage string. */
export const pct = (v, digits = 1) =>
  v == null || Number.isNaN(v) ? '—' : `${(Number(v) * 100).toFixed(digits)}%`

/** Fixed-precision float, tolerant of null/undefined. */
export const fixed = (v, digits = 2) =>
  v == null || Number.isNaN(v) ? '—' : Number(v).toFixed(digits)

export const mono = {
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  fontSize: 12,
}
