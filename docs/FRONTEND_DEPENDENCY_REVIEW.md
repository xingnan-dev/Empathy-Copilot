# 前端依赖独立审查待办

2026-11-14；只读审查完成，修复仍为独立待办。本记录不宣称漏洞已消除，也不自动批准发布。
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
