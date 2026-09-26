# Resonique Demo Operator Guide

## Before the judges arrive

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
