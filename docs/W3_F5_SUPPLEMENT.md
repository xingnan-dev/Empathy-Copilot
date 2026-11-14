# W3 F5 定向补验

2026-11-14；起点 ae294ca43f4d7c31295e4bc7e7d2cfc1896b04fa，E3.2 分支，W4继续暂缓。
原W3报告保留，但原订单计数只覆盖API实验worker；普通CLI的factory未接入计数。
W2父进程execution_counts同样不能证明子进程查询次数，已修正测试注释及交接说明。

## 观测方式

新增 scripts/observe_completed_recovery.py，仅供实验启动：包装原CLI模块的
build_postgres_workflow，在返回工作流的注册表execute上记录订单入口和返回，再调用原main。
正常CLI没有此观测包装；补验增加独立观测事务和安装事件，不改原脚本、状态转换、工具结果或续接逻辑。
事件持久化到同一隔离库的w3_observation表，包含独立CLI actor和实际PID；进程退出后仍可读取。
每次真实续接必须出现CLI_OBSERVER_INSTALLED；零查询不能靠“没有任何观测事件”判定。

每轮先创建独立f5-control实验案件，启动包装进程，通过同一工厂/执行包装主动调用订单工具一次，
验证1入口、1返回。随后用另一实验标识执行真实F5：原API在恢复COMPLETED提交后终止并wait，
包装子进程调用原main，验证新增订单入口/返回均0，调查到WAITING_FOR_USER、请求SETTLED、
原Evidence与全部尝试记录相同；重启API后GET200稳定且原请求重放不执行。
控制案件与真实F5分别持久计数，报告明确保存两者标识和原始事件，不合并计数。

## 实际结果与命令

```powershell
.\.venv\Scripts\python scripts/tool_recovery_experiment.py --cases F5 --repetitions 3 --regression
```

脚本自建并清理唯一标签tmpfs PostgreSQL容器与API子进程，不操作业务库。
[新增原始报告](../backend/evaluation_output/w3/w3-561c3576356e4367a72b35cd3008c4b9/report.json)
保存本轮固定样本摘要、环境、现场快照和持久事件。报告git_commit为补验起点，实验源修改随本补验提交。

| 轮次 | 独立离线正对照入口/返回 | 真实F5 CLI新增入口/返回 | 原状态/GET断言 |
| --- | --- | --- | --- |
| 1 | 1/1 | 0/0 | 通过 |
| 2 | 1/1 | 0/0 | 通过 |
| 3 | 1/1 | 0/0 | 通过 |

对应测试随完整回归重跑：221通过、28跳过（27官方工作簿、1真实Qwen）；零失败/错误。
Ruff和mypy通过。没有重跑其他W3进程场景：共享设施的非F5路径未改变，新增逻辑限定F5分支。
原F5报告的状态推进断言仍有价值，但旧计数不再作为CLI零调用证据；以本次正对照和实际子进程
观测为准。无产品实现缺陷或规格变更，本次修复实验观测覆盖，交回评审后再决定W4。
