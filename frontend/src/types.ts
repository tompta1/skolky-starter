export type School = {
  external_key: string
  entity_ico: string | null
  red_izo: string | null
  school_izo: string | null
  place_izo: string | null
  entity_name: string | null
  school_name: string | null
  school_kind_code: string | null
  municipality: string | null
  municipality_part: string | null
  street: string | null
  house_number: string | null
  orientation_number: string | null
  postal_code: string | null
  lat: number | null
  lon: number | null
  website: string | null
  email?: string | null
  website_checked_at: string | null
  data_box_id: string | null
  data_box_type: string | null
  data_box_subtype: string | null
  data_box_name: string | null
  distance_km: number
  address: string
}

export type MapSchool = {
  external_key: string
  name: string | null           // coalesce(school_name, entity_name)
  street: string | null         // kept so we can build "Mateřská škola Kapradová"
  school_kind_code: string | null
  lat: number
  lon: number
  municipality: string | null
  data_box_id: string | null
  website: string | null
  email?: string | null
  address: string
}

/** "Mateřská škola Kapradová" — school type + street name (without house number) */
export function displayName(s: MapSchool): string {
  const base = s.name ?? kindLabel(s.school_kind_code)
  return s.street ? `${base} ${s.street}` : base
}

export type NearbyResponse = { items: School[]; count: number }
export type MapResponse   = { items: MapSchool[]; total: number }

// ── Kind taxonomy ────────────────────────────────────────
export type KindDef = { code: string; label: string; color: string }

/** `code` is a prefix: 'A00' matches only 'A00'; 'C' matches 'C00','C11',… */
export const SCHOOL_KINDS: KindDef[] = [
  { code: 'A00', label: 'Mateřská',  color: '#f59e0b' },
  { code: 'B00', label: 'Základní',  color: '#60a5fa' },
  { code: 'C',   label: 'Střední',   color: '#a78bfa' },
  { code: 'GYM', label: 'Gymnázium', color: '#06b6d4' },
  { code: 'E00', label: 'VOŠ',       color: '#34d399' },
  { code: 'F',   label: 'ZUŠ',       color: '#fb923c' },
  { code: 'J',   label: 'Speciální', color: '#f472b6' },
  { code: 'K',   label: 'Poradna',   color: '#38bdf8' },
  { code: '_',   label: 'Ostatní',   color: '#64748b' },
]

export function kindGroup(code: string | null): string {
  if (!code) return '_'
  for (const k of SCHOOL_KINDS) {
    if (k.code !== '_' && code.startsWith(k.code)) return k.code
  }
  return '_'
}

export function kindColor(code: string | null): string {
  const kg = kindGroup(code)
  return SCHOOL_KINDS.find(k => k.code === kg)?.color ?? '#64748b'
}

export function kindLabel(code: string | null): string {
  const kg = kindGroup(code)
  return SCHOOL_KINDS.find(k => k.code === kg)?.label ?? 'Ostatní'
}
