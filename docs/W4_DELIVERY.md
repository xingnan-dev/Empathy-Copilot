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
