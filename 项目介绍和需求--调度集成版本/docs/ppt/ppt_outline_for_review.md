# AIChemMCP 智能调度原型系统结题 PPT 大纲确认稿

> 阶段状态：大纲确认稿。  
> 本稿基于当前项目真实文件、demo 输出和测试结果整理，不声明真实硬件已接入。当前系统定位为“仿真调度 / 模拟设备接口 / 原型系统”。

## 1. 总体建议

- **建议总页数：21 页**，符合 18-22 页的结题汇报容量。
- **汇报定位：**工程实践结题展示，重点展示从 AIMCP Action Server 到调度运行时的工程化闭环。
- **内容边界：**当前项目已实现可运行的仿真调度原型，未接入真实机器人、真实工作站、真实仪器或真实设备 ACK/异常恢复协议。
- **视觉风格：**清爽专业、科技感、工程系统展示风。
- **推荐配色：**深蓝 `#0B1F3A`、青色 `#16C7D9`、科技蓝 `#1E6BFF`、深灰 `#2B3440`、浅灰白背景，少量绿色表示 OK/完成，少量橙色表示待扩展。
- **页面表达：**少文字、多图形；优先使用架构图、流程图、模块卡片、运行截图、测试结果截图、JSON 结果局部截图。
- **真实输出依据：**
  - `AIChemMCP-main/outputs/demo_result.json`：`demo_mode = simulation`，`all_completed = true`，`simulation_time = 152`。
  - `python demo.py` 当前运行结果：`Mode: simulation/mock hardware`，最终 `All completed: True`，`Final simulation time: 152`。
  - `python run_tests.py` 当前运行结果：8 个 unittest，结果 `OK`。

## 2. 页面大纲

| 页码 | 标题 | 核心信息 | 推荐视觉形式 | 需要使用的项目素材 |
|---:|---|---|---|---|
| 1 | AIChemMCP 智能调度原型系统 | 面向自动化化学实验流程的 AIMCP 调度集成原型；强调 simulation / mock hardware | 深色科技封面，大图背景 + 半透明标题层 + 关键词标签 | `README.md`、`AIChemMCP-main/README.md`；可用 AI 生成自动化实验室抽象背景 |
| 2 | 项目背景：从实验规划到资源调度 | AI for Chemistry 场景中，实验任务需要转化为可执行、可排队、可追踪的资源调度过程 | 左侧场景图，右侧 3 张卡片：任务、资源、调度 | `docs/ppt_materials.md` 背景段；`sample_resources.json` |
| 3 | 项目目标与实现范围 | 构建可运行的 AIMCP 智能调度仿真闭环；明确不是实物硬件控制系统 | 中心闭环图 + 六个目标模块卡片 | `AIChemMCP-main/README.md` 的 What This Prototype Can Show / Current Completion |
| 4 | 需求分析与边界 | 功能、非功能、演示、工程实践四类需求；边界是模拟工作站和机器人 | 四象限需求矩阵 | `README.md`、`AIChemMCP-main/README.md`、`docs/ppt_materials.md` |
| 5 | 系统总体架构 | Agent / Action Server / Tools / SchedulingRuntime / Scheduler / Models 分层 | 横向分层架构图，接口层与调度层分色 | `agent.py`、`servers/action_server.py`、`tools/action_server_tools.py`、`scheduling/` |
| 6 | 核心调用链闭环 | 用户或 Agent 调用工具，Action Server 路由，Runtime 提交任务，Scheduler 生成命令，状态返回 | 6 步箭头流程图 + 文件名标注 | `servers/action_server.py`、`tools/action_server_tools.py`、`scheduling/runtime.py` |
| 7 | 工程目录结构 | 当前可运行原型集中在 `AIChemMCP-main/`，形成入口、核心模块、示例、测试、输出闭环 | 目录树截图/仿代码树 + 右侧说明标签 | 根目录、`AIChemMCP-main/` 目录结构 |
| 8 | 数据模型设计 | `Task`、`Resource`、`Workstation`、`Robot`、`Tool`，状态枚举支撑调度可观测 | UML 风格实体关系卡片 + 状态条 | `scheduling/models.py` |
| 9 | 任务与资源状态流转 | 任务 WAITING/RUNNING/COMPLETED/ERROR，资源 IDLE/BUSY/RESERVED/TRANSPORTING 等 | 状态机图 + 小型资源状态表 | `scheduling/models.py`、`scheduling/runtime.py` |
| 10 | 调度流程设计 | 时间线预留、安全缓冲、机器人转运、无缝步骤前瞻检查、FCFS/SPT 入口 | 主流程图 + 关键方法 callout | `scheduling/scheduler.py`、`scheduling/runtime.py` |
| 11 | Action Server 工具接口 | 暴露 6 个工具：3 个任务提交工具 + 3 个调度控制工具 | 六宫格接口卡片，按“任务类/控制类”分组 | `servers/action_server.py`、`tools/action_server_tools.py` |
| 12 | 示例任务与模拟资源 | 3 个模拟工作站、2 个模拟机器人；3 个单步任务 + 1 个三步 workflow | 资源地图 + 任务列表卡片 | `examples/sample_resources.json`、`sample_tasks.json`、`sample_workflow.json` |
| 13 | Demo 演示流程 / 调度闭环 | demo 提交 4 个任务，推进时间，最终全部完成；最终仿真时间 152 | 时间线 + 运行截图 + `all_completed` 结果卡 | `demo.py`、`outputs/demo_result.json`、`python demo.py` 终端输出 |
| 14 | 关键功能实现亮点 | 任务抽象、资源映射、状态快照、执行历史、资源使用统计、结构化输出 | 5-6 张功能卡片，配文件路径标签 | `scheduling/runtime.py`、`scheduling/scheduler.py`、`outputs/demo_result.json` |
| 15 | 异常处理与工程健壮性 | 输入校验、未知工具拒绝、结构化错误返回、max_steps 限制 | 错误路径流程图 + `INVALID_INPUT` 示例卡 | `tools/action_server_tools.py`、`scheduling/runtime.py`、`tests/test_scheduling_runtime.py` |
| 16 | 测试验证 | 当前 `python run_tests.py` 跑通 8 个 unittest，覆盖模型、调度、运行时、工具错误、demo smoke | 测试结果截图 + 覆盖范围矩阵 | `tests/test_scheduling_runtime.py`、当前测试终端输出 |
| 17 | 工程化实践总结 | 模块化、分层、接口封装、可复现 demo、结果归档、测试验证 | “工程实践六要素”卡片布局 | `AIChemMCP-main/README.md`、项目目录、测试和输出 |
| 18 | 项目成果 | 已完成可运行仿真原型、Action Server 接口、调度运行时、demo 输出和测试；区分后续扩展 | 左列“已完成”实色卡，右列“后续扩展”虚线卡 | `outputs/demo_result.json`、`run_tests.py` 输出、README |
| 19 | 项目难点与解决方案 | 抽象实验任务、解耦 Agent 与调度器、无硬件条件下闭环演示、多资源冲突、可测试性 | 难点 -> 方案 -> 文件 三段式对照表 | `scheduling/`、`servers/`、`tools/`、`tests/` |
| 20 | 不足与展望 | 当前是 simulation 原型；真实硬件协议、ACK、异常恢复、复杂依赖、可视化界面为后续方向 | 当前边界 + 未来路线图 | `README.md` Future Extensions、`AIChemMCP-main/README.md` Future Extensions |
| 21 | 总结 | 完成从 AIMCP 工具调用到调度仿真执行的工程化闭环，为后续真实实验室调度系统预留结构 | 闭环总结图 + 4 个结论短句 | 架构图、demo 完成结果、测试 OK 结果 |

## 3. 需要截图的页面

| 截图内容 | 推荐页码 | 用途 | 推荐裁剪范围 |
|---|---:|---|---|
| 项目目录结构 | 7 | 展示工程目录组织 | 根目录 + `AIChemMCP-main/` 展开到一级或二级 |
| `AIChemMCP-main/README.md` | 3 / 18 | 展示原型能力、Quick Start、Current Completion | What This Prototype Can Show、Current Completion |
| `python demo.py` 终端输出 | 13 | 展示 demo 可运行 | 标题、任务表、最终 `All completed: True` |
| `AIChemMCP-main/outputs/demo_result.json` | 13 / 18 / 21 | 展示结构化输出和最终状态 | `demo_mode`、`scheduling_process_summary`、`final_task_status`、`all_completed` |
| `python run_tests.py` 终端输出 | 16 | 展示测试通过 | 8 个测试 `ok` 和最终 `OK` |
| `scheduling/models.py` | 8 / 9 | 展示任务、资源、状态模型 | `TaskStatus`、`ResourceStatus`、`Task`、`Resource` |
| `scheduling/scheduler.py` | 10 / 14 | 展示调度器逻辑 | `_reserve_step()`、`_plan_regular_transfers()`、`schedule()` |
| `scheduling/runtime.py` | 10 / 15 | 展示运行时封装和校验 | `submit_task()`、`advance_time()`、`run_until_all_complete()`、校验函数 |
| `servers/action_server.py` | 11 | 展示真实暴露的 6 个工具接口 | `AVAILABLE_TOOLS_ACTION` 和 capability 列表 |
| `tools/action_server_tools.py` | 11 / 15 | 展示工具封装和结构化错误 | `_safe_call()`、`_error_response()`、六个工具方法 |
| `examples/sample_resources.json` | 12 | 展示模拟资源配置 | 三个 workstations、两个 robots |
| `examples/sample_workflow.json` | 12 / 13 | 展示三步 workflow | `workflow_tools`、`processing_times`、`seamless_steps` |
| `tests/test_scheduling_runtime.py` | 16 | 展示测试覆盖范围 | 测试类名和关键断言 |

## 4. 适合使用 AI 生成背景图的页面

- **第 1 页 封面：**自动化化学实验室 + 数字调度界面 + 蓝青色科技光效。注意画面是“抽象/概念背景”，不要表现为真实已接入本项目硬件。
- **第 2 页 项目背景：**AI Agent、实验任务、模拟设备资源之间的概念连接图，可用轻量科技插画。
- **第 20 页 不足与展望：**未来自动化实验室路线图背景，强调后续方向，不暗示已完成。
- **第 21 页 总结：**抽象闭环网络背景，叠加 Agent -> Action Server -> Runtime -> Scheduler -> Output 闭环。

## 5. 适合流程图 / 架构图 / 卡片布局的页面

### 流程图 / 架构图

- 第 5 页：系统总体架构图。
- 第 6 页：核心调用链流程图。
- 第 9 页：任务与资源状态机。
- 第 10 页：调度流程图。
- 第 13 页：Demo 演示时间线。
- 第 15 页：异常处理流程图。
- 第 20 页：未来扩展路线图。
- 第 21 页：闭环总结图。

### 卡片布局

- 第 3 页：项目目标模块卡片。
- 第 4 页：需求分析四象限。
- 第 11 页：六个 Action Server 工具卡片。
- 第 12 页：模拟资源与任务卡片。
- 第 14 页：关键功能实现亮点卡片。
- 第 17 页：工程化实践六要素卡片。
- 第 18 页：已完成 / 后续扩展双栏卡片。
- 第 19 页：难点与解决方案对照卡片。

## 6. 样张建议

本轮样张建议只做以下 3 页，不生成完整 PPT：

1. **封面**：验证整体科技感、标题层次和背景图气质。
2. **系统总体架构**：验证正式工程汇报的图形密度、分层架构表达和中文标签可读性。
3. **Demo 演示流程 / 调度闭环**：验证真实 demo 数据、时间线、结果卡片和运行截图的结合方式。

样张命名建议：

- `docs/ppt/sample_preview.pptx`
- `docs/ppt/sample_images/slide_01.png`
- `docs/ppt/sample_images/slide_05.png`
- `docs/ppt/sample_images/slide_13.png`
- `docs/ppt/sample_speech.md`

## 7. 需要确认的问题

- 是否确认总页数采用 **21 页**？
- 是否确认整体风格采用“清爽专业 + 蓝青科技 + 工程系统展示风”？
- 是否确认样张优先生成第 1、5、13 页？
- 样张中的封面是否需要补充真实小组成员、指导老师、课程名称和日期？
- 第 13 页是否使用终端输出截图作为严格素材，还是先用结构化结果卡片模拟，待最终版再替换截图？

