import { describe, expect, it } from 'vitest'
import { filterSchools, type Bounds } from '../filterUtils'
import type { MapSchool } from '../types'

function school(overrides: Partial<MapSchool> = {}): MapSchool {
  return {
    external_key: 'test-1',
    name: 'Test School',
    street: null,
    school_kind_code: 'A00',
    lat: 50.0,
    lon: 14.0,
    municipality: 'Praha',
    data_box_id: null,
    website: null,
    address: '',
    ...overrides,
  }
}

const BOUNDS: Bounds = { w: 13.0, s: 49.0, e: 15.0, n: 51.0 }

describe('filterSchools', () => {
  it('includes school inside bounds with active kind', () => {
    const result = filterSchools([school()], BOUNDS, new Set(['A00']))
    expect(result).toHaveLength(1)
  })

  it('excludes school west of bounds', () => {
    const result = filterSchools([school({ lon: 12.9 })], BOUNDS, new Set(['A00']))
    expect(result).toHaveLength(0)
  })

  it('excludes school east of bounds', () => {
    const result = filterSchools([school({ lon: 15.1 })], BOUNDS, new Set(['A00']))
    expect(result).toHaveLength(0)
  })

  it('excludes school south of bounds', () => {
    const result = filterSchools([school({ lat: 48.9 })], BOUNDS, new Set(['A00']))
    expect(result).toHaveLength(0)
  })

  it('excludes school north of bounds', () => {
    const result = filterSchools([school({ lat: 51.1 })], BOUNDS, new Set(['A00']))
    expect(result).toHaveLength(0)
  })

  it('includes school on boundary edge (inclusive)', () => {
    const onEdge = school({ lat: BOUNDS.s, lon: BOUNDS.w })
    const result = filterSchools([onEdge], BOUNDS, new Set(['A00']))
    expect(result).toHaveLength(1)
  })

  it('excludes school with inactive kind', () => {
    const result = filterSchools([school({ school_kind_code: 'B00' })], BOUNDS, new Set(['A00']))
    expect(result).toHaveLength(0)
  })

  it('maps null school_kind_code to "_" — included if "_" active', () => {
    const s = school({ school_kind_code: null })
    expect(filterSchools([s], BOUNDS, new Set(['_']))).toHaveLength(1)
    expect(filterSchools([s], BOUNDS, new Set(['A00']))).toHaveLength(0)
  })

  it('returns empty array for empty schools input', () => {
    const result = filterSchools([], BOUNDS, new Set(['A00']))
    expect(result).toHaveLength(0)
  })

  it('excludes all schools when activeKinds is empty', () => {
    const result = filterSchools([school(), school({ school_kind_code: 'B00' })], BOUNDS, new Set())
    expect(result).toHaveLength(0)
  })
})
