import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchMapSchools } from './api'
import MapPane, { type MapHandle } from './MapPane'
import {
  SCHOOL_KINDS,
  displayName,
  kindColor,
  kindGroup,
  kindLabel,
  type MapSchool,
} from './types'

type Bounds = { w: number; s: number; e: number; n: number }

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const [activeKinds, setActiveKinds] = useState<Set<string>>(
    new Set(['A00', 'B00', 'C', 'E00', 'F', 'J', 'K']),
  )

  const [allSchools, setAllSchools] = useState<MapSchool[]>([])
  const [mapLoading, setMapLoading] = useState(true)
  const [mapError,   setMapError]   = useState<string | null>(null)

  const [bounds,     setBounds]     = useState<Bounds | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)

  const mapRef        = useRef<MapHandle>(null)
  const selectedElRef = useRef<HTMLLIElement | null>(null)

  // ── Load all schools once ─────────────────────────────
  useEffect(() => {
    fetchMapSchools()
      .then(r => setAllSchools(r.items))
      .catch(e => setMapError(e.message))
      .finally(() => setMapLoading(false))
  }, [])

  // ── Derive viewport list ──────────────────────────────
  const visibleSchools = useMemo<MapSchool[]>(() => {
    if (!bounds) return []
    return allSchools.filter(s => {
      if (s.lon < bounds.w || s.lon > bounds.e || s.lat < bounds.s || s.lat > bounds.n) return false
      return activeKinds.has(kindGroup(s.school_kind_code))
    })
  }, [allSchools, bounds, activeKinds])

  const listSchools = useMemo<MapSchool[]>(() => {
    return [...visibleSchools].sort((a, b) =>
      displayName(a).localeCompare(displayName(b), 'cs'),
    )
  }, [visibleSchools])

  // ── Map callbacks ─────────────────────────────────────
  const handleBoundsChange = useCallback(
    (w: number, s: number, e: number, n: number) => setBounds({ w, s, e, n }),
    [],
  )

  const handleSchoolClick = useCallback((key: string) => {
    setSelectedKey(key)
    setTimeout(() => selectedElRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 60)
  }, [])

  // ── Controls ──────────────────────────────────────────
  function toggleKind(code: string) {
    setActiveKinds(prev => {
      const next = new Set(prev)
      next.has(code) ? next.delete(code) : next.add(code)
      return next
    })
  }

  function handleListClick(s: MapSchool) {
    setSelectedKey(s.external_key)
    mapRef.current?.flyTo(s.lat, s.lon, 16)
  }

  return (
    <div className="layout">

      {/* ── Left panel ──────────────────────────────── */}
      <aside className={`sidebar${sidebarOpen ? '' : ' sidebar-collapsed'}`}>

        <div className="sidebar-head">
          <button className="mobile-toggle" onClick={() => setSidebarOpen(o => !o)} aria-label="Přepnout panel">
            {sidebarOpen ? '▼' : '▲'}
          </button>

          <div className="chips">
            {SCHOOL_KINDS.map(k => (
              <button
                key={k.code}
                className={`chip ${activeKinds.has(k.code) ? 'chip-on' : ''}`}
                style={{ '--kc': k.color } as React.CSSProperties}
                onClick={() => toggleKind(k.code)}
              >
                {k.label}
              </button>
            ))}
          </div>

          <div className="list-count">
            {mapLoading
              ? 'Načítám data…'
              : `${visibleSchools.length.toLocaleString('cs')} škol ve výřezu`}
            {mapError && <span className="error"> — {mapError}</span>}
          </div>
        </div>

        {/* School list */}
        <ul className="school-list">
          {!mapLoading && listSchools.length === 0 && (
            <li className="list-empty">Žádné školy. Oddálte mapu nebo změňte filtry.</li>
          )}

          {listSchools.slice(0, 400).map(s => {
            const isSel = s.external_key === selectedKey
            const name  = displayName(s)

            return (
              <li
                key={s.external_key}
                ref={isSel ? (el: HTMLLIElement | null) => { selectedElRef.current = el } : undefined}
                className={`school-item${isSel ? ' sel' : ''}`}
                onClick={() => handleListClick(s)}
              >
                {/* Colour dot */}
                <span
                  className="dot"
                  style={{ background: kindColor(s.school_kind_code) }}
                  title={kindLabel(s.school_kind_code)}
                />

                <div className="item-body">
                  {/* Primary name */}
                  <div className="item-name" title={name}>{name}</div>

                  {/* Address */}
                  {s.address && (
                    <div className="item-addr">{s.address}</div>
                  )}

                  {/* Data-box + email row */}
                  <div className="item-chips">
                    {s.data_box_id && (
                      <span className="tag tag-ds" title="Datová schránka">
                        📦 {s.data_box_id}
                      </span>
                    )}
                    {s.email && (
                      <a
                        className="tag tag-web"
                        href={`mailto:${s.email}`}
                        onClick={e => e.stopPropagation()}
                        title={s.email}
                      >
                        ✉️ {s.email.substring(0, 32)}
                      </a>
                    )}
                  </div>

                  {/* Website — last row */}
                  {s.website && (
                    <a
                      className="tag tag-web"
                      href={s.website}
                      target="_blank"
                      rel="noreferrer"
                      onClick={e => e.stopPropagation()}
                      title={s.website}
                    >
                      🌐 {s.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '').substring(0, 36)}
                    </a>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      </aside>

      {/* ── Map ─────────────────────────────────────── */}
      <main className="map-area">
        <MapPane
          ref={mapRef}
          schools={allSchools}
          activeKinds={activeKinds}
          highlighted={new Set()}
          userLocation={null}
          onBoundsChange={handleBoundsChange}
          onSchoolClick={handleSchoolClick}
        />
      </main>

    </div>
  )
}
