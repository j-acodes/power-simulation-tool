import { afterEach, describe, expect, it, vi } from 'vitest'
import { deleteDesign, seedDiagram } from './api'
import type { SeedParams } from './types'

function reply(status: number, body: unknown) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status })))
}

afterEach(() => vi.unstubAllGlobals())

describe('API errors', () => {
  it("carries the server's reason, not just the status code", async () => {
    reply(400, { detail: "BESS solution 'x' has no rated active power in the catalogue, so it cannot be sized." })
    await expect(seedDiagram({} as SeedParams)).rejects.toThrow(/no rated active power/)
  })

  it('joins validation errors into one message', async () => {
    reply(422, { detail: [{ msg: 'Field required' }, { msg: 'Input should be a valid number' }] })
    await expect(seedDiagram({} as SeedParams)).rejects.toThrow('Field required; Input should be a valid number')
  })

  it('falls back to the status code when the body has no detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('Internal Server Error', { status: 500 })))
    await expect(deleteDesign(1)).rejects.toThrow('HTTP 500')
  })
})
