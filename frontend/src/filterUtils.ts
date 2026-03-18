import { kindGroup, type MapSchool } from './types'

export type Bounds = { w: number; s: number; e: number; n: number }

export function filterSchools(
  schools: MapSchool[],
  bounds: Bounds,
  activeKinds: Set<string>,
): MapSchool[] {
  return schools.filter(s => {
    if (s.lon < bounds.w || s.lon > bounds.e || s.lat < bounds.s || s.lat > bounds.n) return false
    return activeKinds.has(kindGroup(s.school_kind_code))
  })
}
