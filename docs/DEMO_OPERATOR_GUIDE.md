# Resonique Demo Operator Guide

These existing case demonstrations remain useful for local review of the preserved baseline.
Current development scope and pending verification are recorded in
[PROJECT_STATE.md](PROJECT_STATE.md); startup and data-use requirements are in the
[run guide](COMPETITION_RUN_GUIDE.md). Competition submission and judging constraints do not
apply to this operating checklist.

## Current three-minute synthetic-data recovery demo

This terminal/API demonstration uses two independent synthetic cases: a normal-query control,
then a comparable case with an injected readonly timeout. A completed logical query is not forced
back into failure. React retains its existing case display; recovery is operated through API/CLI.
Start from the environment in the [run guide](COMPETITION_RUN_GUIDE.md).

```powershell
.\.venv\Scripts\python scripts/tool_recovery_experiment.py --cases F0 F6 --repetitions 1
```

Copy the printed report directory into `$reportDirectory`, then inspect the actual run:

```powershell
$run = Get-Content (Join-Path $reportDirectory 'report.json') -Raw | ConvertFrom-Json
$normal = $run.results | Where-Object scenario -eq 'F0'
$recovery = $run.results | Where-Object scenario -eq 'F6'
$failure = $recovery.checkpoints | Where-Object label -eq 'failure_before_restart'
$final = $recovery.checkpoints | Where-Object label -eq 'final'
$failure.state | Select-Object status,state_revision,tool_calls
$final.state.tool_calls | Format-Table id,status,attempt_sequence,previous_attempt_id
$final.state.evidence | Select-Object id,key,source
$final.counts
```

The harness actually starts a single API, injects TimeoutError in the readonly experimental tool,
waits for the old API to exit, starts a new one, sends an explicit recovery request, then repeats
the identical request. That replay must return200 without another tool entry. The F6 final total
is2 entries/1 return: one failed call plus one successful recovery; replay adds0. Request history,
source Evidence and wait-confirmed process records are in the report. No real provider outage or
business transaction is being simulated as a measured production result.

| Time | Show | Suggested narration |
| --- | --- | --- |
| 0:00–0:30 | F0 final state and sourced order | “先看正常查询：购买来自订单记录，仍不代表实际使用，更不能证明因果。” |
| 0:30–1:10 | F6 failure snapshot and FAILED record | “另一个本地合成案件注入只读超时。失败被保存，没有成功证据，系统暂停等待人工处理。” |
| 1:10–1:45 | Old process exit record, new API, recovery request | “脚本确认原API进程退出后重启。人工请求携带目标尝试、修订号和恢复原因。” |
| 1:45–2:25 | FAILED parent, COMPLETED child, Evidence source | “恢复创建新尝试，保留失败历史。结果继续经过Grounding，随后调查进入下一条追问。” |
| 2:25–3:00 | Replay result/count invariant and limitations | “重复同一请求只读已有进度，不重新查询。这是本地单进程人工恢复；跨主机接管和真实权限认证仍不在范围内。” |

For completed-query crash continuation and its separate positive control:

```powershell
.\.venv\Scripts\python scripts/tool_recovery_experiment.py --cases F5 --repetitions 1
```

Use [F5 supplementary evidence](W3_F5_SUPPLEMENT.md) for the zero-CLI-query conclusion. Parent process
execution_counts alone cannot establish it. Video status is **pending delivery**: this execution
session has no available screen-capture interface and neither FFmpeg nor OBS was found. Actual
terminal/API execution evidence is retained in [W4 delivery](W4_DELIVERY.md); no video is claimed.

## Existing baseline demonstrations

The sections below retain the accepted S00154/supporting-case paths. Official cases require the
workbook and verified usage permission; they are not prerequisites for the synthetic recovery demo.

## Before a local demonstration

1. Start with `docker compose up --build` and wait for all three services to become healthy.
2. Confirm `http://localhost:8000/health` returns `{"status":"ok"}`.
3. Confirm the organizer workbook is configured for S00001/S00009; never display its local path.
4. Open the S00154 UI plus prepared read-only API views for S00001/S00009. Keep secrets and
   terminals containing environment values off screen.

## MAIN DEMO — S00154

### Step 1 — Open the primary case

Open `http://localhost:5173/`.

**Expected UI:** Current Case S00154, HIGH ATTENTION, evidence and open gaps.

**Narration:** “Resonique first reconstructs what is known and where each fact came from.”

### Step 2 — Inspect Evidence and Meaning

Open the Intelligence view and point to consumer-reported versus verified business provenance.

**Expected:** Consumer report remains distinct from order/service facts; unknowns remain visible.

**WOW MOMENT:** The system refuses to turn purchase, timing, or the consumer's causal assertion into
confirmed product attribution.

### Step 3 — Show safety and action

Scroll to Action/Response Studio.

**Expected:** SAFETY path, attribution is not `SUPPORTED`, `ESCALATE`, and Human Approval Required.
Generate a response only if Qwen is available; otherwise show the explicitly labelled fallback/error.

### Step 4 — Prove durability

Refresh the browser.

**Expected:** Evidence, gaps, revision, and checkpoint state persist.

## SUPPORTING DEMO — S00001

### Step 1 — Open the official case

Open the prepared `GET http://localhost:8000/api/cases/S00001` response view.

**Expected:** Official image reference exists, while asset availability remains false/unavailable.

**Narration:** “The organizer workbook references an image, but the image asset was not supplied.”

### Step 2 — Show the independent vision acceptance

Use the prepared acceptance result for the synthetic broken-pump fixture; do not attach it to the
official case or call it an official image.

**Expected:** Provenance `DEMO_FIXTURE`, `fixture=true`, type `AI_OBSERVATION`.

**WOW MOMENT:** Even real Qwen Vision output remains an observation—not a verified fact, defect
verdict, causal attribution, medical conclusion, or automatic replacement decision.

## SUPPORTING DEMO — S00009

### Step 1 — Open the logistics conflict

Open the prepared `GET http://localhost:8000/api/cases/S00009` response view.

**Expected:** Verified “delivered” business record and consumer-reported “not received” claim both
remain visible; neither overwrites the other.

### Step 2 — Follow Agent activity

Point to the completed logistics tool and grounded Evidence, then the waiting/checkpoint state.

**Expected:** `CALL_TOOL` → business record → Evidence grounding → `WAIT`.

### Step 3 — Resume the existing investigation

Use the prepared deterministic resume flow with later logistics evidence.

**Expected:** Existing checkpoint resumes, gaps are reevaluated, and the case concludes without
changing the attribution invariant.

**WOW MOMENT:** Resonique does not merely answer; it pauses and continues the same investigation.

## REPEAT CONTACT

### Step 1 — Return to S00154

Refresh or open a second `http://localhost:5173/` tab after the primary demo.

**Expected:** Context Passport, prior evidence, order/service history, question history, and
completed tools are restored from the durable state.

### Step 2 — Show continuity

Point to restored context and the next unresolved gap.

**Expected:** Known information is not re-asked and completed lookups are not repeated.

**WOW MOMENT:** The consumer does not need to repeat the story.

## Failure-safe operator rule

If Qwen, PostgreSQL, an official asset, or the API is unavailable, show the real labelled error or
safe fallback. Never claim a model call succeeded, substitute the synthetic fixture for an official
image, edit database state live, or auto-send a response.
