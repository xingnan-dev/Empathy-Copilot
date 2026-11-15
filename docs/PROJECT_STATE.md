# Project State

## Project identity

- **Product:** Resonique
- **Repository:** Empathy-Copilot
- **Role:** Beauty Service Investigation Agent
- **Development mode:** Independent post-competition development, building on the preserved Team Oasis baseline.
- **Operating model:** ChatGPT project `blackkesong` owns planning, product design, review, and project materials; Codex owns code changes, tests, and Git. This repository is the single source of truth.

## Competition history

- **Event:** L'Oréal Beauty Tech Hackathon 2026
- **Team:** Oasis
- **Entry:** Resonique
- **Submission date:** 2026-10-05
- **Competition PPT:** SUBMITTED
- **Demo Video:** SUBMITTED
- **Final Submission Audit:** COMPLETE
- **Competition submission:** COMPLETE
- **Outcome:** The competition has ended and the team did not advance, as reported by the project owner on 2026-11-07.

Submission dates and completed PPT/video records above are historical facts, not current
development requirements. See [the submission manifest](SUBMISSION_MANIFEST.md).

## Product positioning

Resonique is an evidence-aware, stateful investigation agent for beauty-service support. It reconstructs what is known, preserves provenance and uncertainty, and prepares empathetic, actionable next steps for human approval.

## Frozen competition baseline

- **Version:** V1.0 Technical Freeze
- **Release:** Resonique v1.0.0 Competition Submission
- **Historical phase:** Competition delivery freeze (Phase 10.1)
- **Frozen technical baseline:** `44073aca8077e46e187bb4eb7d4f8370a8452c8c`
- **Competition release tag:** `v1.0.0-competition-submission`
- **Competition release commit:** `e77ef5a063179cba3c7aa3cc0a3438d89b5646c2`
- **Freeze scope:** The competition technical baseline and release remain frozen. Independent development proceeds in separately reviewed post-competition increments.

## Core innovations

1. Evidence-aware Reasoning
2. Stateful Investigation Agent
3. Actionable Empathy

## Core principles

- **Understand Before Answer.**
- **Act with Empathy.**
- **LLM proposes. Domain validates. Agent decides. Human approves.**

## Demo cases

- **Primary:** S00154
- **Supporting:** S00001, S00009, Repeat Contact

## Technical stack

- **Frontend:** React, Vite, TypeScript, Tailwind
- **Backend:** Python, FastAPI
- **Agent:** LangGraph
- **Model:** Qwen
- **Database:** PostgreSQL
- **Deployment:** Docker Compose

## Completed phases summary

Phases 0–9 established and validated the evidence/provenance domain, deterministic safety boundaries, stateful LangGraph investigation, business grounding, durable persistence, API and accepted UI, Qwen integration, official competition data, multimodal handling, and evaluation/optimization. Phase 10.1 completed competition delivery readiness and froze accepted product behavior.

Competition Hotfix 1 is complete. Explicit consumer-reported product usage is grounded as `CONSUMER_REPORTED`; for S00154, `exact_product_used = 面霜` and the deterministic NBQ advances to `ACTUAL_FIRST_USE_TIME`.

Competition Enhancement 1 is complete. The deterministic, read-only `ServiceStrategyPolicy` implements **Consumer Signal → Service Strategy → Action**. Emotion remains an auxiliary `AI_INFERENCE`; it does not change Evidence, Attribution, Safety, Agent routing, or human-approval requirements. No new LLM call was added.

## Current restrictions

- The competition version may receive only critical bug, security, or deployment fixes.
- New functionality must enter a separate v1.1 phase and must not directly modify the competition version.
- Do not redesign the accepted UI.
- Do not modify `ui-prototype/` unless explicitly instructed.
- Preserve evidence provenance and deterministic safety boundaries.

## Current work

- **Completed maintenance:** Frontend dependency fixes from `codex/frontend-dependency-fixes`,
  starting from latest main `2a1fee8b26d10ab2251a4e731d006a6f3b54ec42`;
  compatible Vite/CSS/ESLint fixes passed communication-area static review;
  Node22 Docker build/checks and final nginx HTTP delivery verified, **已通过 PR #2 合并 main**;
  minimatch/typescript-eslint residual risk remains open, with no forced override or major downgrade.
  Merge commit `4dbf25f86ec8702f4bb5ef6d8746982bce242279` on 2026-11-14 preserves
  the three reviewed commits through `7b03126b9c9890d03cb0653211d51d02522fc1a2`;
  [PR #2](https://github.com/xingnan-dev/Empathy-Copilot/pull/2). The development branch is retained.
  Scope: dependency upgrades and necessary compatibility adjustments only; no release tag authorized.
  See [dependency review](FRONTEND_DEPENDENCY_REVIEW.md) for verification and remaining risks.
- **Productization branch:** `codex/phase-e3-2-readonly-recovery`
- **Phase E3.1:** Durable tool failure handling implemented and locally validated on isolated
  PostgreSQL: 159 tests passed, 28 skipped for documented official-data/real-model dependencies;
  the PostgreSQL subset passed 20 checks with one official-data skip. Ruff and mypy passed.
  See [W0 validation](W0_VALIDATION.md) for scope, environment, and limitations. W0/E3.1 review was accepted on 2026-11-14; the frozen competition tag and commit remain unchanged.
- **Implementation commit:** `a89bed63f5581280d4c2041016ba5f9645ec5a79`.
- **Current phase:** 沟通区最终评审通过；**E3.2 已完成，已合并 main**.
- **Merge record:** [PR #1](https://github.com/xingnan-dev/Empathy-Copilot/pull/1),
  merge commit `a719fab1e922c9a41ecb6f1381b9641ea2d75a4e` on 2026-11-14;
  reviewed range `e77ef5a..bfef0b3` (18 commits), preserved without squash or rebase.
  Local main was fast-forwarded to the remote merge; the development branch and competition tag remain intact.
- **W4 starting checkpoint:** `00b946368bc3a0f69f9ba139673fe5d569fe780b`.
  [Delivery record](W4_DELIVERY.md) covers clean-checkout verification, documentation and demo;
  video: 经负责人决定取消, with no video gate on final acceptance, merge or release.
  W4 acceptance covers code, tests, fault experiments, clean checkout, documentation and Git status.
  Frontend dependency remediation is tracked independently below; residual risk and release tags require separate communication-area review.
- **W2 verification:** [Execution and validation handoff](W2_VALIDATION.md): 218 passed,
  28 external-input skips; PostgreSQL subset 36 passed / 1 official-data skip; Ruff and mypy passed.
  Implementation checked at `da131051af0f4849b6ae2a3677e15e7c887ba8f8`.
- **Plan:** [Post-competition engineering plan](POST_COMPETITION_PLAN.md); further recovery work
  follows the reviewed D2 contract; W3/F5 process verification and E3.2 final acceptance passed; main merge is complete; release confirmation remains pending.
- Keep the competition technical baseline and submission tag frozen during independent development.
- **Accepted post-competition baseline:** `ff1e35b4ba67e952386253a09d772e0e6918965a`.
  W2 now implements manual readonly recovery; W3/F5 independent-process acceptance has passed communication-area review.

## Reading and operation

- Follow [AGENTS.md](../AGENTS.md) for the required development reading order; the completed product phase
  is [E3.2 / W4](phases/PHASE_E3_2.md). Completed dependency maintenance and its open residual risk follow the
  [independent review](FRONTEND_DEPENDENCY_REVIEW.md), without expanding product scope.
- Use the [run guide](COMPETITION_RUN_GUIDE.md) for local setup and data-source requirements,
  and the [operator guide](DEMO_OPERATOR_GUIDE.md) for the existing demonstration paths.
- Historical phase requirements and submission records remain available as baseline evidence;
  they do not set new submission deadlines or replace current phase acceptance criteria.


## E3.2 final acceptance boundary

沟通区已确认本轮交付完成，完成前交付记录为 `6f5ca51ce368da348649a0b77a1e63d06a5b72a0`。
验证依据沿用 [W2](W2_VALIDATION.md)、[W3](W3_VALIDATION.md)、[F5补验](W3_F5_SUPPLEMENT.md)
和 [W4干净检出](W4_DELIVERY.md)，不因文档收尾声称重新运行测试。
视频经负责人决定取消；27项官方工作簿和1项真实Qwen测试跳过范围保留。
恢复限定本地单API工作进程；退出条件与操作者身份是声明，不是认证或跨主机fencing。
旧程序读取新增字段的回滚限制保留，需配套数据库备份，不能删除恢复历史后降级。
[前端依赖修复](FRONTEND_DEPENDENCY_REVIEW.md)已通过兼容升级及Node22 Docker补验评审，并通过PR #2合并main；
audit由14条降至7条中危，均关联同一minimatch公告，剩余风险未关闭，不宣称全部修复。
前端测试5通过，类型检查/lint/构建/npm ci通过；15项HTTP/CSS检查不替代浏览器交互验收。
Docker补验使用Node22.23.5/npm10.9.9、Linux/amd64及nginx1.27.5，同样5项测试通过；
最终首页和JS/CSS均HTTP200，内容摘要匹配；本次容器/验证镜像标签已清理，既有业务容器保持原状态。
Dockerfile与锁文件未改，minimatch风险独立开放；浏览器交互和基础镜像CVE扫描仍未验证，不重跑后端故障矩阵。

## Basic CI implementation (2026-11-15)

Active branch: `codex/basic-ci`, starting commit `e4c6f1215f1cbdbbd81887695e55744cc5524065` (latest remote main, clean worktree). Three independent jobs reuse existing checks; basic CI reviewed and merged via PR #3; main protection enabled by subsequent owner authorization. No product/dependency/migration changes or release tag authorized. Official workbook/real Qwen inputs are absent; full W3 experiments are outside first required checks. Frontend minimatch risk remains open.

### CI real-run evidence

[PR #3](https://github.com/xingnan-dev/Empathy-Copilot/pull/3), [first Actions run](https://github.com/xingnan-dev/Empathy-Copilot/actions/runs/43694363196).
Source ab5e72fdd6dcb50c5affa90df5a43c3c6ea5e45c; checkout used GitHub PR synthetic merge 9bbf3c9 into main e4c6f12.
- backend: pip install -e ".[dev]", Ruff check ., mypy, pytest -m "not postgres" -rs --tb=short; 185 passed/27 skipped/37 deselected, job48s, tests2.25s.
- postgres: fresh postgres:16-alpine service, dedicated resonique_ci_test, health readiness, no volumes/business secrets; pytest -m postgres;36 passed/1 skipped/212 deselected, job47s, tests4.98s.
- frontend: Node22, npm ci/test/typecheck/lint/build;5 passed/0 skipped, job54s.
Skipped: backend26 official-workbook tests +1 real-Qwen credentials test; PostgreSQL1 official-import test. Full W3 process experiments not invoked. No skip is counted as passing. Remaining minimatch risk is not suppressed by disabling any job; npm audit is not a required check in this first scope.
Actions checkout v4, setup-python v5, setup-node v4, upload-artifact v4 were verified against their official repository tag refs and pinned to full SHAs. Official usage documentation: [checkout](https://github.com/actions/checkout), [Python](https://github.com/actions/setup-python), [Node](https://github.com/actions/setup-node), [artifacts](https://github.com/actions/upload-artifact).
All run commands use explicit bash -e -o pipefail; no continue-on-error. Read-only contents permission, no business credentials, checkout does not persist credentials. Logs and backend/PostgreSQL JUnit uploaded with always(), retained14days. Every job timeout15minutes. PR-to-main, main push and workflow_dispatch triggers; manual dispatch becomes generally available after workflow reaches default branch.
Local Ruff/mypy passed; non-PostgreSQL local tests186 passed/26 skipped (local environment differed for Qwen opt-in; remote isolated result above is the CI baseline). Initial sandbox interpreter startup failed; environment permission allowed preflight to run. No remote job failures or CI compatibility patches were necessary. No dependency, behavior or migration change.
Suggested stable required check names after review: `backend`, `postgres`, `frontend`. No branch-protection settings changed. Artifacts can expire; the run URL and summary remain the audit entry.

### CI merge and main gate (2026-11-15)

PR #3 merged with merge commit `ce3bd82c2e2522f76c59b33dfed3112329d6cd36`, preserving ab5e72f and0b561e2. Latest source0b561e2 had all three checks pass on PR synthetic merge100963b before merge.
The actual main push [run43695412924](https://github.com/xingnan-dev/Empathy-Copilot/actions/runs/43695412924) independently completed successfully on ce3bd82: backend/postgres/frontend all passed, not inferred from PR results.
Main branch protection was successfully applied and read back through GitHub REST API: PR required, zero approving reviewers, no code-owner or last-pusher approval; strict up-to-date backend/postgres/frontend checks bound to GitHub Actions App ID15368; administrators included; force pushes and main deletion prohibited. No prior branch protection or active rulesets existed to overwrite. Linear history is not required, so merge commits remain usable. No bypass allowances were added.
[Protection API evidence](https://api.github.com/repos/xingnan-dev/Empathy-Copilot/branches/main/protection); [official API semantics](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection).
This status update itself follows a separate PR and the same three checks. Future documentation also follows PR/check delivery; no direct push to main. Remaining minimatch risk, official-data/Qwen skips, full W3 exclusion, browser and image-CVE unverified boundaries remain unchanged. No deployment or release tag added.

### Browser acceptance preparation (2026-11-15)

Branch codex/browser-acceptance starts at latest main bb4916a745556c2db3cb1030b022fbaaf7ef6dcf.
[Delivery record](W4_DELIVERY.md) contains actual UI entry inventory, browser-control tooling gap and manual checklist.
All six browser acceptance paths remain UNEXECUTED; no screenshot/browser-version/console evidence exists.
Installed browser executables do not imply a working browser-control session. No new framework, product change or temporary runtime resources created.
Message success additionally needs a deterministic experimental model provider; no-credentials unavailable variant must remain explicit.
Documentation follows PR/required checks; no merge authorized. Existing limitations and minimatch risk unchanged.

### Real browser acceptance follow-up (2026-11-15)

Preparation status above is historical at85fbac6. Owner authorized Playwright dev tooling; actual Chrome acceptance and a minimal favicon404 fix are in e8e8e31.
[W4 results](W4_DELIVERY.md) distinguish five passing browser-script modes from six acceptance paths: path4 is PARTIAL because newly sent raw chat bubble disappears after reload, although Evidence and state persist. Other paths executed with real frontend/single-worker API/disposable PostgreSQL, fake or absent model, no real Qwen/workbook.
Do not call full E2E accepted solely from green CI. Raw-message persistence/display contract needs communication-area review before expanding storage/API behavior. PR #5 remains unmerged; minimatch and previous external-input/image-CVE boundaries remain open.

### Message persistence design pending review (2026-11-15)

Owner confirmed raw chat refresh gap. [Minimal design](phases/PHASE_MESSAGE_PERSISTENCE.md) proposes a distinct inbound-message table and transaction-bound checkpoint adapter, preserving official history and E3.2 boundaries. Design only: no product/dependency/migration changes implemented. PR #5 stays unmerged; browser scripts, screenshots and partial acceptance results retained. Implementation waits for communication-area review.

### 消息持久化修复：已实施，待沟通区评审

规格17ac624已通过沟通区评审，按M1–M6实施；PR #5不合并，既有浏览器部分通过证据保留。

M1–M6实现与本地验收结果见[W4新增记录](W4_DELIVERY.md)：246通过/27官方数据跳过/1真实Qwen排除，
真实Chrome九模式90断言，原刷新缺口的新结果通过；旧部分通过记录不改写。
负责人已确认保留Evidence.metadata.original_message作为既有溯源，消息表为展示/幂等权威来源，State不新增聊天数组。
提交a7b91f9、f22b6f6、ff61ec7及后续交付记录更新PR #5；不合并、不发布。上线先备份/迁移，含消息降级拒绝删表；剩余授权、隐私、minimatch和外部输入边界保留。

### LIVE原文溯源补订：已实施，待沟通区评审

PR #5暂缓合并。关联Evidence已有original_message时与消息表text精确比较，冲突HTTP409 / MESSAGE_PROVENANCE_CONFLICT；写入整笔回滚，GET/重放同样拒绝冲突，缺字段兼容且不补造。针对性31项通过，Ruff/mypy通过；最新三个CI以PR检查为准。详见[W4补验记录](W4_DELIVERY.md)。本轮不重复完整浏览器/W3矩阵，原限制保留。
