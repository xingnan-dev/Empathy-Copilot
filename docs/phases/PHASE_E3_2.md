# Phase E3.2 — D2 人工只读恢复规格

2026-11-14；W1 交付，待沟通区评审。本文确定 W2 实现契约，不表示功能已实现。
产品范围、F0–F12 定义沿用 [赛后计划](../POST_COMPETITION_PLAN.md)，不重复扩展。

## 交接与现状

W0 已于本轮获项目负责人评审通过，基线为
`ff1e35b4ba67e952386253a09d772e0e6918965a`。起始工作区干净；E3.2 分支与该提交相同。
[W0 记录](../W0_VALIDATION.md)中的 PostgreSQL 跳过项为
`backend/tests/test_phase4_postgres.py::test_official_import_is_idempotent_and_reconstructs_after_restart`：
未配置 OFFICIAL_DATASET_PATH，涉及官方工作簿导入、幂等性与案例重建，非 E3.1 必需验证。
E3.1 本地失败持久化、重启读取和冲突检查已通过；本轮不补跑官方数据测试。

现有 `_execute` 按 invocation_id 或工具名/参数找到任意旧调用即返回；`_replace_call`
按 id 更新记录；决策器扫描全部未完成记录、完成检查只按工具名；这些行为尚不支持恢复链。
已有 `WAITING_FOR_HUMAN → INVESTIGATING` 转换和 PostgreSQL 修订号条件更新可复用。
API 前缀实际为 `/api/cases`。应用尚无恢复服务、请求账本或执行资格对象。

## 1. 模型契约

沿用 State JSONB 和 ToolCallRecord，不新增业务关系表。全部新模型 extra=forbid；
新审计时间使用带时区 UTC datetime；空白字符串拒绝，不静默裁剪改变请求内容。

### 身份与字段

逻辑调用键为现有 `_invocation_id(case_id, tool_name, canonical_arguments)`，保持当前
SHA-256 前 32 位算法及 JSON sort_keys/separators/ensure_ascii 规则。还必须比较实际
工具名和规范参数，哈希相同而内容不同拒绝，不能误合并。相同案件/工具/参数仍表示同一查询需求；
本阶段不提供已完成查询的刷新入口。

ToolCallRecord 原字段保持；新增字段如下：

| 字段 | 类型/默认 | 语义与校验 |
| --- | --- | --- |
| attempt_sequence | int 或 None，默认 None | 新链根为 1，恢复为父序号+1；旧根 None 在查询投影中视为序号 1，不回填历史 |
| previous_attempt_id | str 或 None，默认 None | 后续尝试必须指向同案件、同逻辑调用的唯一当前叶节点 |
| recovery_request_id | UUID 或 None，默认 None | 后续尝试必须关联同案件账本记录；根为 None |

`id` 是尝试身份：新普通根仍使用 tool-{invocation_id}，恢复尝试使用 attempt-{UUID4}；
旧 id 不改写。`invocation_id` 原默认 None 保留，旧记录在纯函数投影中计算逻辑键。
`attempt_count` 不作尝试序号：保留旧值，旧缺失仍为 0；新 PENDING 为 0，RUNNING 置 1，
终态保留 1。它表示进入运行阶段，不证明工具入口或外部副作用已发生。

State 新增 `tool_recoveries: list[ToolRecoveryRecord] = []`。
每条记录字段均必填，无业务默认：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| request_id | UUID | 案件内唯一 |
| target_attempt_id / new_attempt_id | str | 分别引用父与子尝试 |
| logical_call_id | str | 与父子规范逻辑键一致 |
| expected_revision | int >= 0 | 原请求值，参与内容绑定 |
| operator_id | str，1–128 字符 | 操作者声明，不是认证身份 |
| reason | str，1–1000 字符 | 禁止放凭据；保留原文供审计 |
| previous_process_exited | bool | 接受请求必须为 true |
| accepted_at | UTC datetime | 实际领取时间 |
| interrupted_status | PENDING / RUNNING / None | 父为未完成时保存其原状态，FAILED 时 None |

请求内容以这些原始请求字段逐项比较，不仅比较摘要。accepted_at、new_attempt_id 由服务生成。
失败尝试原记录永不被后续尝试覆盖。中断父记录保持原 PENDING/RUNNING 和原时间；账本
interrupted_status 明确记录“人工确认中断并接替”，不伪造失败发生时间或成功结束时间。

State 新增 `human_review_blocks: list[str] | None = None`，受控取值为 TOOL_RECOVERY、
SAFETY、BUSINESS_REVIEW、QUESTION_LIMIT、OTHER。None 表示旧状态未记录原因，绝不解释成空列表。
新流程每次进入人工等待都明确设置完整原因集合；恢复只移除 TOOL_RECOVERY，不能清除其他原因。
旧等待状态只有 E3.1 的已知确定性工具失败/未完成暂停转换、匹配工具记录，且无其他审核信号时，
允许纯函数识别为仅 TOOL_RECOVERY；无法唯一识别即 OTHER。实现需对白名单转换 reason 使用精确
匹配/固定模板参数校验，不使用 LLM 或模糊子串推断。原 reason/events 不改写。

新写入的映射固定：工具失败及未完成调用暂停为 TOOL_RECOVERY；严重程度或场景安全升级
为 SAFETY；human_review_required 为 BUSINESS_REVIEW；追问次数/去重阻断为 QUESTION_LIMIT；
其他人工等待为 OTHER。多个原因取并集；已存在的非工具原因保持，普通审批只能通过原审批入口解除。
旧原因精确适配范围仅限 tools.py 的 `Business tool {tool_name} failed; manual recovery is required.`
和 decision.py 的 `Tool invocation {id} requires manual recovery before another execution.`，
必须匹配最后正式事件及实际当前调用，其余一律 OTHER。

### 全局校验

调用 id、请求 id 唯一；每逻辑调用恰有一个根，链无环、无分叉，每父最多一个子。
旧快照如存在同逻辑键多根，拒绝恢复并报 LEGACY_AMBIGUITY，不擅自合并或丢弃记录。
加载无恢复结构的历史数据仍按旧规则校验；新恢复结构必须整链合法。
每个非根必须同时有 sequence、previous_attempt_id、recovery_request_id；根不得携带恢复关联。
父必须 FAILED/RETRYABLE 或经 interrupted_status 明确接替的未完成记录，不能接替 COMPLETED。
账本父子反向引用一一对应，工具和参数不变；失败/未完成记录不得有成功 Evidence ids。
现有跨案件、Evidence 引用、生命周期、修订号校验继续执行；不允许 model_copy 绕过校验。

## 2. 执行及选择规则

新增纯函数 `effective_tool_calls(state)`（services/tool_attempts.py）：按校验过的显式链
返回各逻辑调用唯一叶节点；未被接替的任何失败仍有效。不得按列表末项或时间最大值选成功。

| 位置 | W2 最终行为 |
| --- | --- |
| `_execute` 普通路径 | 无记录才准备根；当前叶 COMPLETED 复用结果；PENDING/RUNNING/FAILED 均不执行且交给策略暂停 |
| `execute_recovery` 新路径 | 只接受本次领取成功返回的进程内 RecoveryExecutionPermit；无 permit 即拒绝，不能从数据库记录构造资格 |
| `_replace_call` | 只更新同一尝试的生命周期，保持 id、关联、参数、sequence；找不到或重复 id 拒绝；新尝试只能 append |
| `_execute` 记录构造 | 每次转换必须保留关联字段，不能重建时丢失父/request 引用 |
| decide 的阻塞谓词 | 只扫描有效叶节点；成功子接替历史失败后可继续，其他链的未完成状态仍阻断 |
| `_completed_tool` | 使用同一选择器，按调用所需工具名及规范参数查询对应叶；不能被其他参数的历史成功满足 |
| workflow.run | 普通重入遇到恢复 PENDING/RUNNING 仍暂停；只有恢复服务持有 permit 的调用可跳过普通调度执行该尝试 |

permit 是服务内部不可序列化对象，包含 case、request、attempt、领取后 revision 和一次性 consumed
状态。同步领取函数仅在 CAS 提交明确成功后返回它；执行入口先消费 permit，再对该 PENDING
执行 RUNNING 条件写入，只有写成功才调用工具。禁止反序列化、API 传入或后台扫描执行。
提交结果不确定时不返回 permit，不猜测是否成功；客户端通过同请求重放/GET 核实。

## 3. HTTP 契约

POST `/api/cases/{case_id}/tool-recoveries`；GET
`/api/cases/{case_id}/tool-recoveries/{request_id}`。均为受控本地入口，无新增认证承诺。
POST 必填且无默认：request_id(UUID)、target_attempt_id(str)、expected_revision(int>=0)、
operator_id、reason、previous_process_exited(bool)，长度按模型表；拒绝额外字段。
客户端不能提交新工具名、参数、尝试序号、分类或执行许可。

固定成功响应字段：case_id、request_id、logical_call_id、target_attempt_id、attempt_id、
attempt_status（既有四状态）、failure_kind（可空）、error_summary（可空且脱敏）、
result_evidence_ids（列表）、accepted_revision（expected_revision+1）、current_revision、
lifecycle、current_action（可空）、continuation（PENDING/RUNNING/SETTLED/INTERRUPTED）、replayed(bool)。
工具状态与案件生命周期分列，不将查询成功等同整个案件结案。
首次请求同步执行并续接；正常结束 201。重复 POST 和 GET 对已稳定结果返回 200；
PENDING/RUNNING 或已完成工具但调查尚未续接返回 202，附 Location 指向 GET。
GET 的 replayed=false；重复 POST 为 true。响应投影最新持久化状态，不缓存旧修订号响应。

新增账本字段 `continuation: enum = PENDING`：领取时 PENDING，工具开始时 RUNNING，
失败暂停或续接落库后 SETTLED；新请求接替未完成尝试时父请求（若有）标 INTERRUPTED。
上述字段变化与相应 State 转换一起提交。工具 COMPLETED 到续接之间允许 RUNNING：
此时重放只读，不自动续接；进程退出后通过现有普通工作流重入继续（不重新查询），
下一正式转换将对应账本标 SETTLED，纳入 F5 检查。

处理顺序固定：解析结构 → 加载案件 → 查 request_id → 相同内容返回进度（不检查原旧 revision）
或不同内容 409 REQUEST_ID_CONFLICT → 新请求检查 revision → 目标/资格/安全/预算 → 原子领取。
CAS 失败后重新读取请求账本：若同 id 同内容已存在则只读返回；否则 409 REVISION_CONFLICT。
未接受的错误请求不持久化账本，不占用请求 id。跨案件 request_id 独立，不泄露另一案件内容。

错误沿用 ErrorView 的 code/message 表达：422 INVALID_REQUEST（字段错误）；404 CASE_NOT_FOUND /
RECOVERY_NOT_FOUND / ATTEMPT_NOT_FOUND；409 REQUEST_ID_CONFLICT / REVISION_CONFLICT /
ATTEMPT_SUPERSEDED；409 RECOVERY_NOT_ALLOWED（终态、非允许工具、分类禁止、状态不符）；
409 HUMAN_REVIEW_BLOCKED / PROCESS_EXIT_UNCONFIRMED / STEP_BUDGET_EXHAUSTED / LEGACY_AMBIGUITY；
503 RECOVERY_STORAGE_UNAVAILABLE（含提交回执不确定）。不得把数据库异常/密钥写入响应。
工具业务失败已被接受则仍返回 201，attempt_status=FAILED，保留 failure_kind，不能伪装 HTTP 未领取。
回包丢失时先 GET，404 可用完全相同请求重放；200/202 不再执行。不得为“重试 HTTP”换 request_id。

## 4. 资格、原子领取与安全

唯一允许恢复工具为 get_order_history，且注册表 side_effect_free 必须 true；其他工具即使只读也拒绝。
允许状态：WAITING_FOR_HUMAN 且仅 TOOL_RECOVERY；或重启后 INVESTIGATING 且当前叶未完成、
current_action=CALL_TOOL、无其他阻断。失败须 RETRYABLE；NON_RETRYABLE/UNKNOWN_OUTCOME 拒绝。
已完成、用户等待、业务终态、错误目标、并行未解决的其他逻辑调用均拒绝恢复。
重新运行既有严重程度、场景安全和 human_review_required 检查；任何安全升级、未完成业务审批、
追问预算导致的人工暂停均拒绝。未知人工暂停来源拒绝，不靠一次工具成功清除。

所有接受请求都要求 previous_process_exited=true，含 FAILED，避免原进程返回后仍继续执行。
实验脚本负责停止并 join/wait 原工作子进程，确认退出再请求；固定超时不是退出证明。
应用只记录声明，没有跨主机 fencing。测试环境单执行工作进程，恢复 HTTP 控制进程独立。

领取使用 StateTransitionService 一次转换（等待→调查或调查→调查，action=CALL_TOOL）：
追加新 PENDING 尝试及请求账本、记录中断接替关系、仅清除工具暂停原因、更新 reason/时间，
revision 和 step 各+1、追加一个事件，全部随同一 JSONB 与关系元数据 CAS 写入。
CAS where case_id AND expected_revision；失败无 permit、无工具执行。工具 RUNNING 为第二次
转换+CAS；完成/失败为第三次转换+CAS，Evidence 与完成记录原子写入。
成功后重入工作流，第四次转换可追问/结案/安全升级/继续调查；不增加额外“恢复完成”空转换。
领取要求 max_steps-step_count >= 4；不足直接拒绝且保持原暂停与计数；后续普通工具仍走原预算。

领取后崩溃：PENDING 留存，重放只读；RUNNING 同理。再次恢复须退出声明、新 request_id、
目标为该新叶，原父链和已接受请求全保留。两个请求争同 revision 仅一个 CAS 成功；
同请求并发失败方只能读取获胜记录。运行后冲突按原 StateConflictError 保护，禁止补写覆盖。
恢复成功的原始结果经 Grounding；同 Evidence id 内容不同拒绝持久化并暂停为 NON_RETRYABLE，
不能静默复用不同内容。本轮固定样本内容不变，来源观察时间来自真实记录/实际观测，禁止补造。

## 5. 旧快照与回滚

state_schema_version 保持 1：仅加带默认字段，已有字段语义不变；不需要迁移关系表。
PostgresCheckpointStore.load 仍先校验 State、再比对 case/consumer/schema/revision 元数据。
旧记录缺省字段保留默认未知；逻辑键和有效序号在纯函数投影推导，不写回虚构事件/时间。
无恢复链的旧 FAILED 缺分类数据仍按现有 E3.1 规则拒绝，不能自动补成 RETRYABLE。
新保存 JSONB 与关系 schema_version 必须同为 1；任何不一致拒绝加载。
同 schema 数字不代表向后兼容：旧程序 extra=forbid 会拒绝新字段。回滚须停工作进程并恢复
升级前数据库备份到匹配程序版本，不能删字段后继续同一恢复案件；新历史保留独立只读备份。

W2 创建真实旧格式 fixture：分别在比赛提交 e77ef5a 和 W0 基线 ff1e35b 的独立临时检出中，
用各自模型和本地合成样本实际执行/序列化；记录提交、生成脚本、版本、SHA-256。
比赛版本覆盖正常 COMPLETED 及其模型真实可表示的 PENDING/RUNNING；不得声称比赛引擎已持久化中间态。
E3.1 用真实故障与提交后中断生成 FAILED/PENDING/RUNNING/COMPLETED。每种测试读取、保存、
重新加载及允许的正常续接，旧已完成工具不重复；缺失时间仍缺失。另测试未知字段、坏关联、
跨调用父、分叉/循环、重复身份、元数据不一致均拒绝；失败样本不能虚构旧程序成功路径。

## 6. W2 任务与验收映射

以下路径相对仓库根；新文件是计划交付，不是本轮已有实现。

| 顺序/依赖 | 目标文件或函数 | 操作及交付物 | 对应测试 |
| --- | --- | --- | --- |
| T1 / D2通过 | backend/app/domain/agent.py；新 services/tool_attempts.py | 新字段、账本、原因集合、整链校验和纯选择器 | F11；新增 F13 坏链/参数一致性/旧模型默认值 |
| T2 / T1 | backend/tests/fixtures/legacy_tool_states/（新）；新生成脚本 | 双基线真实序列化及生成清单 | F11；关系元数据、回滚拒绝测试 |
| T3 / T1 | services/tools.py 的 _execute/_replace_call；agent/decision.py 的阻塞/完成判断；services/context_passport.py | 共用有效叶选择，保留全部历史展示，身份精确完成检查 | F0、F6、F9；F13 不同参数和多链阻断 |
| T4 / T1,T3 | 新 services/tool_recovery.py；services/transitions.py；persistence/checkpoints.py | 同步 CAS 领取、一次性 permit、四步预算及安全检查；不改变关系存储模式 | F2–F4、F6–F10、F12；新增 F14 审核原因未知/预算3拒绝4接受 |
| T5 / T4 | agent/workflow.py；api/services/case_application_service.py；api/schemas/cases.py；api/routes/cases.py；api/app.py | POST/GET、错误映射、重放顺序、调查续接及 continuation 投影 | F5–F9；新增 F15 回包丢失/同id改内容/提交回执不确定 |
| T6 / T2–T5 | tests/test_phase2_workflow.py、test_phase4_postgres.py、test_phase5_api.py；新 tests/test_tool_recovery.py | 本地假工具、真实隔离库与 API 集成回归；故障注入接点 | F0–F12全部逻辑断言及F13–F15；实现与测试同提交 |
| W3 / T6 | 新 scripts/tool_recovery_experiment.py 及进程集成测试 | 独立工作进程握手/退出证据、持久计数、样本摘要、报告 | F1–F5/F8/F9独立进程验证，F12副作用未知阻断；不得以W2单进程测试替代 |

F1 普通首次调用在 PENDING 前中断仍走原路径；F4 允许人工确认后的再次只读查询，报告真实次数。
F12 的有副作用假工具仅在测试注册，永不进入恢复允许清单。
W2 预计 6–8 个工作日（每天4小时），较原4–5天增加旧格式样本、原因兼容与请求状态查询测试；
W3 预计5–7天，W4仍3–5天。剩余14–20工作日，不包含评审等待。T2或CAS验收失败即调整排期，
不能跳过验证；真实模型质量、官方数据授权、跨主机接管继续独立处理。

## 7. 交付门槛

W1 只提交本文与状态/导航更新；W2 必须在规格评审后开始。
W2按 T1+测试、T2、T3+测试、T4+测试、T5/T6 分组提交并阶段推送；每次精确暂存和核对远端。
W3报告须记录实际通过/失败/跳过，未完成故障矩阵不得宣布阶段完成。主分支合并另行验收。
