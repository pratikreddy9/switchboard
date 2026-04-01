/**
 * Validates the structure of docs/evidence/*.json snapshot files.
 * Runs without a live backend — reads files directly.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'

const EVIDENCE_DIR = resolve(process.cwd(), 'docs/evidence')

function loadEvidence(name: string) {
  const p = resolve(EVIDENCE_DIR, name)
  if (!existsSync(p)) return null
  return JSON.parse(readFileSync(p, 'utf-8'))
}

const REQUIRED_FILES = [
  'workspace-registry.json',
  'server-registry.json',
  'service-inventory.json',
  'repo-inventory.json',
  'docs-index.json',
  'logs-index.json',
  'run-history.json',
]

describe('Evidence files exist', () => {
  for (const file of REQUIRED_FILES) {
    it(`${file} exists`, () => {
      const p = resolve(EVIDENCE_DIR, file)
      expect(existsSync(p), `Missing: ${p}`).toBe(true)
    })
  }
})

describe('workspace-registry.json shape', () => {
  it('has workspaces array', () => {
    const data = loadEvidence('workspace-registry.json')
    if (!data) return // file not yet generated — skip
    expect(data).toHaveProperty('workspaces')
    expect(Array.isArray(data.workspaces)).toBe(true)
  })
})

describe('service-inventory.json shape', () => {
  it('has services array', () => {
    const data = loadEvidence('service-inventory.json')
    if (!data) return
    expect(data).toHaveProperty('services')
    expect(Array.isArray(data.services)).toBe(true)
  })

  it('no service entry contains secret_path or password fields', () => {
    const data = loadEvidence('service-inventory.json')
    if (!data) return
    const FORBIDDEN = ['secret_path', 'secret_paths', 'password', 'token', 'key', 'credential']
    for (const svc of data.services) {
      for (const field of FORBIDDEN) {
        expect(
          Object.keys(svc).map((k) => k.toLowerCase()),
          `Service ${svc.service_id} exposes forbidden field: ${field}`,
        ).not.toContain(field)
      }
    }
  })
})

describe('run-history.json shape', () => {
  it('has runs array', () => {
    const data = loadEvidence('run-history.json')
    if (!data) return
    expect(data).toHaveProperty('runs')
    expect(Array.isArray(data.runs)).toBe(true)
  })
})

describe('Secret path data not in dashboard-safe evidence', () => {
  const SAFE_FILES = [
    'workspace-registry.json',
    'server-registry.json',
    'service-inventory.json',
    'docs-index.json',
    'logs-index.json',
  ]

  for (const file of SAFE_FILES) {
    it(`${file} does not contain secret path data`, () => {
      const p = resolve(EVIDENCE_DIR, file)
      if (!existsSync(p)) return
      const raw = readFileSync(p, 'utf-8').toLowerCase()
      // These strings should never appear in dashboard-safe files
      const BANNED = ['.env', 'secret_path_index', 'private/']
      for (const banned of BANNED) {
        expect(raw, `${file} contains banned string: "${banned}"`).not.toContain(banned)
      }
    })
  }
})
