import { describe, expect, it } from 'vitest'
import { SCHOOL_KINDS, displayName, kindColor, kindGroup, kindLabel } from '../types'
import type { MapSchool } from '../types'

// ── kindGroup ────────────────────────────────────────────

describe('kindGroup', () => {
  it('returns exact code for single-entry codes', () => {
    expect(kindGroup('A00')).toBe('A00')
    expect(kindGroup('B00')).toBe('B00')
    expect(kindGroup('E00')).toBe('E00')
  })

  it('returns prefix for prefix-matched codes', () => {
    expect(kindGroup('C00')).toBe('C')   // Střední
    expect(kindGroup('C11')).toBe('C')
    expect(kindGroup('F10')).toBe('F')   // ZUŠ
    expect(kindGroup('F20')).toBe('F')
    expect(kindGroup('J11')).toBe('J')   // Speciální
    expect(kindGroup('K10')).toBe('K')   // Poradna
    expect(kindGroup('K20')).toBe('K')
  })

  it('returns _ for unmatched codes (canteens, clubs, etc.)', () => {
    expect(kindGroup('L11')).toBe('_')   // Výdejna
    expect(kindGroup('L13')).toBe('_')   // Školní družina
    expect(kindGroup('G21')).toBe('_')   // Jídelna
    expect(kindGroup('H22')).toBe('_')
  })

  it('returns _ for null', () => {
    expect(kindGroup(null)).toBe('_')
  })

  it('all SCHOOL_KINDS codes (except _) are their own kindGroup', () => {
    for (const k of SCHOOL_KINDS) {
      if (k.code === '_') continue
      // A concrete example code that starts with this prefix
      const sample = k.code.length === 1 ? k.code + '00' : k.code
      expect(kindGroup(sample)).toBe(k.code)
    }
  })
})

// ── kindColor ─────────────────────────────────────────────

describe('kindColor', () => {
  it('returns a hex colour string', () => {
    const color = kindColor('A00')
    expect(color).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('returns the same colour for codes with the same group', () => {
    expect(kindColor('C00')).toBe(kindColor('C11'))
    expect(kindColor('F10')).toBe(kindColor('F20'))
  })

  it('returns the fallback colour for unknown codes', () => {
    const fallback = kindColor(null)
    expect(kindColor('ZZZZ')).toBe(fallback)
    expect(kindColor('L11')).toBe(fallback)
  })
})

// ── kindLabel ─────────────────────────────────────────────

describe('kindLabel', () => {
  it('maps A00 → Mateřská', () => expect(kindLabel('A00')).toBe('Mateřská'))
  it('maps B00 → Základní',  () => expect(kindLabel('B00')).toBe('Základní'))
  it('maps C00 → Střední',   () => expect(kindLabel('C00')).toBe('Střední'))
  it('maps E00 → VOŠ',       () => expect(kindLabel('E00')).toBe('VOŠ'))
  it('maps F10 → ZUŠ',       () => expect(kindLabel('F10')).toBe('ZUŠ'))
  it('maps null → Ostatní',  () => expect(kindLabel(null)).toBe('Ostatní'))
  it('maps L11 → Ostatní',   () => expect(kindLabel('L11')).toBe('Ostatní'))
})

// ── displayName ───────────────────────────────────────────

function makeSchool(overrides: Partial<MapSchool> = {}): MapSchool {
  return {
    external_key: 'test:key',
    name: 'Mateřská škola',
    street: null,
    school_kind_code: 'A00',
    lat: 50.0,
    lon: 14.0,
    municipality: 'Praha',
    data_box_id: null,
    website: null,
    address: 'Testovací 1, Praha',
    ...overrides,
  }
}

describe('displayName', () => {
  it('appends street to name when street is present', () => {
    expect(displayName(makeSchool({ street: 'Kapradová' }))).toBe('Mateřská škola Kapradová')
  })

  it('returns just the name when street is null', () => {
    expect(displayName(makeSchool({ street: null }))).toBe('Mateřská škola')
  })

  it('falls back to kindLabel when name is null', () => {
    const result = displayName(makeSchool({ name: null, street: null }))
    expect(result).toBe('Mateřská')  // kindLabel('A00')
  })

  it('combines fallback label with street', () => {
    const result = displayName(makeSchool({ name: null, street: 'Ulice' }))
    expect(result).toBe('Mateřská Ulice')
  })
})
