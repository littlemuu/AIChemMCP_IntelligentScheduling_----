# AIMCP 与智能调度算法模块连接方案

## 1. 目标

本文档说明如何将 `AIChemMCP-main` 中的 AIMCP 模块与智能调度算法模块连接起来，使系统能够从“高层实验任务规划”进一步落到“底层工作站与机器人调度执行”。

连接完成后，系统应具备以下能力：

- AIMCP 负责接收用户目标、调用 LLM、生成实验工作流；
- 智能调度模块负责根据资源状态安排工作站和机器人；
- Action 层负责把调度器生成的执行指令发送给硬件或仿真平台；
- 两部分之间通过统一的任务模型和命令接口协同工作。


## 2. 两个模块的职责划分

为了避免系统耦合混乱，必须先明确 AIMCP 和调度模块各自负责什么。

### 2.1 AIMCP 模块负责什么

`AIChemMCP-main` 更适合承担“高层决策”和“工具编排”职责，例如：

- 接收用户输入的实验目标；
- 借助 LLM 规划实验流程；
- 选择需要调用哪些工具；
- 向不同 MCP Server 发出工具调用请求；
- 汇总实验结果并继续迭代规划。

它本质上更像一个**实验任务编排层**。

### 2.2 智能调度模块负责什么

智能调度模块更适合承担“底层执行资源分配”职责，例如：

- 维护工作站和机器人状态；
- 维护时间线 `timeline`；
- 判断任务当前是否可执行；
- 判断无缝衔接步骤是否能同时满足；
- 为机器人和工作站做未来时间窗预留；
- 生成真正可执行的设备动作命令。

它本质上更像一个**资源调度层**。

### 2.3 结论

因此，AIMCP 不应直接控制机器人和工作站，而应先把实验任务交给调度器，由调度器统一决定：

- 哪个任务何时开始；
- 用哪台工作站执行；
- 由哪个机器人负责转运；
- 是否满足无缝连接约束。


## 3. 推荐总体架构

推荐采用如下结构：

```text
用户 / LLM
    |
    v
AIMCP Agent
    |
    v
Action Server
    |
    v
Scheduling Runtime
    |
    +--> Scheduler
    +--> Workstations / Robots / Tasks
    |
    v
硬件控制接口 / 仿真平台
```

在这个结构中：

- `Agent` 负责理解目标和规划实验；
- `Action Server` 负责接收动作请求；
- `Scheduling Runtime` 负责维护调度器实例和资源状态；
- `Scheduler` 负责生成工作站与机器人的调度决策；
- 硬件接口负责真正执行动作。


## 4. 当前项目中的现有连接点

根据当前代码结构，最适合的连接位置如下：

### 4.1 AIMCP 入口

- `AIChemMCP-main/agent.py`

该文件负责：

- 启动各个 MCP Server；
- 发现工具；
- 根据 LLM 输出分发工具调用请求。

这意味着 AIMCP 当前已经具备了“上层任务请求入口”。

### 4.2 Action Server

- `AIChemMCP-main/servers/action_server.py`

该文件负责：

- 暴露 `robotic_reaction`、`robotic_measurement`、`robotic_characterization` 等工具；
- 接收 MCP 请求并调用工具实现。

这意味着它天然适合作为“调度模块的外层网关”。

### 4.3 Action Tools

- `AIChemMCP-main/tools/action_server_tools.py`

该文件目前还是空实现：

```python
class ActionServerTools:
    def tool_robotic_reaction(self):
        raise NotImplementedError
```

这恰好说明，这里正是最合适的接入点。

### 4.4 调度模块

你们当前已经有一套可运行的调度核心代码：

- `IntelligentScheduling-main/src/models.py`
- `IntelligentScheduling-main/src/scheduler.py`
- `IntelligentScheduling-main/src/main.py`

其中：

- `models.py` 负责定义任务和资源模型；
- `scheduler.py` 负责前瞻预留与调度决策；
- `main.py` 当前主要承担本地仿真入口与状态推进逻辑。


## 5. 推荐连接原则

### 5.1 不要直接把调度逻辑塞进 Agent

`agent.py` 的职责是：

- 规划；
- 分发工具调用；
- 管理多服务器通信。

如果把工作站状态判断、机器人预留、时间线维护都直接写进 `agent.py`，会导致：

- 上层规划逻辑和底层执行逻辑混在一起；
- 代码难维护；
- 后续更换硬件接口或调度算法时改动过大。

因此不建议在 `Agent` 中直接写调度代码。

### 5.2 不要让 Action Server 直接操作硬件细节

`action_server.py` 更适合只保留：

- MCP 协议收发；
- 参数解析；
- 工具路由。

真正的业务逻辑应该放在 `action_server_tools.py` 和调度运行时中。

### 5.3 调度器应作为独立运行时存在

调度器不是一次性函数，而是一个长期存在、持续维护状态的组件。

它需要长期维护：

- 当前任务队列；
- 各工作站状态；
- 各机器人状态；
- 时间线和预留信息；
- 当前样品流转情况。

因此应该把它设计成一个独立的 `runtime` 或 `service`，而不是每次请求都重新创建。


## 6. 推荐实现方案

建议在 `AIChemMCP-main` 中新增一个调度模块目录，例如：

```text
AIChemMCP-main/
  scheduling/
    __init__.py
    models.py
    scheduler.py
    runtime.py
```

其中：

### 6.1 `models.py`

负责存放调度系统的数据模型：

- `Task`
- `TaskStatus`
- `Resource`
- `ResourceStatus`
- `Workstation`
- `Robot`
- `Tool`

### 6.2 `scheduler.py`

负责存放核心调度算法：

- 候选任务选择；
- 无缝连接判断；
- 机器人与工作站的时间窗预留；
- 指令生成。

### 6.3 `runtime.py`

负责维护调度器的长期运行状态：

- 初始化工作站和机器人；
- 保存 `Scheduler` 实例；
- 接收 AIMCP 传入的新任务；
- 推进系统时间；
- 更新资源状态；
- 取出待执行命令。

这层非常重要，因为 `main.py` 当前的仿真逻辑，本质上就应该迁移到这里。


## 7. 实际连接流程

推荐把完整调用流程设计成如下顺序。

### 第一步：AIMCP 生成实验任务

用户提出实验目标后，AIMCP 的 `Agent` 通过 LLM 生成一条工作流，比如：

- 需要先反应；
- 再测量；
- 再表征；
- 或者执行一个多步实验流程。

此时 AIMCP 拿到的仍然是“实验语义”。

### 第二步：Action Server 接收请求

当 `Agent` 决定调用动作工具时，会把请求发到：

- `ActionServer`

例如：

- `robotic_reaction`
- `robotic_measurement`

### 第三步：Action Tools 将请求转换为调度任务

在 `action_server_tools.py` 中，不应直接立刻执行机器人动作，而应先把请求转换成一个调度任务 `Task`。

例如：

```text
robotic_reaction(recipe=..., vessel_id=...)
    ->
submit Task(
    workflow_tools=[...],
    processing_times={...},
    seamless_steps=[...],
    sample_id=...
)
```

这一步就是把 AIMCP 的“实验请求语义”翻译成调度器能理解的“资源任务语义”。

### 第四步：任务进入调度运行时

`ActionServerTools` 将新任务提交给 `SchedulingRuntime`：

- `runtime.submit_task(task)`

调度运行时将该任务加入 `Scheduler.task_queue`。

### 第五步：调度器生成资源执行计划

随后由运行时驱动调度器：

- `runtime.tick()`
- `scheduler.schedule(current_time)`

调度器会根据当前资源状态：

- 检查工作站是否空闲；
- 检查机器人是否可用；
- 检查下一工作站能否承接；
- 决定是否预留未来时间窗；
- 生成执行命令。

### 第六步：Action Tools 执行调度命令

调度器返回的命令不会直接暴露给 LLM，而应由 `ActionServerTools` 内部消化并发送给硬件控制接口。

例如命令可能是：

- `START_PROCESSING`
- `MOVE_TO_PICKUP`
- `TRANSPORT_SAMPLE`

### 第七步：硬件回执驱动状态更新

硬件系统执行后返回状态或 ACK：

- 工作站开始加工；
- 工作站完成；
- 机器人已取样；
- 机器人已放样。

这些回执再反馈给 `SchedulingRuntime`，由它更新：

- `Task.status`
- `Workstation.status`
- `Robot.status`
- `timeline`

这样形成完整闭环。


## 8. 建议的数据接口

要让 AIMCP 和调度器顺利连接，建议定义统一的任务提交接口。

例如：

```python
{
    "task_id": "task_001",
    "sample_id": "sample_001",
    "task_type": "reaction",
    "workflow_tools": ["reaction_tool", "measurement_tool"],
    "processing_times": {
        "reaction_tool": 300,
        "measurement_tool": 60
    },
    "seamless_steps": [(0, 1)],
    "priority": "normal"
}
```

这个接口的作用是把 AIMCP 的实验规划与调度器的数据模型标准化。

建议至少包含：

- `task_id`
- `sample_id`
- `task_type`
- `workflow` 或 `workflow_tools`
- `processing_times`
- `seamless_steps`
- `priority`


## 9. Action 层推荐改法

建议把 `action_server_tools.py` 改造成下面三层结构：

### 9.1 任务提交接口

例如：

- `submit_experiment_task(...)`

负责：

- 接收 AIMCP 的动作请求；
- 解析成 `Task`；
- 提交给调度运行时。

### 9.2 调度推进接口

例如：

- `tick_scheduler(...)`

负责：

- 推进调度器；
- 获取新的执行命令；
- 触发资源状态更新。

### 9.3 硬件执行接口

例如：

- `execute_hardware_command(...)`

负责：

- 将调度器输出的命令发送给真实设备或仿真平台；
- 接收状态回执；
- 回写运行时状态。


## 10. 当前最适合的最小实现路径

如果你们现在只是要尽快打通一个最小可运行版本，建议按这个顺序做：

### 第一步

把 `IntelligentScheduling-main/src` 中的：

- `models.py`
- `scheduler.py`

迁移到 `AIChemMCP-main/scheduling/` 中。

### 第二步

把 `main.py` 中的状态推进逻辑抽出，重构为：

- `runtime.py`

这样它就不再是脚本入口，而是一个可被 Action 层调用的运行时服务。

### 第三步

在 `action_server_tools.py` 中创建一个全局运行时实例，例如：

```python
self.runtime = SchedulingRuntime(...)
```

### 第四步

把 `tool_robotic_reaction()` 改成：

- 接收请求；
- 构造 `Task`；
- 提交给调度器；
- 返回任务已受理信息，而不是立刻假装“实验已经做完”。

### 第五步

后续再逐步接入：

- ACK 机制；
- 真实工作站状态；
- 真实机器人状态；
- 数据库或持久化存储。


## 11. 一句话总结

最合理的连接方式是：

**让 AIMCP 负责“决定做什么实验”，让智能调度模块负责“决定这些实验任务何时、在哪个工作站、由哪个机器人执行”，再由 Action Server 把调度结果转成真正的硬件动作。**

换句话说：

- AIMCP 是任务编排层；
- Scheduler 是资源调度层；
- Action Server 是执行接口层。

三层分清之后，系统才容易扩展、调试和落地。


## 12. 后续建议

如果后续要真正开始实现，推荐下一步直接做下面两件事：

1. 在 `AIChemMCP-main` 下创建 `scheduling/` 目录，并迁移调度核心代码；
2. 在 `action_server_tools.py` 中先接一个最小版 `SchedulingRuntime`，让 `robotic_reaction` 不再直接执行，而是先提交任务给调度器。

