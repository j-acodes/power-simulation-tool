import { spawn } from 'node:child_process'
import { createConnection } from 'node:net'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'

const repoRoot = fileURLToPath(new URL('..', import.meta.url))

/** Is something already serving on this port? */
function alreadyServing(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = createConnection({ port, host: '127.0.0.1' })
    const done = (answer: boolean) => {
      socket.destroy()
      resolve(answer)
    }
    socket.on('connect', () => done(true))
    socket.on('error', () => done(false))
    socket.setTimeout(500, () => done(false))
  })
}

// ponytail: dev-only supervisor so `npm run dev` is the single command.
// Starts uvicorn as a child of Vite, restarts it if it dies, and kills it on
// shutdown. Gives up after 3 crashes so a permanently-broken backend (a bad
// venv, say) fails loudly instead of looping.
//
// It stands down entirely when a backend is already listening. That is the
// normal case on a machine running one as a service -- and the old behaviour
// there was four identical "Address already in use" errors per session,
// looking like a fault when nothing was wrong. Vite proxies /api to whatever
// holds the port, so standing down costs nothing.
function backend(): Plugin {
  return {
    name: 'start-backend',
    apply: 'serve',
    configureServer(server) {
      let proc: ReturnType<typeof spawn>
      let stopping = false
      let crashes = 0

      const start = () => {
        const startedAt = Date.now()
        proc = spawn(
          `${repoRoot}.venv/bin/uvicorn`,
          // data/ is watched too, with *.yaml included alongside uvicorn's
          // default *.py: the component catalogue is YAML loaded once at
          // import, so without this a catalogue edit is invisible until a
          // manual restart -- and the app quietly serves a stale catalogue
          // while every test passes against the new one.
          ['backend.main:app', '--port', '8000', '--reload',
           '--reload-dir', 'backend', '--reload-dir', 'powertool', '--reload-dir', 'data',
           '--reload-include', '*.py', '--reload-include', '*.yaml'],
          { cwd: repoRoot, stdio: 'inherit' },
        )
        proc.on('error', (e) => server.config.logger.error(`backend failed to start: ${e.message}`))
        proc.on('exit', (code) => {
          if (stopping) return
          // ponytail: only a rapid crash-loop counts toward the cap. A backend that
          // ran fine for a while and then died gets a clean slate, so a long dev
          // session isn't left unsupervised by unrelated crashes hours apart.
          if (Date.now() - startedAt > 10_000) crashes = 0
          if (++crashes > 3) {
            server.config.logger.error(`backend died ${crashes}x (last exit ${code}); giving up`)
            return
          }
          server.config.logger.warn(`backend exited (${code}); restarting`)
          setTimeout(start, 1000)
        })
      }

      void alreadyServing(8000).then((busy) => {
        if (busy) {
          server.config.logger.info(
            'backend already listening on :8000 — leaving it alone (proxying to it)',
          )
          return
        }
        start()
      })

      const stop = () => {
        stopping = true
        proc?.kill()
      }
      server.httpServer?.on('close', stop)
      process.on('exit', stop)
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), backend()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    // React Testing Library's auto-cleanup-after-each-test hooks itself onto
    // a global `afterEach` — without this it silently no-ops and DOM nodes
    // leak between tests in the same file.
    globals: true,
  },
})
