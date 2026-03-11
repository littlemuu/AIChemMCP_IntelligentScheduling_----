# 项目介绍和需求--调度集成版本

这个目录保存的是在原始资料基础上新增的“AIMCP 接入智能调度算法”版本。

## 本版本包含的主要改动

- 在 `AIChemMCP-main/` 中加入了调度运行时
- 将 `Action Server` 与调度器接通
- 让 `Agent -> ActionServer -> Scheduler` 链路可以跑通
- 支持：
  - `robotic_reaction`
  - `robotic_measurement`
  - `robotic_characterization`
  - `scheduler_status`
  - `scheduler_advance`
  - `scheduler_run_until_complete`

## 推荐调试入口

进入：

- `AIChemMCP-main/`

运行：

```powershell
python agent.py
```

这会启动一个本地演示流程，展示：

- Agent 发现工具
- Agent 调用 Action Server
- Action Server 将任务提交给调度器
- 调度器推进到任务完成

## 目录说明

- `AIChemMCP-main/`
  - 已集成调度器的 AIMCP 版本
- `IntelligentScheduling-main/`
  - 调度算法参考代码

## 注意

这个目录是当前可继续开发的版本。
如果后续要继续做：

- 接真实硬件接口
- 接多步实验流程
- 接 LLM 自动决策

建议都在这个目录继续进行，不要在“最初版本”目录上继续改。

