# W2 实施与验证交接

2026-11-14；T1–T6 本地实施完成，待沟通区评审。W3 尚未开始。
代码基线 `ff1e35b4ba67e952386253a09d772e0e6918965a`；规格依据为
`af52b577ac8b69daca0e97995c613efd2427c124` 中的 [D2](phases/PHASE_E3_2.md)。
本次通过检查的实现提交为 `da131051af0f4849b6ae2a3677e15e7c887ba8f8`；
本文所在后续提交仅整理操作入口与交接状态。W0 已验证基线仍保留，未移动标签或合并 main。

## 交付及分组提交

| 任务 | 实际范围 | 提交 |
| --- | --- | --- |
| T1 | domain/agent.py 新模型、domain/tool_history.py 全局链校验、services/tool_attempts.py 有效尝试选择；字段默认、旧 attempt_count 语义保留；专项测试 | 888e65e |
| T2 | scripts/generate_legacy_tool_states.py；两历史提交的七份本地样本、摘要清单及兼容测试 | 85c6545 |
| T3 | services/tools.py、grounding.py、context_passport.py、agent/decision.py；有效链阻塞与精确完成判断、全历史投影、批次证据去重及冲突拒绝 | c5ecec8 |
| T4 | services/tool_recovery.py、review_blocks.py、transitions.py、tools.py；CAS领取、一次性进程内permit、安全原因、四步预算和测试 | 4cc5fac |
| T5 | API app/routes/application service；POST/GET、错误映射、重放；scripts/resume_completed_recovery.py；API测试 | 9dbc2f2 |
| T6 | PostgreSQL恢复集成、竞争领取、提交边界注入、失败CAS、CLI续接、七样本数据库轮转；补充坏链/拒绝测试；执行器直接调用边界；样本LF规则 | da13105 |

六组均完成对应检查后推送 `origin/codex/phase-e3-2-readonly-recovery`，每次只读核对远端提交。
最终文档提交及远端精确号见沟通区交付回报。领域校验放 domain 层，服务层复用选择器，避免领域
依赖工作流/存储。没有增加关系表、迁移、UI框架或自动重试；ui-prototype 与官方资产保持原样。

## 验证环境、命令及结果

Python 3.13.14，现有 .venv。专用 PostgreSQL 容器 `empathy-w2-e32-test-20261114`，
镜像 postgres:16-alpine，数据库 empathy_w2_test，127.0.0.1:55433，数据目录为 tmpfs。
测试未指向业务库5432或其卷。Docker Desktop 启动可能恢复既有应用容器；测试命令不操作其数据。
测试进程明确置空 OFFICIAL_DATASET_PATH 和 LLM_API_KEY，未加载/上传官方工作簿、未调用真实模型。
TestClient 是进程内 API 测试，数据库是真实 PostgreSQL；竞争是双线程/独立会话，不是跨进程验收。

从仓库根目录，先将 TEST_DATABASE_URL 设置为**专用测试库**（fixture会重建public schema）：

```powershell
$env:OFFICIAL_DATASET_PATH = ''
$env:LLM_API_KEY = ''
.\.venv\Scripts\python -m pytest -m postgres -rs --tb=short
.\.venv\Scripts\python -m pytest -rs --tb=short
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy
git diff --check
```

| 检查 | 最终结果 |
| --- | --- |
| PostgreSQL子集 | 36 passed，1 skipped；当时206 deselected（随后仅新增3项非数据库坏链测试） |
| 完整后端回归 | 218 passed，28 skipped，零失败/错误，共246项 |
| Ruff | 全仓通过 |
| mypy | 104个源文件通过 |
| 文档与diff | 交付前检查本地链接目标与暂存区，结果见沟通区回报 |

28项跳过：test_phase4_postgres.py 1项官方导入/重建、test_phase7_official_dataset.py 10项、
test_phase8_multimodal.py 4项、test_phase9_evaluation.py 12项，均缺少官方工作簿路径；
test_phase6_qwen.py 1项真实Qwen调用因凭据未启用。跳过不是通过，官方数据回归与真实语言质量未宣称完成。

实际问题及处理：旧样本生成子进程最初使用Windows本地输出编码，改为Python UTF-8模式后生成成功；
API测试在沙箱停滞后中断，转授权环境运行通过；新增数据库测试单独通过但全套首次出现12项fixture
注册错误，改为显式注册共享fixture后全套通过。静态检查发现的类型/格式问题均已修正。
执行器增补直接调用保护，防止换工具或参数绕过暂停。样本目录.gitattributes固定JSON为LF，
避免Windows checkout改变摘要。这些中间错误没有被标为已验证最终结果。

## F0–F16 本轮验证层级

| 场景 | W2实际证据 | W3仍需完成 |
| --- | --- | --- |
| F0 | 既有正常业务工具、数据库与新恢复成功路径；来源及证据引用验证 | 加入统一实验报告 |
| F1 | 数据库PENDING写前注入中断，初始快照无工具，重入查询一次 | 单API进程握手和实际终止 |
| F2 | 已提交PENDING恢复后普通执行暂停；新请求接替并保留父尝试 | 实际API进程终止与退出证据 |
| F3 | 已提交RUNNING、入口前注入中断；恢复只执行新尝试 | 实际API进程终止与持久入口计数 |
| F4 | 工具返回后完成写入前注入中断；快照RUNNING，人工再查，保留父记录 | 进程级故障点、真实查询次数报告 |
| F5 | 真实数据库COMPLETED后运行独立离线CLI；SETTLED、GET200、重跑CLI修订号不变 | 单API进程终止/重启后的完整HTTP闭环及独立计数 |
| F6 | 只读超时失败后恢复成功；原失败不覆盖 | 编入进程实验 |
| F7 | API重放、PENDING202、旧修订号重放优先、同请求并发CAS无重复资格 | API进程并发及持久计数 |
| F8 | PostgreSQL双线程/独立会话竞争，仅一permit、失败方零工具入口 | 两独立进程竞争与独立计数表 |
| F9 | 新恢复PENDING再次中断后接替，三条尝试与INTERRUPTED请求保留 | 连续真实进程终止 |
| F10 | 非只读/未知/不可重试、其他人工原因、退出声明、预算3拒绝4接受、旧修订号等拒绝 | 完整进程矩阵回归 |
| F11 | 两历史基线七个真实序列化文件；内存及PostgreSQL保存/加载/允许续接；旧成功无重查 | 固定样本纳入最终故障报告 |
| F12 | 测试注册表中带副作用假工具写内存标记再丢回执；UNKNOWN_OUTCOME阻断恢复，标记一次 | 独立持久标记、进程边界验证 |
| F13 | 无效父、错误序号、跨调用、坏请求引用、分叉、重复id、循环、孤立账本、不同参数拒绝 | 作为回归随实验执行 |
| F14 | 非工具人工原因保留，未知旧原因拒绝，严格字段与四步预算 | 作为回归随实验执行 |
| F15 | 同id改内容409、领取提交回执丢失503后重放202且无资格、GET查询、离线续接幂等 | 故障代理/进程级回包丢失与计数 |
| F16 | created_at不同复用；真实字段差异及混合批次整批拒绝；数据库FAILED/NON_RETRYABLE原子落库；失败CAS冲突保留RUNNING | 报告真实故障重复次数，不以单元测试替代进程验收 |

现有W0测试同时保留元数据不一致拒绝、迁移、种子幂等、重启恢复、证据安全等回归。
本轮没有运行 scripts/tool_recovery_experiment.py：它是W3待交付脚本，不应将其描述为已有入口。

## 操作入口

运行仍按 [本地运行指南](COMPETITION_RUN_GUIDE.md)，使用单Uvicorn API worker，不启用reload。
本轮恢复仅允许 get_order_history，所有原安全及人工审批门槛有效。
读取 GET /api/cases/{case_id} 的 revision 及 context_passport.tool_attempts，选择当前叶的attempt id；
先由外部管理脚本终止并wait旧API执行进程，确认退出，再启动新API。
将退出声明与目标旧执行进程关联保存，不能以记录年龄、超时或单一PID代替退出证明。

POST `/api/cases/{case_id}/tool-recoveries` 请求字段如下（占位值须替换）：

```json
{
  "request_id": "唯一UUID，HTTP重放必须保持不变",
  "target_attempt_id": "当前叶尝试id",
  "expected_revision": 3,
  "operator_id": "本地操作者声明",
  "reason": "旧API进程已退出，人工恢复只读查询",
  "previous_process_exited": true
}
```

首次完成201；重放及GET稳定200；仍PENDING/RUNNING为202；Location指向
GET `/api/cases/{case_id}/tool-recoveries/{request_id}`。丢失回包先GET，不能换id盲重试。
新恢复失败或中断必须经新一次人工确认、目标选新叶、使用新request id与最新revision。
操作者身份和退出条件仅为声明，不提供认证或跨主机fencing。

若状态为COMPLETED而continuation=RUNNING，停止并wait API后，在离线窗口运行：

```powershell
.\.venv\Scripts\python scripts/resume_completed_recovery.py --case-id <case_id> --request-id <UUID>
```

脚本使用 DATABASE_URL 建新连接，加载快照，以其当前revision调用workflow.run；
首个后续正式转换原子SETTLED，不重复原查询。随后重启单API并GET确认200。
CAS冲突非零退出，不覆盖。该脚本不接替PENDING/RUNNING工具，不得与API同时运行。
生成历史样本的脚本只用于受控更新fixture，真实生成时间变化会更新摘要，不是常规运行步骤。

## 限制与后续

W2测试通过但阶段评审未完成；不宣布生产可靠性或完成W3。
固定只读样本没有实现可变业务源版本化；证据内容冲突会暂停供人工处理。
schema_version仍为1但旧程序extra=forbid不保证读取新增字段；回滚必须停进程并恢复升级前数据库备份，
保留新历史副本，不能删恢复字段后继续旧程序。允许清单不得因工具注册只读就自动扩展。
W3预计5–7个工作日、W4预计3–5个工作日（每天4小时）；W2未发现需扩大产品范围的事项，
上述fixture注册/编码问题已在本轮修复。下一步先评审本交接，再单独启动W3进程实验。


F5观测说明补订：父进程execution_counts只覆盖父进程，不能作为CLI子进程无查询的直接证据。
该测试仍验证状态推进与幂等性；跨进程调用观测见 [W3 F5补验](W3_F5_SUPPLEMENT.md)。
