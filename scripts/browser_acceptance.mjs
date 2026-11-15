import { createRequire } from 'node:module'
import { writeFile, access } from 'node:fs/promises'
import path from 'node:path'
const require = createRequire(path.resolve('frontend/package.json'))
const { chromium } = require('@playwright/test')
const output = process.env.BROWSER_OUTPUT
const mode = process.env.BROWSER_MODE
const base = process.env.BROWSER_FRONTEND
const api = process.env.BROWSER_API
const evidence = { mode, checks: [], console: [], requests: [] }
const browser = await chromium.launch({ channel: 'chrome', headless: true })
evidence.browser = browser.version()
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
await context.tracing.start({ screenshots: true, snapshots: true })
const page = await context.newPage()
page.on('pageerror', error => evidence.console.push({ type: 'pageerror', message: error.message }))
page.on('console', message => { if (message.type() === 'error') evidence.console.push({ type: 'error', message: message.text(), location: message.location() }) })
page.on('response', response => { if (response.url().startsWith(api) || response.status() >= 400) evidence.requests.push({ path: new URL(response.url()).pathname, method: response.request().method(), status: response.status() }) })
const assert = (condition, name) => { if (!condition) throw Error(name); evidence.checks.push(name) }
const snapshot = async name => page.screenshot({ path: path.join(output, `${mode}-${name}.png`), fullPage: true })
const get = async () => (await context.request.get(`${api}/api/cases/S00154`)).json()
try {
 await page.goto(base)
 await page.getByRole('button', { name: 'Prepare response', exact: true }).waitFor()
 await snapshot('loaded')
 const before = await get()
 assert(before.evidence.every(x => x.source && x.provenance), 'source provenance present')
 assert(before.gaps.length > 0 && before.lifecycle === 'WAITING_FOR_HUMAN', 'gaps and lifecycle loaded')
 assert((await page.locator('body').innerText()).includes('S00154'), 'real case rendered')
 if (mode === 'message' || mode === 'unavailable') {
  await page.getByLabel('Consumer message').fill('我实际用的是面霜。')
  const responsePromise = page.waitForResponse(r => r.url().endsWith('/messages'))
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const response = await responsePromise
  const after = await get()
  if (mode === 'message') {
   assert(response.status() === 200, 'message accepted by real backend with fake provider')
   assert(after.revision > before.revision && after.evidence.length > before.evidence.length, 'message evidence persisted')
   await page.getByText('我实际用的是面霜。', { exact: true }).waitFor()
   assert(after.evidence.some(x => x.type === 'CONSUMER_REPORTED' && JSON.stringify(x).includes('面霜')), 'consumer evidence source retained')
   assert(!(after.gaps.some(x => x.id === 'EXACT_PRODUCT_USED' && x.status === 'OPEN')), 'confirmed product resolves corresponding gap')
   const post = await response.json()
   assert((await page.locator('body').innerText()).includes(after.current_action), 'page shows backend next action')
   assert(post.current_action === after.current_action && post.revision === after.revision, 'message response next action matches reloaded state')
  } else {
   assert(response.status() === 503, 'no-model request unavailable')
   await page.getByText('Model understanding unavailable. Please retry.', { exact: true }).waitFor()
   assert(after.revision === before.revision, 'unavailable message did not change state')
  }
  await snapshot('message')
  await page.reload()
  await page.getByRole('button', { name: 'Prepare response', exact: true }).waitFor()
  const restored = await get()
  assert(JSON.stringify(restored.evidence) === JSON.stringify(after.evidence) && restored.revision === after.revision, 'refresh preserves evidence and revision')
  assert((await page.locator('body').innerText()).includes(after.current_action), 'refreshed page shows persisted next action')
  evidence.originalMessageBubbleAfterReload = await page.getByText('我实际用的是面霜。', {exact:true}).count()
  await snapshot('refreshed')
 }
 if (mode === 'approval') {
  assert(before.human_checkpoint.can_approve, 'fixture can approve')
  await page.getByRole('button', { name: 'Prepare response', exact: true }).click()
  await page.getByText('Fallback Draft', { exact: true }).waitFor()
  const responsePromise = page.waitForResponse(r => r.url().endsWith('/human-approval'))
  await page.getByRole('button', { name: 'Approve escalation', exact: true }).click({ clickCount: 2 })
  await responsePromise
  await page.getByRole('heading', { name: 'High-impact action approved' }).waitFor()
  const after = await get()
  assert(after.human_checkpoint.state === 'APPROVED' && after.revision === before.revision + 1, 'approval exactly one revision')
  const stale = await context.request.post(`${api}/api/cases/S00154/human-approval`, { data: { expected_revision: before.revision } })
  assert(stale.status() === 409 && (await stale.json()).message.includes('Refresh'), 'stale revision rejected with readable feedback')
  assert((await get()).revision === after.revision, 'no duplicate approval')
  await snapshot('approved')
  await page.reload()
  await page.getByRole('button', { name: 'Prepare response', exact: true }).waitFor()
  assert((await get()).human_checkpoint.state === 'APPROVED', 'approval survives refresh')
 }
 if (mode === 'conflict') {
  await page.getByRole('button',{name:'Prepare response',exact:true}).click()
  await page.getByText('Fallback Draft',{exact:true}).waitFor()
  const external = await context.request.post(`${api}/api/cases/S00154/human-approval`,{data:{expected_revision:before.revision}})
  assert(external.status()===200,'independent client approved before stale UI click')
  await page.getByRole('button',{name:'Approve escalation',exact:true}).click()
  await page.getByRole('alert').filter({hasText:'Case updated elsewhere. Refresh current state.'}).waitFor()
  assert((await get()).revision === before.revision+1,'stale UI does not repeat approval')
  await snapshot('conflict-feedback')
 }
 if (mode === 'outage') {
  const waitFile = async name => { for(let i=0;i<300;i++){try{await access(path.join(output,name));return}catch{await new Promise(r=>setTimeout(r,100))}}throw Error('handshake timeout') }
  await writeFile(path.join(output,'stop-api'),'ready')
  await waitFile('api-stopped')
  await page.reload()
  await page.getByRole('heading',{name:'Unable to load live case state.'}).waitFor()
  await snapshot('offline')
  await writeFile(path.join(output,'restart-api'),'ready')
  await waitFile('api-restarted')
  await page.getByRole('button',{name:'Retry',exact:true}).click()
  await page.getByRole('button',{name:'Prepare response',exact:true}).waitFor()
  assert((await get()).revision === before.revision,'restart reads persisted revision')
  await snapshot('reconnected')
 }
 evidence.state = await get()
 assert(!evidence.console.some(x => x.type === 'pageerror'), 'no uncaught browser exceptions')
 evidence.status = 'PASSED'
} catch (error) { evidence.status = 'FAILED'; evidence.error = String(error); await snapshot('failure'); process.exitCode = 1 }
finally { await context.tracing.stop({ path: path.join(output, `${mode}-trace.zip`) }); await browser.close(); await writeFile(path.join(output, `${mode}.json`), JSON.stringify(evidence, null, 2)) }
