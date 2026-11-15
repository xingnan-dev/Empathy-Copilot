# 消费者消息持久化最小修复设计（待沟通区评审）

2026-11-15；设计依据为PR #5提交43132af及既有浏览器记录，唯一推荐方案如下。
本轮只设计，不改产品代码、依赖、迁移或合并PR；浏览器截图、脚本及路径4部分通过结论保留。

## 事实与选择

- persistence/models.py的MessageRow归属conversation_sessions，message_id为全局主键；
  official_dataset/persistence.py导入器按message_id upsert，可覆盖字段；sequence/sent_at是历史业务顺序和时间。
  官方Repository按sequence排序，不记录本地消息接收账本或Evidence映射。
- InvestigationState保存Evidence和工作流历史，不保存可靠完整原文；不可从source_text片段补造聊天历史。
- CaseApplicationService.ingest_message无Evidence时直接返回，不持久化原文；有Evidence时工作流可多次保存。
  PostgresCheckpointStore.save自行开启session/事务并提交。复用它作为外层事务的一部分之前必须拆出会话绑定适配能力。
- GET CaseView没有消息列表；DemoHostShell的hostMessages是固定展示样本，sentMessage是会话变量。

推荐：新增**case_inbound_messages**关系表，保留官方messages表用途不变；State JSON不新增原文副本。
复用SQLAlchemy/Alembic、现有State验证/CAS及工作流。消息处理独享一个事务绑定checkpoint适配器，
在该事务中执行现有确定性工作流，再一次性提交入站消息、Evidence与最终checkpoint。
拒绝先存原文再返回模型失败、localStorage持久化、从Evidence重建历史、改造官方表为通用事件平台。

## 数据及校验契约

新增CaseInboundMessageRow（迁移只新增表、索引、约束）：

| 字段 | 类型/约束 | 语义 |
| --- | --- | --- |
| case_id | varchar128，FK investigation_checkpoints.case_id，删除RESTRICT | 可靠案件身份 |
| message_id | varchar128，与case_id复合主键 | 客户端稳定请求身份，原样保存 |
| consumer_id | varchar128，非空 | 从checkpoint确定，客户端不可传 |
| role | varchar16，非空CHECK='CONSUMER' | 服务端固定角色，不接受伪装客服 |
| text | text，非空 | 原始请求原文，不裁剪或改写 |
| received_at | timestamptz，非空 | 首次事务成功领取时服务端UTC时间，不冒充消费者发送时间 |
| sequence | bigint，非空>0，UNIQUE(case_id,sequence) | 本地新增消息按成功提交的案件顺序排序 |
| request_revision | bigint，非空>=0 | 首次请求expected_revision，参与重放内容绑定 |
| accepted_revision | bigint，非空>request_revision | 本事务最终checkpoint revision |
| evidence_ids | JSONB数组，非空，默认[] | 首次接收产生的Evidence id，顺序保留；空数组是合法成功 |

不提供客户端received_at、role、sequence和evidence_ids输入。message_id为1–128字符、拒绝空白或控制字符，
text保留Unicode原文，1–4000字符且必须含非空白；expected_revision为非负整数，严格extra=forbid。
不做大小写/Unicode归一化后认定相同内容。接收时间仅首次生成，重放不得改变时间/序号。
与当前案件已知历史消息source_id发生同ID碰撞也返回MESSAGE_ID_CONFLICT，不将历史消息认作入站重放。
跨案件同message_id独立合法，Evidence关联始终按case_id+source_id判断，不以全局source_id联接。
新增消息不可被官方导入器更新；无更新/删除消息接口，本阶段不提供保留期限或批量删除功能。

State schema_version仍为1，原字段不变；原文仅在关系表，防止双份事实不一致。
新入站Evidence保持CONSUMER_REPORTED和CONSUMER_MESSAGE原语义：source_id=message_id，case_id相同，
observed_at使用received_at；不能将接收时间当成症状或使用时间。
最终事务校验evidence_ids全部存在于最终State，并指向本消息；无Evidence消息不创建伪Evidence。

## HTTP及界面契约

POST /api/cases/{case_id}/messages请求仍为{message_id,message,expected_revision}。
200固定返回扩展CaseView，新增receipt字段仅POST具有：
`message_receipt:{message_id,sequence,received_at,accepted_revision,evidence_ids,replayed:boolean}`。
GET receipt为null。POST的receipt指向首次接收结果，CaseView为本次一致读取的当前状态，不回滚到旧响应；并发的新提交可能在响应后到达，不承诺全局瞬时最新。
GET/POST的CaseView新增：
- messages：MessageView[]，确定顺序；字段id、case_id、role、text、received_at、sent_at、sequence、
  origin、content_type、evidence_ids。live origin=LIVE、role=CONSUMER、sent_at=null，id是原message_id。
- message_history：{historical_source:OFFICIAL|DEMO_FIXTURE|UNAVAILABLE,historical_complete:boolean}。
历史MessageView origin=OFFICIAL或DEMO_FIXTURE，received_at=null，sent_at保留已知原值，缺失仍null。
历史角色CONSUMER/AGENT/UNKNOWN由原角色明确映射，不可把未知角色当成消费者。
content_type保留TEXT/IMAGE/UNKNOWN；不新加载、再分发或替换官方图片资源。

排序固定：有依据的历史段（原sequence，重复序号按原id稳定排序并标历史不完整）在前，LIVE段按
本表sequence在后。两段sequence不混为一套时间线；UI明确标记“历史记录/本次新增”，不按客户端时间拼接。
实时新消息的evidence_ids用接收账本，不扫描Evidence推导原文；历史消息只关联实际现存同案件同source_id的Evidence。
GET通过同一个REPEATABLE READ只读事务读取checkpoint与消息，避免把旧状态与新消息混拼。

前端CaseRuntime以服务端messages为唯一已接受消息清单；DemoHostShell移除私有hostMessages和sentMessage作为显示来源。
DEMO_FIXED场景由后端返回明确标记的已有固定样本原文，不从Evidence扩写，不冒充新接收。
正常输入保留原文，不再trim后改变提交内容（仅以trim判断是否全空）。一次发送生成web-UUID，
在请求未决及可重试失败期间保留ID/原文/原revision；禁止每次重试生成新ID。
POST成功后整体替换CaseView及消息列表，按(origin,id)作React key，不再额外append成功气泡；
待发送项仅显示“发送中/未确认/失败”，不列为服务端已接收消息。禁用Send并同时阻止Enter重入。
刷新只GET，禁止自动重发；未确认本地草稿不承诺刷新保存，不用localStorage。

## 顺序、事务与失败规则（唯一主路径）

1. 验证请求并查询该case/message_id已提交账本。匹配原文、role、request_revision后直接返回最新CaseView+
   原receipt(replayed=true)，在检查旧revision、终态和模型可用性**之前**处理；不再次调用模型/工具。
   同ID不同原文或request_revision返回409 MESSAGE_ID_CONFLICT。历史ID碰撞也拒绝。
2. 对新请求加载校验State，检查revision和当前可接收状态（INVESTIGATING、WAITING_FOR_USER、
   WAITING_FOR_HUMAN；ESCALATED/CONCLUDED/TERMINATED拒绝）；模型缺失直接503，不接收原文。
   在数据库写事务外完成一次understand和候选校验，不能持有行锁等待网络模型。
3. 开启SQLAlchemy事务，SELECT checkpoint FOR UPDATE；**再次查账本**（READ COMMITTED语句新快照），
   先重放绑定，再核对当前revision、终态与历史ID碰撞。并发等待方可读已提交获胜账本。
   分配max(sequence)+1及UTC received_at（案件行锁保证序号分配串行）。模型阶段产生Evidence的
   observed_at统一为这一接收时间；保留来源和内容，不重新调用模型。
4. 使用同一Session的transaction-bound checkpoint store：load/save/exists均复用该Session，
   save复用现有State与关系元数据校验、CAS SQL并flush，**不得commit、不得开新session**。
   基于锁内当前State建立本请求的专用workflow实例；不临时替换全局共享workflow/checkpoint。
   工作流及其工具中间保存都落在同一外层事务；只允许现有本地只读工具，不运行恢复领取接口或外部写工具。
   实际工具的读取repository可保持独立只读session，不读取本事务未提交业务数据；本路径不更新业务表。
5. 有Evidence沿用既有resume/transition/确定性调查规则；无Evidence仍接收原文：checkpoint revision+1、
   updated_at更新，其余action/status/step_count/question_count/transition_events保持，不伪造领域转换。
   此revision是接收写入版本，不是完成一次调查步骤。原有审批/恢复CAS因此能发现消息已接收。
6. 校验最终State、Evidence引用与账本后insert消息行；accepted_revision为最终revision。POST投影与序列化预检使用同一事务Session读取本事务消息/State，不调用另开Session的GET读取器；然后事务commit。
   工具正常返回FAILED/人工暂停是合法最终状态，仍可200接收；不可把消息接收等同工具查询成功。
   任何异常（包括工作流、CAS、插入、flush或commit明确失败）回滚整个事务：消息、Evidence、
   checkpoint中间态均不可见。只允许最终提交后返回200；响应序列化在commit前预检，减少成功后格式错误。
7. commit返回结果不确定/回包丢失：前端标“接收结果未确认”，保留原ID和请求，不提示已明确失败。
   GET可按message_id在列表确认已接收；缺失不能证明未提交，使用原POST重放获得最终结论。
   后端新连接重放先查账本；若已经提交即不再执行模型/工具；若确实未提交则可重新处理。
   凡commit调用已发出而无法证明回滚的异常，一律归为COMMIT_UNCERTAIN，不归为明确未保存。
   该机制保证已接受消息不重复，不承诺未提交并发请求的模型调用外部exactly-once。

模型调用发生在领取前，两个并发请求可能各抽取一次，但只有锁内/CAS获胜方进入workflow；
失败方不得执行工具。事务内只读查询在整体回滚后可再次发生，不承诺工具入口跨回滚零重复。
消息路径中间checkpoint不再独立提交；此限制只适用于新消息事务，**不改变E3.2普通工具恢复的持久边界**。
锁等待上限5秒、写事务statement_timeout30秒；获锁后既有步骤预算继续生效，不提高预算或覆盖人工原因。
超时回滚503，禁止失败后补写状态。此事务语义需要专门回归，不得仅把外层with session.begin当作完成。

| 情况 | HTTP/code | UI及数据库结果 |
| --- | --- | --- |
| 无模型/模型错误/结构输出无效 | 503 MODEL_UNAVAILABLE | 明确未接收，原文保留在输入，库中无消息/Evidence变更；不生成成功气泡 |
| 合法理解但无有效Evidence | 200，evidence_ids=[] | 真实消息显示，调查事实不变化，revision+1 |
| 新请求旧revision/锁内竞争失败 | 409 STATE_CONFLICT | “案件已更新，尚未接收此消息，请刷新核对后重试”；原请求保留，用户确认后才能用新ID/新revision另发 |
| 同ID改内容/改原revision | 409 MESSAGE_ID_CONFLICT | “消息标识已用于其他内容”，不自动换ID覆盖 |
| 终态 | 409 INVALID_TRANSITION | 明确当前案件不能接收新消息，无写入；已提交重放仍允许 |
| 请求校验 | 422 VALIDATION_ERROR | 明确修正输入，无写入 |
| commit前明确DB失败/锁超时 | 503 MESSAGE_PERSISTENCE_UNAVAILABLE | 不显示已接收，记录脱敏失败；不吞异常或返回旧CaseView当成功 |
| 提交结果不确定/响应丢失 | 503 MESSAGE_COMMIT_UNCERTAIN或网络错误 | 未确认，GET+原ID重放；不能向用户保证“未保存” |
| 案件不存在 | 404 CASE_NOT_FOUND | 不创建占位案件 |

## 兼容与回滚

官方历史仍从OfficialConversationRepository读取，只显示当前案件实际纳入的消息截止范围，
读取已持久化Evidence元数据official_message_sequence_cutoff（复用现有_official_message_sequence_cutoff选择逻辑）；不得仅按重启时环境变量扩大范围。
旧官方状态若无法确认截止范围，历史段返回UNAVAILABLE/complete=false而非显示全部；不能把尚未用于该案件的后续官方消息泄入展示。
本地集成样本复用现有固定四条文本/图片占位的明确原文、ID、角色资料，提取为后端DEMO_FIXTURE数据源；
无正式时间资料的条目返回null，不把展示用16:20扩写成真实日期。正式seed与测试provider保持分离。
旧未知案件无可证历史返回历史空列表+UNAVAILABLE/complete=false，但新LIVE消息正常返回。
不为旧Evidence补建原文行，不回填虚假received_at或执行历史；旧State可直接加载，迁移前后fixture语义不变。
内存测试使用对应原子消息存储适配器（失败不得提前写_state），不使用内存实现宣称重启持久。

生产启动必须先执行新增表迁移；缺表时明确服务不可用，不退回丢消息的旧路径。
本阶段无新增HTTP鉴权，不把consumer_id/role服务端填写当作用户认证。
降级必须停写并配套匹配版本/数据库备份，保留新增原文及来源的独立备份；旧程序虽能读旧State，
但无法展示新表，不允许无提示降级后继续接收消息。官方数据授权、原文隐私保留期限仍待负责人独立确认，
本设计不授权赛后公开、导出或商用消息资料。

## 实施任务与验收映射（设计评审后才开始）

| 顺序/依赖 | 目标 | 操作/交付 | 必须测试 |
| --- | --- | --- | --- |
| M1 | persistence/models.py；alembic新增迁移；新入站消息repository | 表、唯一/外键/角色校验、排序和原文读写 | 长度/空白/角色/时间、复合ID、历史ID碰撞、迁移与旧快照 |
| M2/M1 | persistence/checkpoints.py；services/checkpoints.py；workflow工厂 | 拆出复用CAS与验证，新增Session绑定适配器及专用workflow构建，默认store行为不变 | 中间flush后回滚零变化、同Session可读、原普通store仍逐次提交；关系元数据校验 |
| M3/M2 | case_application_service.ingest_message；新消息事务服务 | 绑定重放、模型前置、行锁二次检查、无Evidence版本推进及完整事务 | 有/无Evidence原文成功、同ID同内容重放、同ID变更、旧revision、不同/相同ID真实双连接并发 |
| M4/M3 | API schemas/routes/app；官方历史repository适配；本地fixture数据 | CaseView消息投影、receipt、错误码、GET一致读取、历史分段与cutoff | 模型503、空候选200、DB insert/flush/commit故障、结果不确定后重放、无历史不补造 |
| M5/M4 | frontend/api/types.ts、cases.ts、CaseRuntime、DemoHostShell | 服务端清单、稳定请求ID、发送重入保护、明确冲突与未确认状态 | Enter/双击单请求、回包丢失原ID重试、冲突不误报模型失败、列表替换不重复、无localStorage |
| M6/M1–M5 | tests新增消息原子性/PG/API；现有浏览器脚本与W4记录 | 补齐路径4及回归证据，不改旧截图结论 | 真PG重启有/无Evidence原文/顺序/角色/source正确，跨进程竞争；刷新成功气泡保留；审批/续接/E3.2恢复全回归 |

DB故障在真实独立事务边界注入，逐项查关系行、checkpoint revision、Evidence集合；不得仅检查HTTP。
重启验收需退出旧单worker再新建engine/session/workflow，保留同临时库；GET旧快照与官方真实旧格式fixture仍通过。
提交结果不确定用提交后连接异常模拟并标注限制；重复POST不新增序号、Evidence或工具执行。
前端与Playwright确认同一原文连续两条不同ID不被错误折叠、不同角色/历史段不串行误序。
领域行为测试、隔离PostgreSQL、现有三个CI及浏览器六路径均需通过后再交回，PR #5仍不合并。
