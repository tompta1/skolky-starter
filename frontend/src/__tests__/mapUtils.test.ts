import { describe, expect, it } from 'vitest'
import { buildKindFilter, isInCzechia, toGeoJSON } from '../mapUtils'
import { kindGroup, type MapSchool } from '../types'

function school(overrides: Partial<MapSchool> = {}): MapSchool {
  return {
    external_key: 'ico:izo:place',
    name: 'Mateřská škola',
    street: 'Kapradová',
    school_kind_code: 'A00',
    lat: 50.07,
    lon: 14.43,
    municipality: 'Praha',
    data_box_id: 'abc1234',
    website: 'https://example.cz',
    address: 'Kapradová 5, Praha',
    ...overrides,
  }
}

// ── toGeoJSON ─────────────────────────────────────────────

describe('toGeoJSON', () => {
  it('returns a valid GeoJSON FeatureCollection', () => {
    const gj = toGeoJSON([school()])
    expect(gj.type).toBe('FeatureCollection')
    expect(Array.isArray(gj.features)).toBe(true)
  })

  it('produces one feature per school', () => {
    const gj = toGeoJSON([school(), school({ external_key: 'x:y:z' })])
    expect(gj.features).toHaveLength(2)
  })

  it('uses [lon, lat] coordinate order', () => {
    const gj = toGeoJSON([school({ lat: 50.07, lon: 14.43 })])
    const coords = (gj.features[0].geometry as GeoJSON.Point).coordinates
    expect(coords[0]).toBe(14.43)   // lon first
    expect(coords[1]).toBe(50.07)   // lat second
  })

  it('sets kg to the kindGroup of school_kind_code', () => {
    const gj = toGeoJSON([school({ school_kind_code: 'C00' })])
    expect(gj.features[0].properties?.kg).toBe(kindGroup('C00'))  // 'C'
  })

  it('builds display name as "name street"', () => {
    const gj = toGeoJSON([school({ name: 'Mateřská škola', street: 'Kapradová' })])
    expect(gj.features[0].properties?.n).toBe('Mateřská škola Kapradová')
  })

  it('falls back gracefully when name is null', () => {
    const gj = toGeoJSON([school({ name: null, street: 'Ulice' })])
    expect(typeof gj.features[0].properties?.n).toBe('string')
    expect(gj.features[0].properties?.n.length).toBeGreaterThan(0)
  })

  it('stores data_box_id in ds property', () => {
    const gj = toGeoJSON([school({ data_box_id: 'xyz9876' })])
    expect(gj.features[0].properties?.ds).toBe('xyz9876')
  })

  it('stores empty string for null data_box_id', () => {
    const gj = toGeoJSON([school({ data_box_id: null })])
    expect(gj.features[0].properties?.ds).toBe('')
  })

  it('returns empty FeatureCollection for empty input', () => {
    const gj = toGeoJSON([])
    expect(gj.features).toHaveLength(0)
  })
})

// ── buildKindFilter ───────────────────────────────────────

describe('buildKindFilter', () => {
  it('returns always-false expression for empty set', () => {
    const f = buildKindFilter(new Set())
    expect(Array.isArray(f)).toBe(true)
    // implementation uses ['boolean', false] — a valid MapLibre always-false filter
    expect(f[0]).toBe('boolean')
    expect(f[1]).toBe(false)
  })

  it('returns a single equality check for one-element set', () => {
    const f = buildKindFilter(new Set(['A00']))
    expect(f[0]).toBe('==')
  })

  it('returns an any expression for multiple kinds', () => {
    const f = buildKindFilter(new Set(['A00', 'B00', 'C']))
    expect(f[0]).toBe('any')
    // should have one sub-expression per kind
    const checks = (f as unknown[]).slice(1) as unknown[][]
    expect(checks).toHaveLength(3)
    // each check should compare ['get', 'kg'] to a kind code
    for (const check of checks) {
      expect(check[0]).toBe('==')
      expect(check[1]).toEqual(['get', 'kg'])
    }
  })

  it('includes all provided kind codes', () => {
    const kinds = new Set(['A00', 'B00', 'C', 'E00'])
    const f = buildKindFilter(kinds) as unknown[][]
    const codeValues = (f.slice(1) as unknown[][]).map(c => c[2])
    expect(codeValues.sort()).toEqual([...kinds].sort())
  })
})

// ── isInCzechia ───────────────────────────────────────────

describe('isInCzechia', () => {
  it('accepts coordinates inside Czech Republic', () => {
    expect(isInCzechia(50.075, 14.437)).toBe(true)   // Praha
    expect(isInCzechia(49.195, 16.608)).toBe(true)   // Brno
    expect(isInCzechia(49.747, 13.377)).toBe(true)   // Plzeň
  })

  it('rejects coordinates outside Czech Republic', () => {
    expect(isInCzechia(48.208, 16.373)).toBe(false)  // Wien
    expect(isInCzechia(52.52,  13.405)).toBe(false)  // Berlin
    expect(isInCzechia(50.075, 0.0)).toBe(false)     // London area
  })

  it('rejects garbage coordinates (JTSK leak)', () => {
    // un-negated JTSK values would be ~515000, ~1166000 — clearly outside Czech bbox
    expect(isInCzechia(515561, 1166540)).toBe(false)
    expect(isInCzechia(63.18,  45.26)).toBe(false)   // previously wrong transform output
  })
})
