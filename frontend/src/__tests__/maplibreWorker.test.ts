/**
 * Verifies that MapPane calls setWorkerUrl on module load with the URL
 * provided by Vite's ?worker&url import.
 *
 * Background: Vite production builds and non-root base-path deployments
 * (e.g. GitHub Pages at /skolky-starter/) require the worker URL to be
 * resolved at build time via `?worker&url`.  Without this, MapLibre GL
 * falls back to resolving the worker relative to the page origin, which
 * fails on sub-path deployments and produces "tt is not defined" at runtime.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

const MOCK_WORKER_URL = '/skolky-starter/assets/maplibre-gl-csp-worker-Abc123.js'

describe('MapPane – MapLibre worker URL setup', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('calls setWorkerUrl with the URL produced by ?worker&url', async () => {
    const mockSetWorkerUrl = vi.fn()

    // Must use vi.doMock (not vi.mock) after vi.resetModules so the mocks are
    // applied to the freshly-cleared module registry.
    vi.doMock('maplibre-gl', () => ({
      default: {
        Map: class { on() {} remove() {} },
        Marker: class {},
        Popup: class {},
        AttributionControl: class {},
        NavigationControl: class {},
        ScaleControl: class {},
      },
      setWorkerUrl: mockSetWorkerUrl,
    }))

    vi.doMock('maplibre-gl/dist/maplibre-gl-csp-worker?worker&url', () => ({
      default: MOCK_WORKER_URL,
    }))

    // CSS import would throw in Node — stub it out.
    vi.doMock('maplibre-gl/dist/maplibre-gl.css', () => ({}))

    // Stub mapUtils / types so MapPane doesn't pull in more side-effects.
    vi.doMock('../mapUtils', () => ({
      buildKindFilter: vi.fn(),
      toGeoJSON: vi.fn(),
    }))

    await import('../MapPane')

    expect(mockSetWorkerUrl).toHaveBeenCalledOnce()
    expect(mockSetWorkerUrl).toHaveBeenCalledWith(MOCK_WORKER_URL)
  })

  it('passes a non-empty string as the worker URL', async () => {
    const mockSetWorkerUrl = vi.fn()

    vi.doMock('maplibre-gl', () => ({
      default: {
        Map: class { on() {} remove() {} },
        Marker: class {},
        Popup: class {},
        AttributionControl: class {},
        NavigationControl: class {},
        ScaleControl: class {},
      },
      setWorkerUrl: mockSetWorkerUrl,
    }))

    vi.doMock('maplibre-gl/dist/maplibre-gl-csp-worker?worker&url', () => ({
      default: MOCK_WORKER_URL,
    }))

    vi.doMock('maplibre-gl/dist/maplibre-gl.css', () => ({}))

    vi.doMock('../mapUtils', () => ({
      buildKindFilter: vi.fn(),
      toGeoJSON: vi.fn(),
    }))

    await import('../MapPane')

    const url: string = mockSetWorkerUrl.mock.calls[0][0]
    expect(typeof url).toBe('string')
    expect(url.length).toBeGreaterThan(0)
  })
})
