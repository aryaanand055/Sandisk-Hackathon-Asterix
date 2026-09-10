import React from 'react'

/* Single consistent icon set — outline style, 24x24 viewBox, stroke-based.
   Hand-drawn (no icon package dependency) so weight/geometry stays uniform
   across the app. Add new glyphs to PATHS as needed. */

const PATHS = {
  'layout-grid': <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  fingerprint: <><path d="M12 3c-4 0-7 3-7 7v3c0 3 1.5 5.5 3 7" /><path d="M12 3c4 0 7 3 7 7v2" /><path d="M8 20c-1.7-1.8-3-4.3-3-7v-3c0-3.9 3.1-7 7-7s7 3.1 7 7v2" /><path d="M12 8c2.2 0 4 1.8 4 4v3c0 2 .7 3.8 2 5" /><path d="M12 8c-2.2 0-4 1.8-4 4v3.5" /><path d="M12 12c1.1 0 2 .9 2 2v2c0 1.8.6 3.4 1.6 4.7" /></>,
  scale: <><path d="M12 3v18" /><path d="M6 7h12" /><path d="M6 7 3 13a3 3 0 0 0 6 0Z" /><path d="M18 7l-3 6a3 3 0 0 0 6 0Z" /><rect x="9" y="19" width="6" height="2" rx="0.5" /></>,
  target: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none" /></>,
  'git-compare': <><circle cx="6" cy="6" r="2.3" /><circle cx="18" cy="18" r="2.3" /><path d="M8.3 6H15a3 3 0 0 1 3 3v6.7" /><path d="M15.7 18H9a3 3 0 0 1-3-3V8.3" /><path d="M11.5 3.5 8.3 6l3.2 2.5" /><path d="M12.5 20.5l3.2-2.5-3.2-2.5" /></>,
  table: <><rect x="3" y="4.5" width="18" height="15" rx="1.5" /><line x1="3" y1="9.5" x2="21" y2="9.5" /><line x1="9" y1="9.5" x2="9" y2="19.5" /></>,
  'list-detail': <><rect x="3" y="3.5" width="18" height="17" rx="1.5" /><line x1="7" y1="8.5" x2="17" y2="8.5" /><line x1="7" y1="12" x2="17" y2="12" /><line x1="7" y1="15.5" x2="13" y2="15.5" /></>,
  download: <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M4.5 19.5h15" /></>,
  upload: <><path d="M12 21V9" /><path d="m7 14 5-5 5 5" /><path d="M4.5 19.5h15" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.6-4.6L3 9" /><path d="M3 4v5h5" /><path d="M4 13a8 8 0 0 0 14.6 4.6L21 15" /><path d="M21 20v-5h-5" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><line x1="20" y1="20" x2="15.3" y2="15.3" /></>,
  'sliders': <><line x1="4" y1="6" x2="20" y2="6" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="18" x2="20" y2="18" /><circle cx="9" cy="6" r="2" fill="var(--surface, #14161b)" /><circle cx="16" cy="12" r="2" fill="var(--surface, #14161b)" /><circle cx="10" cy="18" r="2" fill="var(--surface, #14161b)" /></>,
  check: <polyline points="20 6 10 17 4 11" />,
  'check-circle': <><circle cx="12" cy="12" r="9" /><polyline points="8.5 12.3 11 14.8 15.8 9.5" /></>,
  x: <><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></>,
  'x-circle': <><circle cx="12" cy="12" r="9" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></>,
  'alert-triangle': <><path d="M12 3.3 22 20H2Z" /><line x1="12" y1="9.5" x2="12" y2="14" /><circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none" /></>,
  info: <><circle cx="12" cy="12" r="9" /><line x1="12" y1="11" x2="12" y2="16.5" /><circle cx="12" cy="7.7" r="0.9" fill="currentColor" stroke="none" /></>,
  'chevron-down': <polyline points="6 9 12 15 18 9" />,
  'chevron-up': <polyline points="6 15 12 9 18 15" />,
  'chevron-left': <polyline points="15 6 9 12 15 18" />,
  'chevron-right': <polyline points="9 6 15 12 9 18" />,
  'chevrons-left': <><polyline points="17 6 11 12 17 18" /><polyline points="11 6 5 12 11 18" /></>,
  'chevrons-right': <><polyline points="7 6 13 12 7 18" /><polyline points="13 6 19 12 13 18" /></>,
  'arrow-right': <><line x1="4" y1="12" x2="19" y2="12" /><polyline points="13 6 19 12 13 18" /></>,
  'arrow-up-right': <><line x1="7" y1="17" x2="17" y2="7" /><polyline points="8 7 17 7 17 16" /></>,
  'external-link': <><path d="M10 6H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" /><path d="M14 4h6v6" /><line x1="20" y1="4" x2="11" y2="13" /></>,
  layers: <><path d="M12 3 3 8l9 5 9-5Z" /><path d="m3 13 9 5 9-5" /><path d="m3 16.5 9 5 9-5" /></>,
  zap: <path d="M12.5 2 4 14h6.5L11 22l8.5-12H13z" />,
  'file-text': <><path d="M7 3h7l4 4v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /><path d="M14 3v4h4" /><line x1="9" y1="12.5" x2="15" y2="12.5" /><line x1="9" y1="16" x2="15" y2="16" /></>,
  inbox: <><path d="M4 12h4.5l1.6 3h3.8l1.6-3H20" /><path d="M5.5 5h13l1.5 7v6a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18v-6Z" /></>,
  database: <><ellipse cx="12" cy="5.5" rx="8" ry="3" /><path d="M4 5.5V18c0 1.7 3.6 3 8 3s8-1.3 8-3V5.5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>,
  cpu: <><rect x="6" y="6" width="12" height="12" rx="1.5" /><rect x="9.5" y="9.5" width="5" height="5" rx="0.5" /><line x1="12" y1="1.5" x2="12" y2="6" /><line x1="12" y1="18" x2="12" y2="22.5" /><line x1="1.5" y1="12" x2="6" y2="12" /><line x1="18" y1="12" x2="22.5" y2="12" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><polyline points="12 7 12 12 15.5 14" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 13.5a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.9 2.9l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V20a2 2 0 1 1-4 0v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.9-2.9l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H4a2 2 0 1 1 0-4h.2a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.9-2.9l.1.1a1.7 1.7 0 0 0 1.9.3H10a1.7 1.7 0 0 0 1-1.6V4a2 2 0 1 1 4 0v.2a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.9 2.9l-.1.1a1.7 1.7 0 0 0-.3 1.9V10a1.7 1.7 0 0 0 1.6 1H20a2 2 0 1 1 0 4h-.2a1.7 1.7 0 0 0-1.6 1Z" /></>,
  play: <path d="M7 4.5v15l13-7.5Z" />,
  loader: <><line x1="12" y1="2" x2="12" y2="6" /><line x1="12" y1="18" x2="12" y2="22" opacity="0.3" /><line x1="4.9" y1="4.9" x2="7.8" y2="7.8" opacity="0.55" /><line x1="16.2" y1="16.2" x2="19.1" y2="19.1" opacity="0.15" /><line x1="2" y1="12" x2="6" y2="12" opacity="0.45" /><line x1="18" y1="12" x2="22" y2="12" opacity="0.75" /><line x1="4.9" y1="19.1" x2="7.8" y2="16.2" opacity="0.15" /><line x1="16.2" y1="7.8" x2="19.1" y2="4.9" opacity="0.9" /></>,
  filter: <path d="M4 5h16l-6 7.5v5.7l-4 2V12.5Z" />,
  columns: <><rect x="3" y="4" width="18" height="16" rx="1.5" /><line x1="9" y1="4" x2="9" y2="20" /><line x1="15" y1="4" x2="15" y2="20" /></>,
  package: <><path d="m12 2.5 8.5 4.9v9.2L12 21.5l-8.5-4.9V7.4Z" /><path d="M3.5 7.4 12 12.3l8.5-4.9" /><line x1="12" y1="12.3" x2="12" y2="21.5" /></>,
}

export function Icon({ name, size = 16, strokeWidth = 1.8, style, className }) {
  const body = PATHS[name]
  if (!body) return null
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={strokeWidth}
      strokeLinecap="round" strokeLinejoin="round"
      style={style} className={className} aria-hidden="true"
    >
      {body}
    </svg>
  )
}

export function Spinner({ size = 14, className, style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth={2.2} strokeLinecap="round"
         className={`spinner ${className || ''}`} style={style} aria-hidden="true">
      {PATHS.loader}
    </svg>
  )
}
