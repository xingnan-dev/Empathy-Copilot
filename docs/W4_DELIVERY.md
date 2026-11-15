# E3.2 已完成，已合并 main

2026-11-14；起点 `00b946368bc3a0f69f9ba139673fe5d569fe780b`，分支
codex/phase-e3-2-readonly-recovery。W3及F5补验已通过沟通区评审；W4交付已通过沟通区最终评审，文档收尾未修改产品代码，
W4整理当时未合并main或创建发布标签；后续合并结果见下文。视频经负责人决定取消，不再作为最终验收、合并或发布的阻断。

## 文档入口

- [README](../README.md)：现有能力、本轮增量、阅读导航及验证入口。
- [运行指南](COMPETITION_RUN_GUIDE.md)：干净检出、合成样本、隔离库、单API、人工恢复及离线续接条件。
- [三分钟演示命令与讲稿](DEMO_OPERATOR_GUIDE.md)：正常对照→只读超时→重启→显式恢复→调查继续、历史/来源/重放。
- [架构与可核实贡献](ARCHITECTURE.md)：三个设计取舍、实现提交、AI辅助与待负责人补充的个人归属。

## 独立干净检出验证

实际使用 `git clone --no-hardlinks --branch codex/phase-e3-2-readonly-recovery` 从本地Git仓库创建
独立完整临时克隆（不是复制工作树），检出00b9463。该路径避免再次下载相同Git对象，远端公开
clone命令与检出的文件相同，但本轮没有重复验证GitHub下载吞吐或公开权限。
验证前确认克隆没有.env、competition_data/official.xlsx、原node_modules或原.venv。
共享的是已安装的Python解释器、Node/Docker软件与包下载缓存；没有复用原工作区依赖目录、密钥或配置。

| 操作 | 实际结果 |
| --- | --- |
| Python 3.13.14 base interpreter → 新venv | 成功，venv含pip |
| 新venv `pip install -e ".[dev]"` | 从包源解析并安装成功，未使用原venv包 |
| 新venv Ruff / mypy | 通过；mypy105源文件 |
| `npm ci` | 按package-lock重新安装231包成功 |
| Node v24.16.0 / npm11.13.0：`npm test` | 5通过 |
| `npm run build` | TypeScript与Vite6.0.7构建成功 |
| 普通API原生迁移/seed、uvicorn单worker | /health返回ok；GET S00154成功，WAITING_FOR_HUMAN |
| 前端Vite preview | HTTP200、生成HTML成功；未进行浏览器交互/E2E验收 |
| 独立实验 `--cases F0 F6 F5 --repetitions 1 --regression` | 3个变体各1次通过，含F5独立CLI正对照 |
| 同次完整回归 | 221通过、28跳过，零失败/错误 |

普通API烟雾验证用独立唯一标记tmpfs PostgreSQL容器、随机loopback端口；通过readiness检查后迁移、
seed、启动API及前端preview，最后terminate/wait自己创建的进程并校验标签后移除容器。
实验验证同样由已提交脚本管理自己的临时资源。未把应用5432或已有卷作为测试目标。
基础环境Git2.55.0.windows.5、Docker Desktop4.86.0/Engine29.7.2、postgres:16-alpine；
镜像摘要、Python构建串、固定输入摘要见原始报告。

新解析的关键依赖：FastAPI0.162.7、Pydantic2.14.3、SQLAlchemy2.1.8、LangGraph1.2.22、
psycopg3.3.9、Uvicorn0.54.0、Alembic1.20.1、pytest8.4.2、Ruff0.17.5、mypy1.20.2。
[观察到的完整Python依赖](../backend/evaluation_output/w4/clean-00b9463/requirements-observed.txt)
仅记录本轮Windows/Python3.13解析，不替代跨平台锁文件。

额外前提：首次安装可访问Python/npm包源；可运行Docker Linux容器、拉取postgres镜像并清理自己的
容器；可绑定本机端口、创建/停止API子进程。包缓存可能加速下载，不是必须输入。
npm安装报告14项漏洞（2低、9中、3高）；本轮没有自动audit fix或升级已冻结前端依赖，需独立审查。
Python只声明版本范围，未来解析可能变化，不据此承诺任何未来版本都兼容。

## 验证依据与数量

W4 [原始报告](../backend/evaluation_output/w4/clean-00b9463/report.json)、
[回归日志](../backend/evaluation_output/w4/clean-00b9463/regression.log)和
[JUnit](../backend/evaluation_output/w4/clean-00b9463/regression.xml)来自独立克隆。
其中git_commit=00b9463，是包含实际运行代码的已提交起点；本轮后续提交只改说明/记录。

| 历史入口 | 数量及口径 |
| --- | --- |
| [W2](W2_VALIDATION.md) | 218项回归通过、28跳过；不等同进程实验次数 |
| [W3](W3_VALIDATION.md) | 13场景变体，首轮13+三轮39=52次运行；F5原CLI计数存在已说明的盲区 |
| [F5补验](W3_F5_SUPPLEMENT.md) | 三次独立正对照各1次查询，三次真实续接各0次CLI订单查询；零调用结论引用这里 |
| W4干净检出 | F0/F6/F5各1次，共3次变体运行，F5另含1次独立正对照；不是重新执行整个W3矩阵 |

W3原报告git_commit可能指向实验源尚未提交时的起点；正式三轮对应609e12a实际实验代码。
F5补验报告git_commit指ae294ca（启动时起点），包装与定向分支随00b9463提交，保留原报告不改写。
W4验证直接从00b9463检出，可追溯到实际包含包装代码的提交。
28项跳过继续为27项官方工作簿依赖、1项真实Qwen凭据依赖；不计为通过，不证明语言质量或官方数据授权。

## 演示与视频

三分钟使用现有实验命令、终端/API及实际报告，正常对照与失败恢复为不同本地合成案件。
讲稿和展示字段在操作指南内，不新增比赛材料或重复演示文档。
本轮实际执行了该流程。视频状态：**经负责人决定取消**。
负责人的本次决定取代此前环境限制导致的“待交付”状态；无需补录视频即可进行最终验收、
合并与发布评审。运行命令、讲稿和操作说明继续保留供复现。
W4按代码、测试、故障实验、干净检出验证、文档和Git状态验收。
前端依赖漏洞审查作为[独立待办](FRONTEND_DEPENDENCY_REVIEW.md)处理，不借视频取消宣称漏洞已修复。

## 最终边界

当前恢复只允许订单只读工具；人工退出/身份字段是声明，跨主机fencing、真实认证、业务副作用对账、
自动重试、通用任务平台仍未交付。React保留现有案件展示，恢复操作使用API/CLI。
旧程序不保证读取新增恢复字段；回滚需要配套数据库备份，原始历史与证据不可删字段回退。
个人设计归属和团队贡献分配待负责人补充；本轮Codex辅助实现、验证和文档整理有提交记录可核对。
PROJECT_STATE与阶段说明标记“E3.2 已完成，已合并 main”。
本轮按代码、测试、故障实验、干净检出验证、文档和Git状态通过最终验收；
主分支合并已获沟通区授权并执行，发布标签仍需另行确认。上述跳过范围、单进程/身份声明、回滚限制及独立依赖待办继续有效。

## 实际合并记录（2026-11-14）

[PR #1](https://github.com/xingnan-dev/Empathy-Copilot/pull/1) 将已评审范围
`e77ef5a..bfef0b3`（18个提交、64个文件）通过 merge commit
`a719fab1e922c9a41ecb6f1381b9641ea2d75a4e` 合入main；两个父提交分别为
`e77ef5a063179cba3c7aa3cc0a3438d89b5646c2` 和
`bfef0b3a9dfab9d1682c28559db6aeb3df716b0f`。无 squash、rebase 或强制推送。
合并前远端main没有新增提交，PR差异与本地已评审范围一致，GitHub报告 CLEAN/MERGEABLE。
main未启用分支保护，仓库无活动ruleset、Actions工作流或PR状态检查；此事实不替代上述本地验证。
合并后确认交付提交为远端main祖先，并将本地main快进同步。
开发分支与比赛标签保留，不创建发布标签。合并后的状态同步仅修改文档，检查本地链接与diff，
未重复运行业务测试；现有跳过与限制继续适用。

## 浏览器验收准备与阻碍（2026-11-15）

被审查提交 `bb4916a745556c2db3cb1030b022fbaaf7ef6dcf`，刷新后main无新增提交，
起始工作区干净，分支codex/browser-acceptance。本轮仅准备验收，**六条真实浏览器路径均未执行，不能判为通过**。
未启动数据库、前后端或浏览器实验进程，无需清理本轮运行资源，未操作既有业务环境。

### 工具缺口与界面事实

本会话工具目录没有Browser/Chrome/Computer控制会话；仓库node环境的playwright、puppeteer、
@playwright/test均无法解析。Node REPL尝试import playwright失败：
`The requested module './index.js' does not provide an export named 'default'`；其余两个模块不存在。
本机有Chrome/Edge可执行文件，但没有本轮可直接复用的交互/截图/控制台采集会话。
可以另建实验CDP适配器或接入现有浏览器插件后继续；本轮没有新增框架或把启动可执行文件当成验收完成。
没有采集到浏览器版本、截图、控制台或网络日志，因此没有自动化或手动浏览器通过证据。

静态检查：CaseRuntime固定getCase('S00154')，未提供案件选择器；界面有消息输入/Send、
Response Studio审批、草稿，以及初次加载失败时的Retry/显式Demo Fixture Mode。
消息接口在model_service未配置时拒绝处理；fixture模式消息亦明确不可用，不应断言消费者消息已持久化。
有效消息成功路径需要实验专用确定性模型provider和真实后端验证，不能用浏览器网络mock替代证据落库。
审批界面只按approved/approving隐藏或禁用按钮，不能仅据静态代码认定重复操作安全或错误提示可理解。
本轮没有复现并确认产品缺陷，因此没有代码修复或新增领域测试。

### 负责人可执行的人工步骤（待真实浏览器环境）

按[运行指南](COMPETITION_RUN_GUIDE.md)的native migration/seed启动实际后端单worker及前端。
使用独立带实验标识的临时PostgreSQL容器/数据库、随机loopback端口，无业务卷；显式设置独立DATABASE_URL、
前端VITE_API_BASE_URL及匹配CORS origin，清除该进程模型凭据/官方数据配置，不读取工作区.env。
各样本使用独立数据库快照、均以S00154作为界面入口，避免为了切换案件修改产品代码。
记录两个服务PID、容器ID/标签、浏览器完整版本、被测SHA和测试时间；只删除自己创建且标签匹配的资源。

| 路径 | 准备/操作及预期 | 本轮实际 |
| --- | --- | --- |
| 1 加载 | 合成S00154，打开实际前端；观察加载完成、来源、缺口、状态，与GET案件返回对照并截图 | 未执行 |
| 2 消息 | 无凭据样本输入有效消息并Send；预期明确不可用且不伪造新增Evidence。成功写入路径另需批准的确定性provider样本，核对消息来源、revision与下一步 | 两个变体均未执行 |
| 3 审批 | 独立具备can_approve条件的S00154，进入Response Studio点击Approve escalation；核对后端审批状态/一次性事件。双击及旧revision API提交分别记录，预期无重复动作、冲突反馈可理解 | 未执行 |
| 4 刷新 | 对上一步已实际持久化状态刷新浏览器，与刷新前GET来源/消息/状态/revision对照；不可把fixture当作数据库恢复 | 未执行 |
| 5 断网恢复 | 新独立样本，终止本轮后端并刷新；预期可见错误。原库重启单worker后点击Retry，确认重新GET真实状态，不能留在Demo Fixture模式冒充恢复 | 未执行 |
| 6 异常 | DevTools启用Preserve log，逐路径保存console、请求method/path/status及必要脱敏响应；区分预期503/409与未处理异常、重复请求 | 未执行 |

审批旧revision可由DevTools对本次独立样本重放原human-approval请求；保存其状态与事件计数，
单独标记为API重放证据，不能替代真实重复点击验收。禁止记录Authorization、模型配置或完整环境变量。
草稿无模型时记录明确fallback/不可用提示及标记；不能把合成回复说成真实模型输出。
上述为执行清单而非结果。恢复能力仍通过API/CLI，未新增恢复按钮或重设计界面，ui-prototype未修改。
剩余minimatch风险和此前官方数据/真实模型/镜像CVE边界不变。

## 真实浏览器自动化验收（2026-11-15，待评审）

前一节及85fbac6只记录准备时的阻碍，不能当作浏览器通过证据。本轮负责人明确授权Playwright后，
已安装开发依赖 `@playwright/test=1.65.1`（新增playwright/playwright-core及锁文件），
通过本机Chrome **157.0.8103.50** 执行真实无头浏览器交互，而非HTTP替代或页面请求mock。
Node24.16.0/npm11.13.0；调度Python3.14.4，API使用项目.venv的已验证Python环境。
刷新远端main仍为bb4916a，工作区起点干净，继续PR #5分支。实验报告starting_commit=85fbac6
是当时工作树父提交；实际执行的新增脚本和favicon修改由 **e8e8e31aeeb06f125ea0aa3c18c5e534783fe357** 保存。
后续仅整理记录，不声称先前报告已运行尚未存在的提交。

**总体：六条路径已实际执行；路径4关于原文聊天气泡恢复不满足预期，不能宣称端到端全部验收通过。**
最终五个独立模式的脚本断言通过，只表示脚本所列40项断言成立，不覆盖该已观测限制。
全部是Playwright自动操作真实浏览器，不是负责人手工点击验收；截图人工查看仅用于辅助核对。

### 复现与隔离

先在frontend运行npm ci，再从根目录运行 `python scripts/run_browser_acceptance.py`。
需要Docker Linux容器权限、本机Chrome、项目.venv；不下载浏览器，不把完整浏览器套件接入CI。
[调度器](../scripts/run_browser_acceptance.py)、[浏览器脚本](../scripts/browser_acceptance.mjs)、
[实验API入口](../scripts/browser_acceptance_worker.py)均可重复使用。
每轮唯一标签tmpfs PostgreSQL容器，五个数据库test_message/test_unavailable/test_approval/test_conflict/test_outage，
均独立迁移/seed、使用同界面固定S00154入口；不共享前一模式状态或业务数据库/卷。
使用仓库已有确定性integration fixture和demo seed，不读取官方工作簿；UI保留原有硬编码脱敏展示。
API单worker、随机loopback端口；前端固定127.0.0.1:5173以符合当前CORS，端口占用即拒绝启动，不终止已有服务。
子进程环境清除LLM/Qwen/vision/official相关配置。消息模式显式使用已有FakeModelProvider，
返回固定EXACT_PRODUCT_USED候选“面霜”，仍经过真实ModelService领域验证、PostgreSQL保存与真实API投影；
其他模式不配置模型，预期503/Fallback Draft，不冒充Qwen成功。实验入口不进入正常运行路径。
API/浏览器握手管理断开与重启：旧进程terminate/wait后写api-stopped，新进程health成功后写api-restarted；
不使用固定等待时长猜测故障边界。截图、trace及JSON不记录密钥或完整环境。

### 最终证据与逐路径结果

最终实验目录为[浏览器报告](../backend/evaluation_output/browser-0880247d91184ccaaa353e2a76fdffce/report.json)。
每个模式的JSON包含断言、console错误位置、API请求状态和最终CaseView；*-checkpoint.json为数据库直接导出，
逐项核对其state_revision与API一致（message3、unavailable1、approval2、conflict2、outage1）。
*-trace.zip包含实际操作、DOM快照及网络证据，截图为真实浏览器，不是设计图。

| 路径 | 预期与实际 | 判定 |
| --- | --- | --- |
| 1 打开案件 | 等待真实加载完成，S00154、WAITING_FOR_HUMAN、证据source/provenance和非空缺口与API一致；截图可核对界面 | 通过 |
| 2 消息 | 实际输入并点击Send；fake模式POST200、revision1→3、新CONSUMER_REPORTED面霜证据、对应产品缺口不再OPEN，页面动作与重新GET一致。无模型独立样本POST503、可读不可用提示，revision不变 | 通过，fake与无模型变体分别标注 |
| 3 审批 | 独立can_approve案件真实双击，revision仅1→2、APPROVED、后续按钮消失；原revision重放409且不增修订。另用独立conflict库先由第二客户端审批，再点击陈旧UI，浏览器显示“Case updated elsewhere. Refresh current state.”，仍只有一次审批 | 通过；API重放与UI冲突分别记录 |
| 4 刷新 | Evidence、来源、状态、revision及下一步恢复，审批也持久化。**新增聊天原文气泡刷新后数量为0**；当前sentMessage仅React state，CaseView没有新增原文历史 | 部分通过；原文恢复未满足，不将其算作通过 |
| 5 后端中断 | 真正停止本轮API，刷新后可见加载错误；同库重启后点击Retry，重新GET真实状态并保持revision，未进入Fixture Mode | 通过 |
| 6 console/network | 无未捕获pageerror。favicon404定位并修复；最终正常消息无console错误；无模型503、陈旧审批409、断开时ERR_CONNECTION_REFUSED均对应故意注入条件，保留原始位置 | 通过所检查范围，不宣称无预期错误 |

[消息截图](../backend/evaluation_output/browser-0880247d91184ccaaa353e2a76fdffce/message-message.png)、
[刷新截图](../backend/evaluation_output/browser-0880247d91184ccaaa353e2a76fdffce/message-refreshed.png)、
[审批截图](../backend/evaluation_output/browser-0880247d91184ccaaa353e2a76fdffce/approval-approved.png)、
[冲突提示](../backend/evaluation_output/browser-0880247d91184ccaaa353e2a76fdffce/conflict-conflict-feedback.png)、
[断开截图](../backend/evaluation_output/browser-0880247d91184ccaaa353e2a76fdffce/outage-offline.png)、
[恢复截图](../backend/evaluation_output/browser-0880247d91184ccaaa353e2a76fdffce/outage-reconnected.png)。

### 问题、修复与检查

最小修复：index.html声明空内联favicon，避免浏览器隐式/favicon.ico的404，不改版式；
现有node测试补充入口icon回归，初版测试路径多退一层导致失败，修正后6通过。最终真实Chrome轮已无该404。
采集脚本首次导出中文checkpoint遇到Windows GBK解码错误；改用UTF-8后完整重跑。
[该未完成轮](../backend/evaluation_output/browser-7ef0476a59e74ad0a30f07d4a6329504/report.json)没有PASSED状态，不算通过；清理完成。
迭代共8轮、28次模式调用（不同覆盖，非28个独立测试），最终完整轮为5模式；
早期轮次仅提交结构化摘要，重复截图/trace留本机忽略，最终轮保留完整证据。

**待沟通区确定：聊天原文持久化/回显契约。** 当前后端持久化模型抽取Evidence，但页面聊天新增气泡是会话状态，
CaseView不返回原文消息历史。本轮未自行增加个人数据留存、API历史投影或localStorage；
这些会扩展产品数据/展示契约，需先明确保留范围、来源与显示规则，再安排修复和刷新回归。
因此本PR不应仅凭CI绿色认定所有浏览器验收通过。

npm ci、6项现有前端测试、typecheck/lint/build、Ruff通过；mypy与现有三个必需CI检查结果以PR #5运行记录为准。
没有将浏览器套件纳入CI，没有改变现有领域安全或恢复机制；minimatch仍7项中危，真实Qwen、官方工作簿、
Edge/Firefox/Safari、移动设备、镜像CVE及完整W3不在本轮新增验收范围。
所有本次Chrome context/browser均finally关闭，前后端直接子进程terminate/wait，
容器清理前核对独立标签并移除；数据库tmpfs随容器消失。已有业务容器未操作。

代码/工具提交e8e8e31的[真实CI运行](https://github.com/xingnan-dev/Empathy-Copilot/actions/runs/43698686487)
backend41秒、postgres53秒、frontend42秒全部通过；本地mypy105文件通过。
文档收尾另行提交并等待最新PR检查，不以此替代上述部分通过的验收结论。

## 消息持久化修复实施与验收（2026-11-15，待沟通区评审）

规格17ac624获批准后按M1–M6实施；起点/远端源均17ac624，main仍bb4916a，工作区干净。
继续PR #5，不合并、不移动标签。原browser-0880及其“刷新部分通过”记录保留不变，本节是新增结果。
负责人确认：Evidence.metadata.original_message保留原有溯源；关系表作为聊天展示/幂等权威来源，
State不新增聊天数组。设计中“原文仅在关系表”已作这一澄清，没有删除证据字段。

| 任务 | 实际实现范围 |
| --- | --- |
| M1 | CaseInboundMessageRow及20261115_0003新增表迁移，案件+消息复合身份、序号唯一、角色/版本/长度约束；不修改官方messages表 |
| M2 | TransactionBoundCheckpointStore复用现有校验/CAS，外层事务独占提交；普通PostgresCheckpointStore仍逐次提交。事务适配器可见中间flush，其他连接不可见 |
| M3 | 原文/角色/接收时间/顺序/证据引用与工作流checkpoint整体提交；无Evidence也revision+1，step/question/事件和人工原因不变。模型在事务外，锁内二次重放/CAS，独立workflow及只读工具守卫，不替换共享对象 |
| M4 | messages/message_history/message_receipt投影，GET同一REPEATABLE READ快照；模型503、存储503、未确认503、冲突409分别表达。保留旧State schema1；官方按持久化cutoff、历史重复序号标不完整、未知角色不伪装；旧样本已有LIVE时不重建 |
| M5 | 移除私有成功气泡，服务端清单替换；原文不trim、同文不同ID不合并、origin/id作key，历史/新增分段标记。Send/Enter重入保护，失败/未确认保留原请求ID与原revision，无localStorage |
| M6 | 单元/API、真实PG回滚/双连接/跨进程/提交回执丢失/迁移回退与普通store及E3.2回归；真实Chrome扩展九模式，数据库消息行/State/页面逐项对照 |

实现提交分组：a7b91f9（M1–M2，首轮真实PG2项通过）；f22b6f6（M3–M4，7项PG及本地/类型检查通过）；
ff61ec7（M5–M6及原始新证据）。最后的历史重复序号完整性标记另有针对性PG17项复核通过。
实验报告starting_commit=f22b6f6为执行时起点；包含所执行源码与新脚本的提交为ff61ec7。
最后前端仅移除了eslint指出的等价catch-rethrow，相关前端检查重跑通过；不把父提交号冒充运行时已有最终提交。

### 后端与数据库验证

最终命令：`python -m pytest -m "not qwen" -rs --tb=short --junitxml=.../tests.xml`，
使用本轮唯一tmpfs PostgreSQL16容器、专用message_test和随机loopback端口，无业务卷。
[最终JUnit](../backend/evaluation_output/message-complete-39185dfb90664ee09717c06918d3c8b4/tests.xml)、
[日志](../backend/evaluation_output/message-complete-39185dfb90664ee09717c06918d3c8b4/tests.log)：
**246通过、27跳过、1 deselected、零失败**，25.98秒；27项为官方工作簿依赖，真实Qwen按标记未执行。
Ruff和mypy110文件通过；前端6项测试、typecheck/lint/build通过，依赖版本未再变更。

PG覆盖：插入失败后消息/Evidence/中间checkpoint全部回滚；成功重放先于终态/模型缺失检查；
同ID改内容拒绝；无Evidence counters/history/人工暂停不变；同ID重放/不同ID竞争使用真实双连接，
并用spawn的两个独立进程分别验证有/无Evidence，只有获胜方写入且保留一条序号。
另用实际首次get_order_history=1的样本证明重放不重复模型或工具，不以零调用样本替代。
提交不确定通过真实事务已commit后的OperationalError注入，GET及原POST重放确认唯一消息；
这是回执异常模拟，不声称真实拔网测试。旧格式/审批/调查续接/恢复及普通store原有回归包含在完整测试内；
未重复独立W3故障矩阵，原证据仍有效于其原范围。

### 新浏览器证据

[最终报告](../backend/evaluation_output/browser-42cdc9de3c7c474583f96132c6592061/report.json)：
本机Chrome157.0.8103.50、Playwright1.65.1、Node24.16.0/npm11.13.0，实际前端与单worker API，
九个独立临时数据库。全部为脚本自动控制真实浏览器，非手工点击、非网络mock；90项脚本断言。
每个模式有*-messages.json关系行、*-checkpoint.json、CaseView/console/请求JSON、截图和trace；
调度器断言原文、角色、顺序、id/evidence_ids及revision一致，并验证Evidence源指向原message_id。

| 原验收路径 | 修复后结果 |
| --- | --- |
| 1 加载/来源/缺口/状态 | 通过；历史样本明确DEMO_FIXTURE，不读官方工作簿 |
| 2 消息接收 | 有Evidence及无Evidence均成功；无模型503且不写入，重试仍用原ID |
| 3 审批/重复/旧revision | 通过；真实双击一次审批，陈旧UI冲突提示可读；消息陈旧revision也不误报模型失败 |
| 4 刷新恢复 | 通过；有/无Evidence原文均恢复，同文不同ID两条、序号递增，历史四条不重复；原文关系行与页面对应 |
| 5 断开重启 | 通过；确认旧API退出后重启同库，Retry恢复原文、角色、顺序及来源关联 |
| 6 console/network | 无未捕获pageerror；预期模型/DB503、冲突409、故意断连均记录，不宣称零错误请求 |

额外真实UI模式db-failure/commit-uncertain/message-conflict覆盖准确反馈；未确认后原ID重放200且replayed=true，
库中仍一条消息。可重复命令仍为 `python scripts/run_browser_acceptance.py`，需要空闲5173以匹配既有CORS。
[有Evidence原文](../backend/evaluation_output/browser-42cdc9de3c7c474583f96132c6592061/message-same-text.png)、
[无Evidence原文](../backend/evaluation_output/browser-42cdc9de3c7c474583f96132c6592061/no-evidence-same-text.png)、
[重启恢复](../backend/evaluation_output/browser-42cdc9de3c7c474583f96132c6592061/outage-reconnected.png)、
[提交不确定后重放](../backend/evaluation_output/browser-42cdc9de3c7c474583f96132c6592061/commit-uncertain-failure-feedback.png)。
模型仅使用已有FakeModelProvider（固定候选/空候选），不冒充真实Qwen；入站表、真实API及领域工作流未mock。

### 中途失败与处理

失败原始结果保留，不覆盖为成功：message-final-1a8d4acc的2个并发测试错把有Evidence的两次转换预期为+1，
修正断言为该fixture的+2；message-verified-115aa78a合成官方样本缺Consumer父行，补齐真实外键前提；
message-releasecheck-b110fc72首次查询样本原已带订单Evidence，未实际执行工具，改成确实缺订单的独立样本后通过。
browser-2edab238在PostgreSQL临时初始化socket已就绪、最终TCP尚未就绪时createdb失败，
改用pg_isready -h127.0.0.1检测最终服务器，后续轮通过。先前日志/JSON编码、Ruff/mypy及前端lint发现的问题均修正；
后端改变旧“无Evidence不保存”测试预期是批准的行为变更，不是忽略失败。早期重复截图/trace本地忽略，结构化摘要和失败日志保留。

### 迁移、回滚与边界

部署新前后端前先停写、备份数据库，运行 `python -m alembic upgrade head` 到20261115_0003。
新增表不改旧State schema1，不回填或从Evidence补造历史；缺表返回明确服务不可用，不退回丢消息路径。
迁移已测试从空库升级及降回0002再升级，旧checkpoint不变；存在已接收消息时downgrade明确拒绝删表。
回滚必须停写并保留新增原文/来源备份，恢复到匹配代码与数据库版本；禁止直接删表/删字段后继续接收消息。
未知历史返回UNAVAILABLE，重复历史序号标不完整，截止范围无法确认不展示后续官方消息；官方导入器不写LIVE表。
模型/工具在未提交并发或整体回滚后可能重复调用，不承诺外部exactly-once；已提交重放不再调用。
本轮未提供鉴权、通用消息编辑/删除/分页、保留期限策略或生产发布，原文授权/隐私仍需负责人管理。
剩余minimatch、真实Qwen/官方数据/镜像CVE/跨浏览器等未验证范围保留。未改ui-prototype，无发布标签或部署流程。
所有本次Chrome与服务退出，独立标签容器移除，数据库tmpfs随之清理；原有业务容器保留。

代码提交ff61ec7的[实际CI运行](https://github.com/xingnan-dev/Empathy-Copilot/actions/runs/43705360330)中backend、postgres、frontend均通过；最后完整性标记修复及文档提交仍等待其最新PR检查，不以旧提交结果替代。


### LIVE原文溯源一致性补验（2026-11-15，待评审）

PR #5继续暂缓合并；本轮起点6a2416265014557df267108eb9b436eb0c25ed95，远端main仍bb4916a。
MessagePersistence.validate_links对LIVE记录关联的Evidence检查已有metadata.original_message与表text精确相等，包含空白和换行，字段存在但null视为冲突；缺字段仍兼容，不补写、不从Evidence补造聊天历史。
错误契约：HTTP409，code=MESSAGE_PROVENANCE_CONFLICT，message=“Message and Evidence original text disagree; no data was changed.”。
写入提交前、GET和已提交请求重放投影均检查；冲突不成功、不覆盖，写入中的消息/Evidence/checkpoint整体回滚。

命令：设置TEST_DATABASE_URL指向本轮新建tmpfs PostgreSQL16独立provenance_test后，
`python -m pytest backend/tests/test_message_persistence_postgres.py backend/tests/test_inbound_messages.py -rs --tb=short --junitxml=backend/evaluation_output/message-provenance-20261115/verified.xml`。
**31通过、0失败、0跳过，14.51秒**；Ruff通过，mypy110文件通过。
新增6个参数化实例覆盖匹配、缺字段、写入回滚、GET/重放冲突及不自动修复；事务测试逐项核对消息行为空、完整checkpoint（含Evidence/计数/历史）不变。
[通过JUnit](../backend/evaluation_output/message-provenance-20261115/verified.xml)、[日志](../backend/evaluation_output/message-provenance-20261115/verified.log)。
首轮4失败/27通过来自夹具修改checkpoint但未推进revision，被现有CAS正确拒绝；修正夹具后通过，原tests.xml/tests.log保留。
未改迁移、依赖、前端或E3.2边界，不重复不受影响的完整浏览器与W3实验；原实际验收证据范围不变。
三个必需CI针对本轮最新提交运行，具体结论以PR检查及本轮交付回报为准，不引用旧提交替代。
本轮仅创建带唯一名称/标签的临时数据库容器；实验结束删除该容器，既有业务容器保留。官方数据、真实模型及minimatch等原限制不变。


### 消息持久化与浏览器验收合并完成（2026-11-15）

沟通区批准[PR #5](https://github.com/xingnan-dev/Empathy-Copilot/pull/5)合并；源提交428849ce5543b3b46b1a710832f6874461a810b7，
目标main未新增提交，原bb4916a。最新合成提交59ce94d9d9e7e50d498baeba709b3b106dff7232的
[三个必需检查](https://github.com/xingnan-dev/Empathy-Copilot/actions/runs/43706753218)全部通过。
核查main严格检查、Actions来源、PR要求及禁止强推/删除规则仍有效，使用普通merge，不使用管理员绕过。
GitHub完整diff因超过20000行不可展示，已用本地Git实际差异与九个源提交记录核对范围。

merge commit：`2d0707f1dcded5c313c58da0ac22092b9a420e40`，父提交为bb4916a与已评审428849c，
未squash/rebase，开发分支及历史标签保留。
合并后实际main的[push CI](https://github.com/xingnan-dev/Empathy-Copilot/actions/runs/43707162075)
backend、postgres、frontend全部通过，不以合并前结果替代。本地main已快进同步。

消息持久化及浏览器验收修复已完成、已合并；上文原“刷新部分通过”、后续修复及溯源补验报告均保留，
其待评审/暂缓合并表述为当时阶段记录，不改写原结论。
部署前必须停写备份并执行`python -m alembic upgrade head`到`20261115_0003`；本轮未连接业务数据库执行迁移或部署。
已有消息时downgrade拒绝删表，回滚须保留原文与证据来源并配套匹配版本/备份。
剩余minimatch、官方数据许可/隐私、真实Qwen与官方工作簿、镜像CVE、其他浏览器及单进程恢复/身份声明限制仍开放。
视频经负责人决定取消，本轮不新增发布标签或部署流程。状态收尾仅文档，通过独立PR及相同三个检查交付；不声称重跑完整浏览器或W3实验。
