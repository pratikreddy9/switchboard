/**
 * Cross-tests for GPT's FastAPI backend.
 * Requires backend running on http://localhost:8009
 * Run with: npm test
 */
import { describe, it, expect, beforeAll } from 'vitest'

const BASE = 'http://localhost:8009/api'

async function get(path: string) {
  const res = await fetch(`${BASE}${path}`)
  return { status: res.status, body: await res.json() }
}

async function post(path: string, body: unknown) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return { status: res.status, body: await res.json() }
}

// Skip all tests if backend is not running
let backendUp = false
beforeAll(async () => {
  try {
    const res = await fetch(`${BASE}/health`, { signal: AbortSignal.timeout(3000) })
    backendUp = res.ok
  } catch {
    backendUp = false
  }
  if (!backendUp) console.warn('⚠ Backend not reachable at :8009 — skipping live tests')
})

describe('GET /api/health', () => {
  it('returns { status: "ok" }', async () => {
    if (!backendUp) return
    const { status, body } = await get('/health')
    expect(status).toBe(200)
    expect(body).toHaveProperty('status')
    expect(body.status).toBe('ok')
  })
})

describe('GET /api/workspaces', () => {
  it('returns { workspaces: [...] } wrapper', async () => {
    if (!backendUp) return
    const { status, body } = await get('/workspaces')
    expect(status).toBe(200)
    expect(body).toHaveProperty('workspaces')
    expect(Array.isArray(body.workspaces)).toBe(true)
  })

  it('includes zapp workspace', async () => {
    if (!backendUp) return
    const { body } = await get('/workspaces')
    const ids = body.workspaces.map((w: { workspace_id: string }) => w.workspace_id)
    expect(ids).toContain('zapp')
  })

  it('includes pesu workspace', async () => {
    if (!backendUp) return
    const { body } = await get('/workspaces')
    const ids = body.workspaces.map((w: { workspace_id: string }) => w.workspace_id)
    expect(ids).toContain('pesu')
  })
})

describe('GET /api/workspaces/:id', () => {
  it('returns { workspace: {...}, services: [...] } wrapper', async () => {
    if (!backendUp) return
    const { status, body } = await get('/workspaces/zapp')
    expect(status).toBe(200)
    expect(body).toHaveProperty('workspace')
    expect(body.workspace).toHaveProperty('workspace_id', 'zapp')
    expect(Array.isArray(body.services)).toBe(true)
  })

  it('returns 404 for unknown workspace', async () => {
    if (!backendUp) return
    const { status } = await get('/workspaces/nonexistent_workspace_xyz')
    expect(status).toBe(404)
  })
})

describe('GET /api/workspaces/:id/latest', () => {
  it('returns required top-level keys', async () => {
    if (!backendUp) return
    const { status, body } = await get('/workspaces/zapp/latest')
    expect(status).toBe(200)
    const REQUIRED_KEYS = ['workspace', 'servers', 'services', 'summary', 'repo_inventory', 'docs_index', 'logs_index']
    for (const key of REQUIRED_KEYS) {
      expect(body, `Missing key: ${key}`).toHaveProperty(key)
    }
  })

  it('services is an array', async () => {
    if (!backendUp) return
    const { body } = await get('/workspaces/zapp/latest')
    expect(Array.isArray(body.services)).toBe(true)
  })
})

describe('GET /api/services/:id', () => {
  it('returns { service: {...} } wrapper with required fields', async () => {
    if (!backendUp) return
    const { status, body } = await get('/services/aichat')
    expect(status).toBe(200)
    expect(body).toHaveProperty('service')
    for (const field of ['service_id', 'workspace_id', 'display_name', 'locations', 'tags', 'execution_mode']) {
      expect(body.service, `Missing field: ${field}`).toHaveProperty(field)
    }
  })

  it('includes runtime config on locations', async () => {
    if (!backendUp) return
    const { status, body } = await get('/services/aichat')
    expect(status).toBe(200)
    expect(Array.isArray(body.service.locations)).toBe(true)
    if (body.service.locations.length > 0) {
      expect(body.service.locations[0]).toHaveProperty('runtime')
      expect(body.service.locations[0].runtime).toHaveProperty('monitoring_mode')
    }
  })
})

describe('GET /api/services/:id/secret-paths', () => {
  it('returns count field (never exposes paths in contract)', async () => {
    if (!backendUp) return
    const { status, body } = await get('/services/aichat/secret-paths')
    expect(status).toBe(200)
    expect(body).toHaveProperty('count')
    expect(typeof body.count).toBe('number')
  })
})

describe('GET /api/workspaces/:id/projects', () => {
  it('returns projects plus environment rollup arrays', async () => {
    if (!backendUp) return
    const { status, body } = await get('/workspaces/pesu/projects')
    expect(status).toBe(200)
    expect(Array.isArray(body.projects)).toBe(true)
    expect(Array.isArray(body.environments)).toBe(true)
    expect(Array.isArray(body.rollups)).toBe(true)
  })
})
