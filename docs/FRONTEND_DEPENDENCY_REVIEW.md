# 前端依赖独立审查与修复记录

2026-11-14；原只读审查保留如下；负责人已授权独立依赖修复，执行结果见文末。
本记录不自动批准合并或发布，也不将剩余风险视为已修复。
[npm原始结果](../backend/evaluation_output/w4/frontend-audit.json)基于当前package-lock：
14个受影响依赖条目，2低、9中、3高、0严重；不等同14个独立漏洞或14条可利用路径。
命令为 frontend 目录下 `npm audit --json`；退出码1表示发现漏洞，不是查询失败。

## 影响与待办

| 依赖组 | 当前事实与暴露判断 | 独立修复任务 |
| --- | --- | --- |
| Vite6.0.7 / esbuild0.24.2 | 开发服务器跨源读取与路径限制绕过类告警；npm scripts确实启动Vite。生产Docker最终阶段只复制dist到nginx，未运行Vite，不能据npm dependencies分类认定生产提供了开发服务器 | 优先在独立变更中升级Vite及兼容插件；npm本次建议Vite6.4.6，需再次核实当时全部通告，不将单一版本建议视为零漏洞证明 |
| PostCSS8.4.49 / source-map-js1.2.1 / selector parser | 本地构建处理CSS/source map链存在文件读取、拒绝服务及输出注入类通告。仓库使用本地受信CSS，但不能排除未来不可信输入、PR或插件链 | 升级PostCSS与相关传递依赖；本次npm建议PostCSS8.5.33；检查生成CSS和source map、重新构建与视觉回归 |
| ESLint9.17.0 / plugin-kit | lint阶段解析配置注释的正则拒绝服务风险；不是浏览器运行时组件 | 独立升级ESLint兼容组合，npm建议9.39.5；重新lint |
| typescript-eslint8.18.2及minimatch链 | AST/文件匹配工具链受影响，部分条目fixAvailable=false；minimatch存在多处传递安装，不能只看根目录版本判断 | 检查npm explain和完整锁文件各安装节点，升级工具链或记录暂无修复的处置；禁止强制覆盖后宣称安全 |

以上暴露判断是根据package.json脚本、Dockerfile的多阶段构建与通告范围所作静态推断，未运行利用PoC。
nginx镜像自身漏洞不属于npm审查覆盖；静态dist也不因此获得安全认证。
建议修复顺序：开发/构建高危链 → lint/类型工具链 → npm审查复查及镜像审查。
完成条件：明确升级差异；npm ci、npm test、typecheck、lint、build与既有UI回归；复查audit，
对残留条目逐项记录暴露与处置。不得使用自动 `npm audit fix --force` 代替评审。

## 来源核对与评审边界

已核对 [Vite跨源读取通告](https://github.com/advisories/GHSA-vg6x-rcgg-rjx6)、
[PostCSS sourceMappingURL通告](https://github.com/advisories/GHSA-6g55-p6wh-862q)和
[minimatch通告](https://github.com/advisories/GHSA-g3hv-75wg-m249)；其余链接保存在原始audit结果。
单个通告修复版本不代表该包其他通告也已修复。以上原只读审查未修改package.json或package-lock.json。
本事项独立处理：视频取消只移除视频阻断，不能被解释为漏洞豁免。负责人在最终评审中
决定依赖修复与合并/发布的安排；代码、测试、故障实验、干净检出、文档和Git仍按既定范围验收。

## 修复执行起点（2026-11-14）

已读取AGENTS、PRD、AGENT_DESIGN、E3.2阶段说明及PROJECT_STATE；E3.2已完成，
本轮为负责人授权的独立依赖维护。远端刷新后main仍为
`2a1fee8b26d10ab2251a4e731d006a6f3b54ec42`，工作区干净，无更新差异；
由origin/main创建 `codex/frontend-dependency-fixes`，不修改ui-prototype或恢复机制，不合并或发布。
Node `v24.16.0` / npm `11.13.0`；起始package-lock SHA-256：
`8430452218bb86a5cfe7882a672c516392e5c15bedf3c5fea7c299a3eea62a45`。
[起始版本及资产摘要](../backend/evaluation_output/frontend-dependency-fixes/baseline.json)、
[修复前audit](../backend/evaluation_output/frontend-dependency-fixes/audit-before.json)已保存。
新audit与原审查相同：14条（2低/9中/3高）。

### 组合A：开发服务器与构建链

| 安装节点 | 原版本 → 本组版本 | 选择依据 |
| --- | --- | --- |
| node_modules/vite | 6.0.7 → 6.4.6 | 保留6主版本；现有plugin-react4.3.4声明支持Vite6，不升级React或插件 |
| node_modules/esbuild及平台包 | 0.24.2 → 0.25.12 | Vite6.4声明的^0.25.0正常解析，不强制覆盖0.x API |
| node_modules/postcss | 8.4.49 → 8.5.23 | 所查PostCSS通告最高受影响版本为8.5.22，同主版本首个修复补丁 |
| node_modules/source-map-js | 1.2.1 → 1.2.2 | 通过现有^1.2.1范围更新，修复indexed map偏移导致的阻塞 |
| node_modules/postcss-selector-parser | 6.1.4 → 6.1.6 | 保留6主版本，现有依赖范围内更新，避开<6.1.5 |

不使用force、overrides或全量依赖刷新。先更新精确Vite/PostCSS，随后仅对source-map-js与
selector-parser运行定向 `npm update ... --package-lock-only --ignore-scripts`。
Vite最初试验6.4.4后，audit发现[仅影响6.4.4的查询绕过](https://github.com/advisories/GHSA-8g5g-mxqh-grgj)，
保留[中间audit](../backend/evaluation_output/frontend-dependency-fixes/audit-build-chain.json)；
改为同6.4系列当前补丁6.4.6并重新验证，不将最初候选当作修复完成。
其余依据：[PostCSS](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp)、
[source-map-js](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)、
[selector-parser](https://github.com/advisories/GHSA-rj75-hqrm-r3gf)。
传递变化包含Vite局部fdir/picomatch节点及esbuild平台包；cssesc移除，业务依赖未升级。

升级前与组合A均运行 `npm test`（5通过、零跳过）、`npm run typecheck`、`npm run lint`、
`npm run build`，全部通过；组合A另用 `npm ci`验证安装。
[原始基线日志](../backend/evaluation_output/frontend-dependency-fixes/baseline-checks.log)、
[最终组合A日志](../backend/evaluation_output/frontend-dependency-fixes/build-chain-final-checks.log)、
[组合A audit](../backend/evaluation_output/frontend-dependency-fixes/audit-build-chain-final.json)：
9条（2低/7中/0高），高危及开发/构建链告警已消除，lint链待下一组处理。

针对性验证命令（先在frontend执行npm ci与npm run build，再回仓库根目录）：
`node scripts/verify_frontend_dependencies.mjs`。
复用现有Vite/PostCSS依赖，不引入框架；[脚本](../scripts/verify_frontend_dependencies.mjs)
仅管理自己启动的loopback服务器及带UUID的合成拒绝文件，finally关闭并清理探针，不读取真实.env。
原锁文件在独立临时目录重建，其CSS与起始SHA完全相同，
[基线CSS](../backend/evaluation_output/frontend-dependency-fixes/baseline.css)按原字节保留。
新CSS64517字节，原64540字节；差异仅13处简单媒体查询的空白压缩。
AST比较仅归一化这些max-width/reduced-motion条件空白，完整保留其他参数、选择器、声明、顺序。
另验证PostCSS/autoprefixer→source map→source-map-js原位置/源内容往返，生产未启用.map输出。
Vite、PostCSS、Tailwind配置及源CSS均未修改。
[HTTP/CSS结果](../backend/evaluation_output/frontend-dependency-fixes/http-css.json)含15项检查：
dev入口、S00154样本、runtime模块、preview及JS/CSS资源可访问；构建JS仍包含案件及审批/草稿/消息入口；
四种合成.env查询均拒绝，foreign Origin未获CORS授权。无浏览器工具，未渲染页面、点击按钮、
核实视觉布局或调用真实后端操作；HTTP资源可用不能替代交互验收。
检查器初始按字节相等断言失败，以上旧版重建与AST比较定位后修正检查方式；
首次端口绑定受沙箱限制，取得环境权限后重跑通过，不将失败尝试算入通过数量。

### 组合B：lint链与最终结果

组合A提交 `d75ee6c0e27844ef86b69bc5e5bedf1790ad991f` 已推送后，升级
`eslint`及配套 `@eslint/js`：9.17.0 → **9.27.0**。这是audit原受影响9.10–9.26范围之后
的首个9系列版本；plugin-kit依赖范围提升至^0.3.1，锁定实际 **0.3.5**（原0.2.8），
满足[plugin-kit公告](https://github.com/advisories/GHSA-xffm-g5w8-qvg7)修复下限0.3.4。
ESLint声明Node ^18.18 / ^20.9 / >=21.1，本机24.16满足；旧typescript-eslint的ESLint9 peer满足。
@eslint/core/config-array按上游范围更新，新增config-helpers；不修改规则、产品源码或构建配置。
typescript-eslint8.18.2、TypeScript5.7.2和全部React相关直接依赖保持不变。

最终再次执行npm ci；npm test **5通过/0失败/0跳过**，typecheck、lint、build全部退出0；
`npm ls --all --json`退出0，无invalid/missing peer。
[完整检查日志](../backend/evaluation_output/frontend-dependency-fixes/lint-chain-checks.log)、
[安装树](../backend/evaluation_output/frontend-dependency-fixes/installed-tree.json)、
[最终HTTP/CSS检查](../backend/evaluation_output/frontend-dependency-fixes/http-css-final.json)
保留证据；最终组合15项HTTP/CSS检查通过，沿用上文的非浏览器层级限制。
未改后端代码或恢复逻辑，未重复运行后端/官方数据/真实模型及W3进程实验；其原验证范围不变。
组合B交付时尚未验证Node22 Docker路径；后续补验见文末。浏览器交互仍未验证。

[最终audit](../backend/evaluation_output/frontend-dependency-fixes/audit-after.json)：
**7中危/0低/0高/0严重**，退出1为仍有告警；非查询失败，不视为零漏洞。
相较起点移除7个受影响包条目（Vite、esbuild、PostCSS、source-map-js、selector-parser、
ESLint、plugin-kit），最终无新增包条目或新增公告。中间6.4.4特有告警未进入最终锁文件。
[机器可读对比](../backend/evaluation_output/frontend-dependency-fixes/summary.json)列出公告集合及全部安装路径版本变化；
锁文件累计41个节点变化：36个版本变化、4个新增、1个移除（含esbuild各平台optional包），不是41个业务包升级。
最终锁文件SHA-256（Git内LF字节）：
`b56b5887cab80c8227c3a8200059d9b2b526e483764f2686c43365a23ec24ed1`。

### 剩余风险与需要沟通区决定的后续

剩余7个audit条目均对应[同一minimatch公告](https://github.com/advisories/GHSA-g3hv-75wg-m249)，
不是7个独立漏洞。受影响7–11.0.0，公告修复版11.0.1。
实际安装 `node_modules/@typescript-eslint/typescript-estree/node_modules/minimatch` **9.0.9**；
这是旧eslint工具链的^9.0.4正常解析；另一根节点 `node_modules/minimatch` **3.1.5** 不在该公告范围。
[修复前链](../backend/evaluation_output/frontend-dependency-fixes/minimatch-before.json)与
[最终链](../backend/evaluation_output/frontend-dependency-fixes/minimatch-after.json)保留npm explain结果。

| 剩余条目（均位于node_modules下） | 关系、暴露条件与处理 |
| --- | --- |
| @typescript-eslint/typescript-estree/node_modules/minimatch | 唯一直接公告节点；攻击者可控glob模式导致lint进程匹配工作量放大，不能据此认定浏览器页面可利用 |
| @typescript-eslint/typescript-estree | 持有上述^9依赖，文件/项目匹配入口，保留告警 |
| @typescript-eslint/parser | 传递依赖estree，保留告警，不换parser掩盖 |
| @typescript-eslint/type-utils | 传递依赖estree/utils，保留告警 |
| @typescript-eslint/utils | 传递依赖estree，保留告警 |
| @typescript-eslint/eslint-plugin | 传递依赖type-utils/utils，保留告警 |
| typescript-eslint | 顶层聚合工具，传递依赖以上节点，保留告警 |

现有eslint.config.js使用固定本地files glob，不启用项目型parserOptions，也不从API接收glob；
本项目常规lint的触发输入受控，但审查不可信PR、插件或修改后的配置仍可能让开发/CI进程暴露。
生产最终nginx阶段不运行ESLint；这是静态暴露判断，未执行DoS PoC或证明不可利用。
临时处理：只运行已审查的lint配置，不将不可信配置/任意glob接入有凭据的长驻进程；
不把本轮结果视为风险接受或发布许可，剩余事项保持开放供负责人决定。

本轮npm registry所列typescript-eslint最新为8.72.2（[版本快照](../backend/evaluation_output/frontend-dependency-fixes/typescript-eslint-latest.json)）；
其estree仍声明minimatch **^10.2.2**（[上游约束](../backend/evaluation_output/frontend-dependency-fixes/upstream-estree.json)），
升级至该8版本仍不能落到11.0.1，因此未作无效升级。8.73.0查询返回404，不将未发布版列为方案。
audit建议降级typescript-eslint7.3.1跨越直接工具主版本，且需重核TypeScript5.7/ESLint9兼容性，
不采用自动建议。将9/10传递依赖强制override到11同样超出声明范围，本轮不实施。
建议优先等待上游8系列采用修复依赖或9/10得到正式回补，再评估最小兼容更新；若需要换主版本、
换parser或调整TypeScript/ESLint主版本，应先提交独立兼容方案及回归范围，经沟通区确认后执行。

### 交付状态

**兼容升级及Node22 Docker补验已通过沟通区评审；已通过PR #2合并main；minimatch剩余风险未关闭。**
开发分支保留，不创建发布标签。已有E3.2历史、视频取消决定、外部输入跳过、
单进程/身份声明及回滚限制均保留。文档本地链接与diff检查后按验证组合提交并推送。

### Node22 Docker交付路径补验（2026-11-14）

起点 `975933705fea428331954b22b9844de0b66707f8`，分支仍为
`codex/frontend-dependency-fixes`；刷新远端后与本地一致，main仍为2a1fee8，开始时工作区干净。
使用当前提交中的原始 `frontend/Dockerfile`、`.dockerignore`、package.json与锁文件，
没有修改产品源码、Dockerfile、依赖版本或锁文件，不扩展工具链主版本迁移。
本次新[验证脚本](../scripts/verify_frontend_node22.py)由本次补验提交保存；
报告starting_commit是被验证的前端快照9759337，不表示该提交已经包含后续新增的验证脚本。

复现：在仓库根目录执行 `python scripts/verify_frontend_node22.py`（Python>=3.12、
Docker Linux引擎、基础镜像/npm源网络访问权限）。脚本通过git archive导出已提交frontend到
独立临时目录，拒绝frontend未提交改动，排除本机node_modules、dist、.env与增量缓存；
用同一上下文先 `docker build --no-cache --target build`，再按原Dockerfile构建最终nginx镜像。
实际完整argv、退出码及原始输出保存在每个实验目录的report.json与对应log文件。

| 环境/镜像 | 实际结果 |
| --- | --- |
| Docker Desktop / Engine / 平台 | 4.86.0 / 29.7.2 / linux/amd64，WSL2 |
| node:22-alpine | Node **v22.23.5** / npm **10.9.9**；基础镜像digest `sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a` |
| nginx:1.27-alpine | nginx **1.27.5**；基础镜像digest `sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10` |
| 验证build镜像ID | `sha256:38a843f541a7acc00e3d117d9ff220fa53f2c0aad1b2ab773a835d79a48ccfd7` |
| 最终交付镜像ID | `sha256:32b6fd796af0a7495d1ce9b287699110573cbbe25ab7817e2e13cf4cbb569e70` |

原Dockerfile基础镜像标签为浮动标签；上表记录本次解析结果，不承诺未来相同标签仍解析到相同内容。
Windows Git导出在本环境按core.autocrlf生成CRLF；导出锁文件原字节SHA-256为
`566f7c596563f87e8280b9a320c3aa170c59ca9473e3fb41398022757e271c4c`，
归一化LF后与Git对象的 `b56b5887…ec24ed1` 完全一致。npm ci后容器内原字节摘要保持566f7c59…，
没有重新解析或改写锁文件。此换行差异解释了导出上下文摘要与上文Git LF摘要的区别。

最终成功实验为 `node22-3847c80d4a60447c9fc4182e3bdf75fb`：
[完整报告](../backend/evaluation_output/frontend-dependency-fixes/node22-3847c80d4a60447c9fc4182e3bdf75fb/report.json)、
[Dockerfile构建日志](../backend/evaluation_output/frontend-dependency-fixes/node22-3847c80d4a60447c9fc4182e3bdf75fb/build-node22.log)、
[nginx镜像构建日志](../backend/evaluation_output/frontend-dependency-fixes/node22-3847c80d4a60447c9fc4182e3bdf75fb/build-nginx.log)、
[容器检查日志](../backend/evaluation_output/frontend-dependency-fixes/node22-3847c80d4a60447c9fc4182e3bdf75fb/node22-checks.log)。

| 隔离环境检查 | 结果 |
| --- | --- |
| npm ci | 通过，安装232包；无宿主机依赖挂载，检查容器退出0 |
| npm test | 5通过、0失败、0跳过；不把多轮执行算作新增用例 |
| typecheck | 清理容器内部TypeScript增量产物后运行，通过 |
| lint / build / npm ls --all | 全部通过，构建1620模块 |
| 最终nginx首页与资源 | /及/index.html可读，引用JS/CSS均HTTP200；Content-Type和SHA-256与独立检查容器dist一致 |
| 产物 | JS 244682字节、CSS 64517字节；[完整资产摘要](../backend/evaluation_output/frontend-dependency-fixes/node22-3847c80d4a60447c9fc4182e3bdf75fb/assets.json) |
| nginx运行内容 | node/npm命令不存在；未运行Vite开发服务器 |
| npm audit | 7中危、0低/高/严重；退出1，仍为同一minimatch公告，[本轮原始结果](../backend/evaluation_output/frontend-dependency-fixes/node22-3847c80d4a60447c9fc4182e3bdf75fb/audit.json) |

两次未完成实验亦保留，不计为完整通过：
[66f508d4报告](../backend/evaluation_output/frontend-dependency-fixes/node22-66f508d402c743f487e2a83f4883a32a/report.json)
在基础镜像缺少Labels字段时采集失败，未进入构建；
[c2f4a9f7报告](../backend/evaluation_output/frontend-dependency-fixes/node22-c2f4a9f774594689b9ec2d6074adbfc4/report.json)
已完成Node22全部检查，但检查器资产键保留了前导斜杠，HTTP摘要比较发生KeyError。
修正两处观测脚本后，重新运行完整路径得到上述PASSED。两者均非产品兼容失败，
不改写失败报告为成功；清理均完成。新脚本另通过Ruff lint/format及Python编译检查。

所有容器/镜像标签用独立UUID及io.resonique.frontend-node22-validation标签；
清理前核对所属标签，删除仅针对本次明确创建的ID/tag。不使用compose down、全局prune或业务卷。
nginx仅发布随机127.0.0.1端口，不挂载业务目录/数据库；每轮临时上下文自动清理。
成功轮两个容器和两个验证镜像标签均已移除，原有容器ID与运行/退出状态保持一致。
保留下载的基础镜像和Docker构建缓存，避免清理共享资源；库存证据只保留ID/状态，
未提交其他项目的名称、挂载和网络信息（前两轮采集的附加库存字段已缩减）。
工具日志仅归一化换行和行末空白，保留输出文字、步骤及退出码；该输出格式整理不改验证逻辑。

剩余minimatch风险继续独立开放，本轮不override、不降级、不迁移主版本。
npm ci仍有ESLint9.27.0不再支持的上游弃用提示，未造成安装或检查失败，
后续维护版本选择单独评估，不据本次通过宣布长期支持。
本轮验证到Linux/amd64 Node22构建与nginx静态交付；**没有浏览器渲染、点击、案件交互或真实API操作验证**，
不等同视觉/端到端验收，亦未进行基础镜像CVE扫描或ARM平台验证。
未改后端，无需且没有重跑完整后端故障矩阵。补验提交/推送并交回沟通区后，PR合并已获授权并执行，见下文；发布仍待确认。

### 实际合并结果（2026-11-14）

[PR #2](https://github.com/xingnan-dev/Empathy-Copilot/pull/2) 以merge commit
`4dbf25f86ec8702f4bb5ef6d8746982bce242279` 合入main，两个父提交分别为
原main `2a1fee8b26d10ab2251a4e731d006a6f3b54ec42` 和已评审交付
`7b03126b9c9890d03cb0653211d51d02522fc1a2`。
完整保留d75ee6c、9759337、7b03126三个提交，无squash、rebase或强制推送。
合并前刷新确认main无新增提交、工作区干净；PR源为
`codex/frontend-dependency-fixes`，目标为`main`，120个文件的差异清单与本地已评审范围完全一致。
GitHub报告CLEAN/MERGEABLE；main无分支保护、活动ruleset或Actions工作流，PR无状态检查。
这些仓库设置不替代前述本地和Node22验证结果。
合并后确认远端main包含7b03126，并将本地main快进至合并提交；开发分支与既有比赛标签保留。
此后仅同步PROJECT_STATE及本记录，检查文档本地链接和diff，不重复运行产品测试或Docker实验。
剩余minimatch七条中危、ESLint弃用提示及浏览器交互/镜像CVE扫描/ARM未验证范围继续保留，
不把兼容修复合并表述为漏洞全部关闭或安全认证；不创建发布标签。
