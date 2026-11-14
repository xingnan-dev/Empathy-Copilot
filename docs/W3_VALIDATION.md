# W3 独立进程故障验收

起点：`3893e68012c2236cdfa5844b27430656bc8357cf`；分支：codex/phase-e3-2-readonly-recovery。
实验基础设施提交：`609e12ad39d906fc4c09d1fa301bb0de3ec26173`。规格沿用
[D2](phases/PHASE_E3_2.md)，原有回归层级见 [W2交接](W2_VALIDATION.md)。

## 运行

使用已安装依赖的 .venv、Docker Desktop 和本地 postgres:16-alpine 镜像，从仓库根目录执行：

```powershell
.\.venv\Scripts\python scripts/tool_recovery_experiment.py --repetitions 1
.\.venv\Scripts\python scripts/tool_recovery_experiment.py --repetitions 3 --regression
```

脚本自建唯一命名、所有权标签、tmpfs数据库容器，随机本机端口，不接受业务数据库作为清理目标。
单API工作进程由脚本创建、health就绪、故障边界握手、kill、wait确认退出、重启。
观察事件单独事务写入 w3_observation.events；TOOL_ENTRY是进入工具，TOOL_RETURN是查询返回，
SIDE_EFFECT_MARKER仅为F12测试副作用标记，不证明真实退款等业务完成。
实验标识逐场景唯一，固定输入摘要保存在report.json，未加载官方数据、未调用真实模型。
普通生产入口不导入实验worker或故障开关。运行时配置/release旗标/普通worker日志被局部忽略，
结构化故障现场、快照、事件和进程退出记录保存在可跟踪报告中。

握手在父进程收到数据库GATE事件后确认，记录其明确执行边界；AFTER_*发生在save提交返回后。
BEFORE_PENDING/BEFORE_COMPLETED/BEFORE_CLAIM明确表示写入前，不将它们称为已提交快照。
轮询间隔仅用于读取握手/就绪条件，不用固定睡眠推断工具执行位置。
previous_process_exited关联目标尝试原进程actor/PID、退出码和wait记录；应用仍仅记录声明。
退出清理只处理Popen创建的子进程及标签token匹配的本次容器，保留报告。

## 证据与验收层级

逐项首次运行：[现场报告](../backend/evaluation_output/w3/w3-feeac9bc5b5f48639be3d1883d639abc/report.json)。
三轮重复及业务回归：[现场报告](../backend/evaluation_output/w3/w3-419904f7f0c64aaaa01f75fa1237df0e/report.json)。
首次运行发生在基础设施提交前，三轮报告中的git_commit是正式实验代码提交；两者实验输入一致。
每个场景现场含请求、关键快照、修订号/步骤/事件数量一致性、尝试链、证据引用完整性、请求进度、
工具计数、进程身份与确认退出。F4允许显式再次查询，必须报告真实两次入口/两次返回。

| 场景 | W3进程断言及其与已有回归的关系 |
| --- | --- |
| F0 | 单API正常完成；1入口/1返回 |
| F1 | PENDING写前kill；初始revision0无调用；重启正常执行一次 |
| F2 | PENDING提交后kill；零入口；重启普通调度暂停，显式恢复完成 |
| F3 | RUNNING提交后、入口前kill；零入口；显式新尝试执行一次 |
| F4 | 返回后、COMPLETED提交前kill；RUNNING无成功证据；恢复后总2入口/2返回 |
| F5 | 恢复COMPLETED提交后kill；离线脚本续接；重启GET200且SETTLED，订单计数不增加 |
| F6 | 超时持久失败后重启恢复；原失败保留；含前置失败共2入口/1返回 |
| F7 | 两HTTP客户端向同一API重放；首请求停在RUNNING，重放202不执行，最终重放200 |
| F8 | 两独立执行进程先均到达领取CAS前握手，再放行；恰一CLAIM_WON，失败方409且零入口 |
| F9 | 恢复RUNNING后再次kill；新请求接替，保留三条尝试及INTERRUPTED父请求 |
| F10 | 使用完整回归的恢复资格、安全、预算和禁止状态检查；不声称新增每种进程变体 |
| F11 | 完整回归包含七个真实旧格式样本、PostgreSQL轮转、元数据一致性与不重复执行 |
| F12 | API工具独立事务写SIDE_EFFECT_MARKER后丢回执；UNKNOWN_OUTCOME，重启拒绝恢复，标记1次 |
| F13/F14 | 完整回归包含坏链、严格请求、暂停原因保护和预算检查 |
| F15_HTTP | 路由已生成回复但发送前kill，客户端丢回包；重启GET/原请求重放200，不再次执行 |
| F15_COMMIT | claim实际提交后注入OSError模拟确认丢失；503、重启GET/重放202，无执行资格；新人工请求可接替 |
| F16 | 完整回归包含创建时间复用、内容冲突整批拒绝、失败落库与CAS冲突保护 |

F8为独立非HTTP领取执行进程的数据库竞争，不冒称双API部署；日常运行仍单API。
F15_COMMIT是确定的提交后故障注入，不声称拔断真实数据库网络；F12是测试标记，不是业务写入对账。
F5包含初始超时一次及恢复成功一次，最终总2入口/1返回；续接本身增加0次查询。

## 失败、限制与交付

基础设施测试最初因沙箱临时路径过长失败，改为无文件系统依赖的清理所有权测试；
补齐实验脚本类型注解，静态检查通过。早期F0烟雾验证通过，正式逐项运行与重复次数以报告为准。
尚未发现需改变产品恢复规格的缺陷。跨主机fencing、真实权限认证、外部业务对账仍不在本阶段。
W3完成情况、准确次数、回归数量及最终提交号在沟通区交付记录中列出；W4须在本轮评审后开始。


## 最终结果

逐项首轮13/13通过；随后三轮39/39通过，共52次场景运行，每个变体实际4次。
正式重复运行代码为609e12a，未发现产品实现缺陷，无需修改D2或恢复实现。
完整业务回归221通过、28跳过（27官方工作簿、1真实Qwen，原因沿用W2），零失败/错误；
Ruff、mypy（105个源文件）通过，47个文档本地链接有效，diff检查通过。
报告复核确认所有实验子进程均有wait退出记录，F2–F4原尝试完整保留，F15_HTTP确有回包丢失。
故障工具入口、返回、标记次数分别列在每个checkpoint；不能把52次运行称为52种故障点。
正式回归日志和JUnit与三轮现场报告存放在同一目录。W3已完成执行交接，待评审，W4尚未开始。
