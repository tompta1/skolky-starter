import maplibregl, { setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-csp-worker?worker&url'

// Vite production builds must be told the worker URL explicitly so that:
//  (a) the worker script is emitted as a separate asset, and
//  (b) the URL includes the correct base-path (e.g. /skolky-starter/ on GH Pages).
// Without this, maplibre resolves the worker relative to the wrong path,
// the worker fails to load, and you get "tt is not defined" at runtime.
setWorkerUrl(workerUrl)
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react'
import { buildKindFilter, toGeoJSON } from './mapUtils'
import type { MapSchool } from './types'

// CartoDB Dark Matter — free, no API key, OSM Shortbread vector tiles
const DARK_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const SRC = 'schools'
const LYR = 'sch-base'

export type MapHandle = {
  flyTo: (lat: number, lon: number, zoom?: number) => void
}

type Props = {
  schools: MapSchool[]
  activeKinds: Set<string>
  onBoundsChange: (w: number, s: number, e: number, n: number) => void
  onSchoolClick: (key: string) => void
}

const MapPane = forwardRef<MapHandle, Props>(function MapPane(
  { schools, activeKinds, onBoundsChange, onSchoolClick },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

  // `ready` flips true once the correct map instance has its source + layers set up.
  // We need a state (not just a ref) so that dependent effects re-run.
  const [ready, setReady] = useState(false)

  // Stable refs for callbacks — avoids stale closures in map event handlers
  const boundsRef = useRef(onBoundsChange)
  const clickRef  = useRef(onSchoolClick)
  useEffect(() => { boundsRef.current = onBoundsChange }, [onBoundsChange])
  useEffect(() => { clickRef.current  = onSchoolClick  }, [onSchoolClick])

  useImperativeHandle(ref, () => ({
    flyTo(lat, lon, zoom = 15) {
      mapRef.current?.flyTo({ center: [lon, lat], zoom, duration: 900 })
    },
  }))

  // ── Init map ─────────────────────────────────────────
  // `isCurrent` guards against the React StrictMode double-mount race:
  //   mount → cleanup (isCurrent=false, map removed) → mount again
  // Without the guard, the FIRST map's async 'load' event fires after cleanup
  // and calls setReady(true) while mapRef points to the SECOND (not-yet-loaded)
  // map. The second map's 'load' then tries setReady(true) but state is already
  // true → React skips the re-render → dependent effects never fire → no data.
  useEffect(() => {
    if (!containerRef.current) return
    let isCurrent = true

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: DARK_STYLE,
      center: [15.5, 49.8],
      zoom: 7,
      attributionControl: false,
    })

    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right')
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left')

    map.on('load', () => {
      if (!isCurrent) return   // stale map — ignore

      map.addSource(SRC, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })

      // Base circles — all active-kind schools
      map.addLayer({
        id: LYR,
        type: 'circle',
        source: SRC,
        filter: ['boolean', false],  // always-false until first setFilter call
        paint: {
          'circle-color': ['get', 'c'],
          'circle-radius': ['interpolate', ['linear'], ['zoom'],
            5, 3, 9, 5, 13, 8, 17, 14,
          ],
          'circle-opacity': 0.9,
          'circle-stroke-width': 1,
          'circle-stroke-color': 'rgba(0,0,0,0.6)',
        },
      })

      // Hover popup
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 10,
        maxWidth: '260px',
      })
      const showPopup = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
        const p = e.features?.[0]?.properties
        if (!p) return
        map.getCanvas().style.cursor = 'pointer'
        const ds  = p.ds ? `<div class="mp-ds">📦 ${p.ds}</div>` : ''
        const em  = p.em ? `<div class="mp-ds"><a href="mailto:${p.em}">${p.em}</a></div>` : ''
        const web = p.w  ? `<div class="mp-web"><a href="${p.w}" target="_blank">${p.w.replace(/^https?:\/\//, '')}</a></div>` : ''
        popup.setLngLat(e.lngLat)
          .setHTML(`<div class="mp"><strong>${p.n}</strong><div class="mp-addr">${p.a}</div>${ds}${em}${web}</div>`)
          .addTo(map)
      }
      const hidePopup = () => { map.getCanvas().style.cursor = ''; popup.remove() }

      map.on('mouseenter', LYR, showPopup)
      map.on('mousemove',  LYR, e => popup.setLngLat(e.lngLat))
      map.on('mouseleave', LYR, hidePopup)
      map.on('click',      LYR, e => {
        const key = e.features?.[0]?.properties?.k
        if (key) clickRef.current(String(key))
      })

      // Report bounds whenever viewport changes
      const report = () => {
        const b = map.getBounds()
        boundsRef.current(b.getWest(), b.getSouth(), b.getEast(), b.getNorth())
      }
      map.on('moveend', report)
      report()   // fire immediately after load

      mapRef.current = map
      setReady(true)
    })

    return () => {
      isCurrent = false
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  // ── Sync GeoJSON data ─────────────────────────────────
  useEffect(() => {
    if (!ready || !mapRef.current) return
    ;(mapRef.current.getSource(SRC) as maplibregl.GeoJSONSource | undefined)
      ?.setData(toGeoJSON(schools))
  }, [schools, ready])

  // ── Sync kind filter ──────────────────────────────────
  useEffect(() => {
    if (!ready || !mapRef.current) return
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mapRef.current.setFilter(LYR, buildKindFilter(activeKinds) as any)
  }, [activeKinds, ready])

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
})

export default MapPane
