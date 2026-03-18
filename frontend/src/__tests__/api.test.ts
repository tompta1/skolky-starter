import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchMapSchools, fetchNearby } from '../api'

// ── helpers ───────────────────────────────────────────────

function mockOk(body: unknown): Response {
  return {
    ok: true,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response
}

function mockErr(status: number, text = `Error ${status}`): Response {
  return {
    ok: false,
    status,
    text: () => Promise.resolve(text),
  } as unknown as Response
}

/** Parse the URL that fetch was called with (relative → absolute via localhost). */
function calledUrl(): URL {
  const raw = vi.mocked(fetch).mock.calls[0][0] as string
  return new URL(raw, 'http://localhost')
}

// ── setup / teardown ──────────────────────────────────────

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

// ── fetchMapSchools ───────────────────────────────────────

describe('fetchMapSchools', () => {
  it('calls /api/schools/map with no query string when called with no args', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], total: 0 }))
    await fetchMapSchools()
    const url = calledUrl()
    expect(url.pathname).toBe('/api/schools/map')
    expect(url.search).toBe('')
  })

  it('calls /api/schools/map with no query string when called with empty kinds', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], total: 0 }))
    await fetchMapSchools([])
    const url = calledUrl()
    expect(url.search).toBe('')
  })

  it('includes comma-joined kinds in query param', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], total: 0 }))
    await fetchMapSchools(['A00', 'B00'])
    expect(calledUrl().searchParams.get('kinds')).toBe('A00,B00')
  })

  it('passes a single kind through unchanged', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], total: 0 }))
    await fetchMapSchools(['C'])
    expect(calledUrl().searchParams.get('kinds')).toBe('C')
  })

  it('returns the parsed JSON body', async () => {
    const payload = { items: [{ external_key: 'k', name: 'Test' }], total: 1 }
    vi.mocked(fetch).mockResolvedValue(mockOk(payload))
    const result = await fetchMapSchools()
    expect(result).toEqual(payload)
  })

  it('throws with response text on non-ok status', async () => {
    vi.mocked(fetch).mockResolvedValue(mockErr(500, 'Internal Server Error'))
    await expect(fetchMapSchools()).rejects.toThrow('Internal Server Error')
  })

  it('throws a fallback message when error body is empty', async () => {
    vi.mocked(fetch).mockResolvedValue(mockErr(503, ''))
    await expect(fetchMapSchools()).rejects.toThrow('HTTP 503')
  })
})

// ── fetchNearby ───────────────────────────────────────────

describe('fetchNearby', () => {
  it('calls /api/schools/nearby with lat, lon, and limit', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], count: 0 }))
    await fetchNearby(50.07, 14.43, 5)
    const url = calledUrl()
    expect(url.pathname).toBe('/api/schools/nearby')
    expect(url.searchParams.get('lat')).toBe('50.07')
    expect(url.searchParams.get('lon')).toBe('14.43')
    expect(url.searchParams.get('limit')).toBe('5')
  })

  it('defaults limit to 10', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], count: 0 }))
    await fetchNearby(50.07, 14.43)
    expect(calledUrl().searchParams.get('limit')).toBe('10')
  })

  it('includes kinds param when provided', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], count: 0 }))
    await fetchNearby(50.07, 14.43, 10, ['A00', 'B00'])
    expect(calledUrl().searchParams.get('kinds')).toBe('A00,B00')
  })

  it('omits kinds param when undefined', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], count: 0 }))
    await fetchNearby(50.07, 14.43)
    expect(calledUrl().searchParams.has('kinds')).toBe(false)
  })

  it('omits kinds param when empty array', async () => {
    vi.mocked(fetch).mockResolvedValue(mockOk({ items: [], count: 0 }))
    await fetchNearby(50.07, 14.43, 10, [])
    expect(calledUrl().searchParams.has('kinds')).toBe(false)
  })

  it('returns the parsed JSON body', async () => {
    const payload = { items: [{ external_key: 'x', distance_km: 0.3 }], count: 1 }
    vi.mocked(fetch).mockResolvedValue(mockOk(payload))
    const result = await fetchNearby(50.07, 14.43)
    expect(result).toEqual(payload)
  })

  it('throws with response text on non-ok status', async () => {
    vi.mocked(fetch).mockResolvedValue(mockErr(404, 'No schools found.'))
    await expect(fetchNearby(50.07, 14.43)).rejects.toThrow('No schools found.')
  })

  it('throws a fallback message when error body is empty', async () => {
    vi.mocked(fetch).mockResolvedValue(mockErr(502, ''))
    await expect(fetchNearby(50.07, 14.43)).rejects.toThrow('HTTP 502')
  })
})
