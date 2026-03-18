import type { MapResponse, NearbyResponse } from './types'

// Empty string → relative URL (works on Vercel where frontend + API share the same origin).
// Override with VITE_API_BASE=http://localhost:8000 in frontend/.env.local for local dev
// when the Vite proxy is not being used.
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export async function fetchNearby(
  lat: number,
  lon: number,
  limit = 10,
  kinds?: string[],
): Promise<NearbyResponse> {
  const params = new URLSearchParams({ lat: String(lat), lon: String(lon), limit: String(limit) })
  if (kinds && kinds.length > 0) params.set('kinds', kinds.join(','))
  const response = await fetch(`${API_BASE}/api/schools/nearby?${params}`)
  if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`)
  return response.json()
}

export async function fetchMapSchools(kinds?: string[]): Promise<MapResponse> {
  const params = new URLSearchParams()
  if (kinds && kinds.length > 0) params.set('kinds', kinds.join(','))
  const qs = params.size ? `?${params}` : ''
  const response = await fetch(`${API_BASE}/api/schools/map${qs}`)
  if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`)
  return response.json()
}
