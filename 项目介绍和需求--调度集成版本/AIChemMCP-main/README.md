# AIChemMCP 智能调度原型系统

AIChemMCP 是一个面向自动化实验室场景的机器人任务调度仿真原型系统。项目把 Action Server 工具调用、调度运行时、任务/资源模型、示例数据、demo 输出和本地测试串成一条可运行的工程闭环。

当前系统定位为 simulation / mock hardware 原型：它可以演示任务提交、资源分配、模拟时间推进、状态查询和结果归档，但尚未接入真实实验室硬件，也不声明已经完成真实实验执行。

## 项目能做什么

- 将示例 reaction、measurement、characterization 请求封装为可调度任务。
- 使用模拟工作站和模拟机器人资源执行调度。
- 维护任务状态、资源状态、资源时间线和执行历史。
- 支持推进模拟时间，或运行到全部任务完成。
- 输出结构化 demo 结果到 `outputs/demo_result.json`。
- 通过本地测试验证模型、调度器、运行时、工具接口和 demo 闭环。

## 项目结构

```text
AIChemMCP-main/
├─ agent.py                         # 原有 AIMCP demo agent 入口
├─ demo.py                          # 一键运行调度仿真 demo
├─ run_tests.py                     # 本地 unittest 测试入口
├─ README.md                        # 当前项目说明
├─ llm_client.py                    # 原有 LLM client 相关代码
├─ run_all_servers.py               # 原有多 server 启动入口
├─ scheduling/                      # 调度核心模块
│  ├─ models.py                     # 任务、资源、工具、工作站、机器人数据模型
│  ├─ scheduler.py                  # 调度器：资源预留、时间线、机器人转运规划
│  ├─ runtime.py                    # 调度运行时：任务提交、时间推进、状态快照
│  └─ __init__.py                   # 导出 SchedulingRuntime
├─ servers/                         # MCP / Action Server 风格服务入口
│  ├─ action_server.py              # 机器人任务与调度控制工具路由
│  ├─ analysis_server.py            # 原有分析服务入口
│  ├─ bo_server.py                  # 原有 BO 服务入口
│  ├─ memory_server.py              # 原有记忆服务入口
│  └─ prediction_server.py          # 原有预测服务入口
├─ tools/                           # Server 调用的工具封装层
│  ├─ action_server_tools.py        # Action Server 到 SchedulingRuntime 的适配
│  ├─ analysis_server_tools.py      # 原有分析工具封装
│  ├─ bo_serveer_tools.py           # 原有 BO 工具封装
│  ├─ memory_server_tools.py        # 原有记忆工具封装
│  └─ prediction_server_tools.py    # 原有预测工具封装
├─ examples/                        # demo 输入数据
│  ├─ sample_resources.json         # 模拟工作站、机器人和工具资源
│  ├─ sample_tasks.json             # 单步示例任务
│  └─ sample_workflow.json          # 多步骤示例 workflow
├─ outputs/                         # demo 输出目录
│  └─ demo_result.json              # 当前 demo 运行结果归档
├─ tests/                           # 本地测试
│  ├─ test_scheduling_runtime.py    # 调度运行时、工具和 demo smoke tests
│  └─ __init__.py
├─ static/                          # 原有静态资源目录
├─ software_data/                   # 原有辅助数据目录
└─ dummy_planner_servers/           # 原有 planner server 示例目录
```

## 核心模块说明

### `scheduling/models.py`

定义调度系统使用的数据模型：

- `TaskStatus`：任务状态，包括 `WAITING`、`RUNNING`、`COMPLETED`、`ERROR`。
- `ResourceStatus`：资源状态，包括 `IDLE`、`BUSY`、`RESERVED`、`TRANSPORTING` 等。
- `Task`：保存任务 id、样品 id、workflow 步骤、工具列表、处理时间、当前步骤和元数据。
- `Resource`：保存资源 id、当前状态、任务时间线和当前占用任务。
- `Workstation`：工作站资源，挂载可用工具。
- `Robot`：机器人资源，用于模拟样品转运。
- `Tool`：工具能力抽象，用于连接任务步骤和工作站能力。

### `scheduling/scheduler.py`

实现资源调度逻辑：

- 维护任务队列和全部任务索引。
- 根据 `workflow_tools` 找到对应工作站。
- 为工作站预留处理时间段。
- 为多步骤 workflow 规划机器人 pickup / transport 时间。
- 支持普通步骤衔接和 `seamless_steps` 连续步骤衔接。
- 生成 `START_PROCESSING` 命令，交给运行时执行。

当前调度策略以 FCFS 为主，并保留 `SPT` 优先策略入口。

### `scheduling/runtime.py`

提供长期存在的调度运行时，是 Action Server 和 Scheduler 之间的状态层：

- 初始化模拟实验室资源：`WS_REACTOR_A`、`WS_MEASURE_A`、`WS_CHAR_A`、`RB_1`、`RB_2`。
- 提供任务提交接口：`submit_task()`、`submit_reaction()`、`submit_measurement()`、`submit_characterization()`。
- 校验输入参数，例如 workflow 工具、处理时间、样品 id、连续步骤配置。
- 推进模拟时间：`advance_time()`、`run_until_all_complete()`。
- 更新任务状态和资源状态。
- 生成运行快照：任务、工作站、机器人、资源占用、执行历史。

### `servers/action_server.py`

提供 Action Server 风格的 JSON-RPC 工具入口：

- 启动时通过 `action_server_advertise_capabilities()` 声明可用工具。
- 从标准输入读取 JSON-RPC 请求。
- 将工具调用路由到 `tools/action_server_tools.py`。
- 对外暴露 6 个原型工具：
  - `robotic_reaction`
  - `robotic_measurement`
  - `robotic_characterization`
  - `scheduler_status`
  - `scheduler_advance`
  - `scheduler_run_until_complete`

其中 reaction / measurement / characterization 是用于演示的实验任务类型，不代表系统已经接入真实实验设备。

### `tools/action_server_tools.py`

封装 Action Server 到调度运行时的适配逻辑：

- 内部持有一个 `SchedulingRuntime` 实例。
- 将工具参数转换为运行时方法调用。
- 用 `_safe_call()` 统一包装正常返回和异常返回。
- 对非法输入返回结构化错误，包括 `INVALID_INPUT` 和当前 `runtime_status`。
- 保证上层工具调用可以拿到完整状态快照，便于 demo 展示和调试。

### `examples/`

保存 demo 使用的可复现输入：

- `sample_resources.json`：模拟工作站、模拟机器人和工具资源配置。
- `sample_tasks.json`：单步示例任务，包括 reaction、measurement、characterization 类型。
- `sample_workflow.json`：多步骤 workflow 示例，包含 `reaction_tool -> yield_measurement_tool -> hplc_tool` 和 `seamless_steps`。

这些数据用于验证调度逻辑，不代表真实实验室硬件配置。

### `outputs/`

保存 demo 输出：

- `demo_result.json`：记录 demo 模式、提交任务、调度过程摘要、最终任务状态、仿真时间、资源使用和执行历史。

当前示例输出中 `demo_mode` 为 `simulation`，最终 `all_completed` 为 `true`。

### `tests/`

保存本地测试：

- `test_scheduling_runtime.py`：覆盖任务模型、调度器资源预留、运行时任务提交和完成、工具层结构化错误、demo 输出生成等行为。

测试使用 Python 标准库 `unittest`，不依赖外部服务。

## 调用链路

```text
User / Agent
  -> servers/action_server.py
  -> tools/action_server_tools.py
  -> scheduling/runtime.py
  -> scheduling/scheduler.py
  -> scheduling/models.py
  -> outputs/demo_result.json
```

这条链路体现了接口层与调度层的解耦：Action Server 负责工具路由，Tools 层负责参数适配和错误包装，Runtime 维护状态，Scheduler 负责资源预留和命令生成，Models 提供统一数据结构。

## 快速运行

进入项目目录：

```powershell
cd AIChemMCP-main
```

运行 demo：

```powershell
python demo.py
```

demo 会读取 `examples/*.json`，提交示例任务，推进模拟时间，并写入：

```text
outputs/demo_result.json
```

运行测试：

```powershell
python run_tests.py
```

如果本地安装了 `pytest`，也可以运行：

```powershell
pytest
```

## 当前完成情况

- 已完成任务模型和资源模型。
- 已完成调度运行时 `SchedulingRuntime`。
- 已完成调度器资源预留与模拟机器人转运。
- 已完成 Action Server 工具路由和 Tools 封装。
- 已完成示例数据、demo 演示闭环和输出归档。
- 已完成基础 unittest 测试验证。

## 边界说明

当前系统是实验室机器人调度仿真原型：

- 未接入真实机械臂。
- 未接入真实仪器。
- 未完成真实实验执行。
- 未实现真实设备 ACK、超时重试和安全联锁。
- 未实现生产级复杂调度和真实实验反馈闭环。

后续可以在现有结构上继续扩展真实硬件协议、异常恢复、复杂依赖调度、可视化监控和 LLM 规划反馈。

