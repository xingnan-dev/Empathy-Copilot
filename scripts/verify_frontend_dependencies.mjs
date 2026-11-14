// Local HTTP/CSS smoke checks; this does not render a browser or exercise live API mutations.
import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { readFile, readdir, writeFile, unlink } from 'node:fs/promises'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const frontend = path.join(root, 'frontend')
const require = createRequire(path.join(frontend, 'package.json'))
const { createServer, preview } = await import(pathToFileURL(require.resolve('vite')))
const postcss = require('postcss')
const autoprefixer = require('autoprefixer')
const { SourceMapConsumer } = require('source-map-js')
const output = path.resolve(process.argv[2] ?? path.join(root, 'backend/evaluation_output/frontend-dependency-fixes/http-css.json'))
// Tailwind 3 resolves content globs relative to cwd, as in `cd frontend; npm run dev`.
process.chdir(frontend)
const baseline = JSON.parse(await readFile(path.join(root, 'backend/evaluation_output/frontend-dependency-fixes/baseline.json'), 'utf8'))
const result = { level: 'HTTP assets and CSS/source-map processing; no browser interaction or live API operation', checks: [] }
const record = (name, details) => result.checks.push({ name, passed: true, ...details })
const assetDirectory = path.join(frontend, 'dist/assets')
const assetNames = await readdir(assetDirectory)
const cssName = assetNames.find(name => name.endsWith('.css'))
assert.ok(cssName)
const css = await readFile(path.join(assetDirectory, cssName))
const cssHash = createHash('sha256').update(css).digest('hex')
const originalCss = await readFile(path.join(root, 'backend/evaluation_output/frontend-dependency-fixes/baseline.css'))
const originalHash = createHash('sha256').update(originalCss).digest('hex')
assert.ok(Object.values(baseline.assets).some(asset => asset.sha256 === originalHash))
function cssStructure(node) {
  const value = Object.fromEntries(['type', 'name', 'selector', 'prop', 'value', 'important', 'text'].filter(key => node[key] !== undefined).map(key => [key, node[key]]))
  if (node.params !== undefined) {
    // Normalize only the observed, simple responsive/reduced-motion media conditions.
    const normalized = node.params.replace(/\s/g, '')
    value.params = node.type === 'atrule' && node.name === 'media' && /^(\(max-width:\d+px\)|\(prefers-reduced-motion:reduce\))$/.test(normalized) ? normalized : node.params
  }
  if (node.nodes) value.nodes = node.nodes.map(cssStructure)
  return value
}
assert.deepEqual(cssStructure(postcss.parse(css.toString())), cssStructure(postcss.parse(originalCss.toString())))
record('production-css-structure-unchanged', { bytes: css.length, sha256: cssHash, baselineBytes: originalCss.length, baselineSha256: originalHash, normalizedOnly: 'whitespace in simple max-width/prefers-reduced-motion media conditions' })
assert.ok(!assetNames.some(name => name.endsWith('.map')), 'production sourcemaps remain disabled')
record('production-maps-disabled', {})

const input = '.dependency-probe { display: flex; user-select: none; color: #d96d5c; }'
const processed = await postcss([autoprefixer]).process(input, {
  from: path.join(frontend, 'dependency-probe.css'),
  to: path.join(frontend, 'dependency-probe.out.css'),
  map: { inline: false, sourcesContent: true },
})
const map = processed.map.toJSON()
assert.ok(map.sourcesContent.includes(input))
const source = new SourceMapConsumer(map).originalPositionFor({ line: 1, column: 0 })
assert.equal(source.line, 1)
assert.ok(source.source.endsWith('dependency-probe.css'))
assert.ok(processed.css.includes('#d96d5c'))
record('postcss-autoprefixer-source-map-roundtrip', { sources: map.sources, originalLine: source.line })

const deniedName = `.env.dependency-probe-${randomUUID()}`
const deniedPath = path.join(frontend, deniedName)
const marker = randomUUID()
let dev
let built
let probeCreated = false
try {
  await writeFile(deniedPath, marker, { flag: 'wx' })
  probeCreated = true
  dev = await createServer({ root: frontend, server: { host: '127.0.0.1', port: 0 } })
  await dev.listen()
  const base = `http://127.0.0.1:${dev.httpServer.address().port}`
  for (const route of ['/', '/src/main.tsx', '/src/runtime/CaseRuntime.tsx', '/src/demo/cases/S00154.ts']) {
    const response = await fetch(base + route)
    assert.equal(response.status, 200)
    const body = await response.text()
    if (route.endsWith('CaseRuntime.tsx')) {
      for (const entry of ['Enter Demo Fixture Mode', 'approveCase', 'generateResponseDraft', 'ingestConsumerMessage']) assert.ok(body.includes(entry))
    }
    record('dev-asset', { route, status: response.status })
  }
  for (const query of ['', '?raw', '?import&raw', '?import&url&inline']) {
    const response = await fetch(`${base}/${deniedName}${query}`)
    assert.ok([403, 404].includes(response.status))
    assert.ok(!(await response.text()).includes(marker))
    record('dev-deny-synthetic-env', { query, status: response.status })
  }
  const foreign = await fetch(base + '/src/main.tsx', { headers: { Origin: 'https://example.invalid' } })
  assert.equal(foreign.headers.get('access-control-allow-origin'), null)
  record('dev-foreign-origin-not-allowed', {})
  built = await preview({ root: frontend, preview: { host: '127.0.0.1', port: 0 } })
  const previewBase = `http://127.0.0.1:${built.httpServer.address().port}`
  const page = await fetch(previewBase)
  assert.equal(page.status, 200)
  const html = await page.text()
  for (const asset of html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)) {
    const response = await fetch(previewBase + asset[1])
    assert.equal(response.status, 200)
    const body = await response.text()
    if (asset[1].endsWith('.js')) {
      for (const entry of ['S00154', '/human-approval', '/response-draft', '/messages', 'Enter Demo Fixture Mode']) assert.ok(body.includes(entry))
    }
    record('preview-asset', { route: asset[1], status: response.status })
  }
  record('preview-index', { status: page.status })
} finally {
  if (built) await new Promise((resolve, reject) => built.httpServer.close(error => error ? reject(error) : resolve()))
  if (dev) await dev.close()
  if (probeCreated) await unlink(deniedPath)
}
await writeFile(output, JSON.stringify(result, null, 2) + '\n')
console.log(`${result.checks.length} HTTP/CSS checks passed; no browser interaction claimed.`)
