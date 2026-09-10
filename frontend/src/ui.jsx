import React from 'react'
import { Icon, Spinner } from './icons.jsx'

export const PALETTE = [
  '#5b7cfa', '#ef5350', '#2fb768', '#e0a324', '#9d7bf0',
  '#45b6d6', '#f0975a', '#7fd99a', '#e070a8', '#8890a0',
]

export const CHART_AXIS = { stroke: '#858c99', fontSize: 11 }
export const CHART_GRID = { stroke: '#e3e5ea', strokeDasharray: '3 3' }

export const TOOLTIP_STYLE = {
  contentStyle: {
    background: '#ffffff', border: '1px solid #d1d5dc', borderRadius: 8,
    fontSize: 12, boxShadow: '0 12px 28px rgba(23,26,33,0.12)',
  },
  labelStyle: { color: '#171a21', fontWeight: 600, marginBottom: 2 },
  itemStyle: { color: '#565d6b' },
}

/* ── Buttons ──────────────────────────────────────────────────────── */

export function Button({
  variant = 'secondary', size, icon, iconRight, loading, disabled,
  children, className, ...rest
}) {
  const cls = [
    'btn', `btn-${variant}`, size === 'sm' ? 'btn-sm' : '',
    loading ? 'btn-loading' : '', className || '',
  ].filter(Boolean).join(' ')
  return (
    <button className={cls} disabled={disabled || loading} {...rest}>
      {icon && <Icon name={icon} size={size === 'sm' ? 14 : 15} />}
      {children}
      {iconRight && <Icon name={iconRight} size={size === 'sm' ? 14 : 15} />}
      {loading && <Spinner size={size === 'sm' ? 13 : 15} className="btn-spinner" />}
    </button>
  )
}

export function IconButton({ icon, size = 16, variant = 'ghost', className, ...rest }) {
  return (
    <button className={`btn ${`btn-${variant}`} btn-icon ${className || ''}`} {...rest}>
      <Icon name={icon} size={size} />
    </button>
  )
}

/* ── Switch ───────────────────────────────────────────────────────── */

export function Switch({ checked, onChange, label, disabled }) {
  return (
    <label className={`switch ${checked ? 'on' : ''}`}
           style={disabled ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}>
      <input type="checkbox" checked={checked} disabled={disabled}
             onChange={(e) => onChange?.(e.target.checked)}
             style={{ position: 'absolute', width: 1, height: 1, opacity: 0 }} />
      <span className="switch-track"><span className="switch-thumb" /></span>
      {label && <span className="switch-label">{label}</span>}
    </label>
  )
}

/* ── Page / section headers ──────────────────────────────────────── */

export function PageHeader({ title, description, actions }) {
  return (
    <div className="page-header">
      <div className="page-header-text">
        <div className="page-title">{title}</div>
        {description && <div className="page-description">{description}</div>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </div>
  )
}

/* ── Cards ────────────────────────────────────────────────────────── */

export function Card({ title, hint, actions, children, style }) {
  return (
    <div className="card" style={style}>
      {(title || actions) && (
        <div className="card-header">
          <div className="card-header-text">
            {title && <div className="section-title">{title}</div>}
            {hint && <p className="section-hint">{hint}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {!title && hint && <p className="section-hint" style={{ marginBottom: 12 }}>{hint}</p>}
      {children}
    </div>
  )
}

const KPI_COLORS = {
  accent: 'var(--accent)', success: 'var(--success)', warning: 'var(--warning)',
  danger: 'var(--danger)', purple: 'var(--purple)', neutral: 'var(--text-secondary)',
}

export function Stat({ label, value, delta, color, icon, tone = 'neutral', trend }) {
  const deltaCls = trend === 'up' ? 'up' : trend === 'down' ? 'down' : ''
  return (
    <div className="stat-card">
      <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
        <span className="stat-label">{label}</span>
        {icon && (
          <span className={`kpi-icon ${tone}`}>
            <Icon name={icon} size={15} />
          </span>
        )}
      </div>
      <span className="stat-value" style={color ? { color } : undefined}>{value}</span>
      {delta && (
        <span className={`stat-delta ${deltaCls}`}>
          {trend === 'up' && <Icon name="arrow-up-right" size={12} />}
          {trend === 'down' && <Icon name="arrow-up-right" size={12} style={{ transform: 'rotate(90deg)' }} />}
          {delta}
        </span>
      )}
    </div>
  )
}

/* ── Badges ───────────────────────────────────────────────────────── */

const BADGE_ICON = {
  pass: 'check-circle', fail: 'x-circle', warn: 'alert-triangle',
  info: 'info', det: 'zap', neutral: null,
}

export function Badge({ kind = 'info', icon, children }) {
  const iconName = icon === null ? null : (icon || BADGE_ICON[kind])
  return (
    <span className={`badge ${kind}`}>
      {iconName && <Icon name={iconName} size={11} strokeWidth={2.4} />}
      {children}
    </span>
  )
}

/* ── Alert ────────────────────────────────────────────────────────── */

const ALERT_ICON = { danger: 'alert-triangle', warning: 'alert-triangle', info: 'info', success: 'check-circle' }

export function Alert({ tone = 'info', title, children, onDismiss }) {
  return (
    <div className={`alert ${tone}`}>
      <Icon name={ALERT_ICON[tone]} size={17} />
      <div className="alert-body">
        {title && <div className="alert-title">{title}</div>}
        <div>{children}</div>
      </div>
      {onDismiss && (
        <button className="alert-close" onClick={onDismiss} aria-label="Dismiss">
          <Icon name="x" size={14} />
        </button>
      )}
    </div>
  )
}

/* ── Empty state ──────────────────────────────────────────────────── */

export function Empty({ icon = 'inbox', title, children }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon"><Icon name={icon} size={19} /></div>
      {title && <div className="empty-state-title">{title}</div>}
      <div className="empty-state-desc">{children}</div>
    </div>
  )
}

/* ── Table ────────────────────────────────────────────────────────── */

/** `cols` = [{key, label, render?, align?, wrap?}] */
export function Table({ cols, rows, rowKey, maxHeight }) {
  if (!rows || rows.length === 0) return <Empty icon="table" title="No data">No rows to display.</Empty>
  return (
    <div className="tbl-wrap" style={maxHeight ? { maxHeight } : undefined}>
      <table>
        <thead>
          <tr>{cols.map(c => <th key={c.key} style={c.align ? { textAlign: c.align } : undefined}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey ? rowKey(r, i) : i}>
              {cols.map(c => (
                <td key={c.key} className={c.wrap ? 'wrap' : undefined}
                    style={c.align ? { textAlign: c.align } : undefined}>
                  {c.render ? c.render(r, i) : String(r[c.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ── Formatters ───────────────────────────────────────────────────── */

export const pct = (v, d = 1) =>
  v === null || v === undefined ? '–' : `${(v * 100).toFixed(d)}%`

export const num = (v, d = 2) =>
  v === null || v === undefined ? '–' : Number(v).toLocaleString(undefined, {
    minimumFractionDigits: d, maximumFractionDigits: d,
  })

export const int = (v) =>
  v === null || v === undefined ? '–' : Number(v).toLocaleString()
