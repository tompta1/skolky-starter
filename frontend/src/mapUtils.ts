/**
 * Pure, side-effect-free map utilities — extracted so they can be unit-tested
 * without instantiating a MapLibre map.
 */
import { displayName, kindColor, kindGroup, type MapSchool } from './types'

// ── GeoJSON ──────────────────────────────────────────────

export function toGeoJSON(schools: MapSchool[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: schools.map(s => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
      properties: {
        k:  s.external_key,
        n:  displayName(s),
        kg: kindGroup(s.school_kind_code),
        c:  kindColor(s.school_kind_code),
        m:  s.municipality ?? '',
        a:  s.address ?? '',
        ds: s.data_box_id ?? '',
        w:  s.website ?? '',
        em: s.email ?? '',
      },
    })),
  }
}

// ── Layer filter expressions ─────────────────────────────
// Using 'any' + '==' instead of 'match'/'in' so the expression is
// unambiguous across all MapLibre versions and easy to unit-test.

type FilterExpr = unknown[]

export function buildKindFilter(activeKinds: Set<string>): FilterExpr {
  if (activeKinds.size === 0) return ['boolean', false]      // always-false
  const checks = Array.from(activeKinds).map(k => ['==', ['get', 'kg'], k])
  return checks.length === 1 ? checks[0] : ['any', ...checks]
}

// ── Czech Republic bbox (generous) ──────────────────────
export const CZ_BBOX = { minLat: 48.5, maxLat: 51.2, minLon: 12.0, maxLon: 18.9 }

export function isInCzechia(lat: number, lon: number): boolean {
  return (
    lat >= CZ_BBOX.minLat && lat <= CZ_BBOX.maxLat &&
    lon >= CZ_BBOX.minLon && lon <= CZ_BBOX.maxLon
  )
}
