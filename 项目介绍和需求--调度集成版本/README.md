# AIChemMCP 智能调度原型系统

本仓库保存工程实践结题使用的 AIChemMCP 调度集成版本。当前项目更准确的定位是：面向自动化实验室场景的机器人任务调度仿真原型系统。

项目重点不是接入真实实验室硬件，而是完成一个可运行、可验证、可展示的软件原型：从 Action Server 工具调用出发，将示例任务提交到调度运行时，由调度器完成模拟资源分配和时间推进，最终输出 `demo_result.json` 并通过本地测试验证。

## 目录总览

```text
.
├─ AIChemMCP-main/                 # 当前主要开发与演示目录
│  ├─ scheduling/                  # 调度模型、调度器、运行时
│  ├─ servers/                     # Action Server 等服务入口
│  ├─ tools/                       # server 调用的工具封装
│  ├─ examples/                    # demo 输入数据
│  ├─ outputs/                     # demo 输出结果
│  ├─ tests/                       # 本地测试
│  ├─ demo.py                      # 一键 demo
│  ├─ run_tests.py                 # 一键测试
│  └─ README.md                    # 主项目 README
├─ docs/                           # PPT、汇报材料和生成产物
│  ├─ ppt_materials.md             # PPT 内容材料
│  └─ ppt/                         # 大纲、样张、最终 PPT 和辅助图
├─ documents/                      # 原始过程文档和报告材料
├─ IntelligentScheduling-main/     # 调度算法参考代码目录
└─ README.md                       # 当前总览文件
```

## 主项目入口

主要代码位于：

```text
AIChemMCP-main/
```

更详细的模块说明见：

```text
AIChemMCP-main/README.md
```

## 核心模块职责

- `scheduling/models.py`：定义任务、资源、工具、工作站、机器人及状态枚举。
- `scheduling/scheduler.py`：负责资源预留、工作站时间线、机器人转运和调度命令生成。
- `scheduling/runtime.py`：维护调度运行时状态，提供任务提交、状态查询、时间推进和运行到完成等能力。
- `servers/action_server.py`：提供 Action Server 风格的 JSON-RPC 工具路由。
- `tools/action_server_tools.py`：将工具调用适配为 `SchedulingRuntime` 方法调用，并返回结构化结果。
- `examples/`：保存模拟资源、示例任务和示例 workflow。
- `outputs/`：保存 demo 输出结果，当前核心输出为 `demo_result.json`。
- `tests/`：保存本地单元测试和 demo smoke test。
- `docs/ppt/final/`：保存结题汇报 PPT、讲稿、预览图和项目结构图。

## 快速运行

进入主项目目录：

```powershell
cd AIChemMCP-main
```

运行 demo：

```powershell
python demo.py
```

运行测试：

```powershell
python run_tests.py
```

## 真实性边界

当前系统是 simulation / mock hardware 原型：

- 未接入真实机械臂。
- 未接入真实仪器。
- 未完成真实实验执行。
- reaction / measurement / characterization / hplc_tool 仅作为示例 workflow 中的任务类型和工具名称。
- 后续可扩展真实硬件协议、异常恢复、安全联锁、复杂依赖调度和可视化监控。

