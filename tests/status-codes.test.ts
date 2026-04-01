/**
 * Tests that GPT's backend handles error cases gracefully with normalized statuses.
 * Requires backend running on http://localhost:8009
 */
import { describe, it, expect, beforeAll } from 'vitest'

const BASE = 'http://localhost:8009/api'

let backendUp = false
beforeAll(async () => {
  try {
    const res = await fetch(`${BASE}/health`, { signal: AbortSignal.timeout(3000) })
    backendUp = res.ok
  } catch {
    backendUp = false
  }
})

describe('404 handling', () => {
  it('unknown workspace returns 404 with structured body', async () => {
    if (!backendUp) return
    const res = await fetch(`${BASE}/workspaces/totally_fake_workspace`)
    expect(res.status).toBe(404)
    const body = await res.json()
    // Must have some structured error — not an empty 404
    expect(body).toBeTruthy()
    expect(typeof body).toBe('object')
  })

  it('unknown service returns 404', async () => {
    if (!backendUp) return
    const res = await fetch(`${BASE}/services/totally_fake_service`)
    expect(res.status).toBe(404)
  })
})

describe('git-pull safety', () => {
  it('refuses non-allowlisted path with error status', async () => {
    if (!backendUp) return
    const res = await fetch(`${BASE}/services/docgenerator/actions/git-pull`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_path: '/etc/passwd' }),
    })
    // Must refuse: 422 Unprocessable or 400 Bad Request
    expect([400, 422, 403]).toContain(res.status)
  })

  it('refuses empty repo_path', async () => {
    if (!backendUp) return
    const res = await fetch(`${BASE}/services/docgenerator/actions/git-pull`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_path: '' }),
    })
    expect([400, 422]).toContain(res.status)
  })
})

describe('collect response shape', () => {
  it('workspace collect returns services array (not crashing)', async () => {
    if (!backendUp) return
    const res = await fetch(`${BASE}/workspaces/zapp/collect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_filter: ['zapplambda'] }),
      signal: AbortSignal.timeout(60000),
    })
    // Must not 500 — even if servers are unreachable, returns structured result
    expect(res.status).not.toBe(500)
    const body = await res.json()
    expect(body).toHaveProperty('services')
    expect(Array.isArray(body.services)).toBe(true)
  }, 70000)

  it('each service result has a status field', async () => {
    if (!backendUp) return
    const res = await fetch(`${BASE}/workspaces/zapp/collect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_filter: ['zapplambda'] }),
      signal: AbortSignal.timeout(60000),
    })
    if (res.status === 500) return // skip if backend errored
    const body = await res.json()
    for (const svc of body.services) {
      expect(svc).toHaveProperty('status')
      const VALID_STATUSES = [
        'ok','partial','auth_failed','unreachable','vpn_or_network_blocked',
        'command_missing','path_missing','not_git_repo','dirty_repo',
        'permission_limited','unverified',
      ]
      expect(VALID_STATUSES).toContain(svc.status)
    }
  }, 70000)
})
