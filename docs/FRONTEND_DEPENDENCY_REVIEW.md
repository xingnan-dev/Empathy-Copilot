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
单个通告修复版本不代表该包其他通告也已修复。当前未修改package.json或package-lock.json。
本事项保持独立开放：视频取消只移除视频阻断，不能被解释为漏洞豁免。负责人在最终评审中
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
