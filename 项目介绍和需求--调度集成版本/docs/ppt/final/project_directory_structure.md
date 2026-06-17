# AIChemMCP 项目目录结构图

> 面向自动化实验室场景的机器人任务调度仿真原型。图中聚焦结题汇报相关主线，省略 `__pycache__`、zip 归档和 IDE 配置等非核心展示项。

```mermaid
flowchart LR
    Root["AIChemMCP-main/<br/>核心原型工程目录<br/><small>demo.py / run_tests.py / README.md</small>"]

    subgraph Interface["接口与工具层"]
        Servers["servers/<br/><small>action_server.py</small>"]
        Tools["tools/<br/><small>action_server_tools.py</small>"]
    end

    subgraph Core["调度核心层"]
        Scheduling["scheduling/<br/><small>models.py<br/>runtime.py<br/>scheduler.py</small>"]
    end

    subgraph Data["示例数据与输出"]
        Examples["examples/<br/><small>sample_resources.json<br/>sample_tasks.json<br/>sample_workflow.json</small>"]
        Outputs["outputs/<br/><small>demo_result.json</small>"]
    end

    subgraph Test["测试与验证"]
        Tests["tests/<br/><small>test_scheduling_runtime.py</small>"]
        RunTests["run_tests.py<br/><small>本地测试入口</small>"]
    end

    subgraph Docs["汇报与文档"]
        Ppt["docs/ppt/final/<br/><small>pptx / speech.md / preview_images</small>"]
    end

    Aux["辅助目录<br/><small>static/ / software_data/<br/>dummy_planner_servers/</small>"]

    Root --> Interface
    Root --> Core
    Root --> Data
    Root --> Test
    Root -.-> Docs
    Root -.-> Aux

    Servers --> Tools
    Tools --> Scheduling
    Examples --> Scheduling
    Scheduling --> Outputs
    Scheduling --> Tests
    RunTests --> Tests

    classDef root fill:#0b2b4a,stroke:#123d63,color:#fff,stroke-width:2px;
    classDef main fill:#eef7fd,stroke:#18c4da,color:#0b1f35,stroke-width:1.5px;
    classDef core fill:#eefbfc,stroke:#1f6bff,color:#0b1f35,stroke-width:1.5px;
    classDef data fill:#f2fbf6,stroke:#27ae60,color:#0b1f35,stroke-width:1.5px;
    classDef support fill:#fff8ef,stroke:#f59240,color:#0b1f35,stroke-width:1.5px;

    class Root root;
    class Servers,Tools main;
    class Scheduling core;
    class Examples,Outputs data;
    class Tests,RunTests,Ppt,Aux support;
```

## 简洁目录树

```text
AIChemMCP-main/
├─ demo.py                         # demo 演示入口
├─ run_tests.py                    # 本地测试入口
├─ README.md                       # 项目说明
├─ servers/
│  └─ action_server.py             # 工具调用路由
├─ tools/
│  └─ action_server_tools.py       # 调度工具封装
├─ scheduling/
│  ├─ models.py                    # 任务 / 资源数据模型
│  ├─ runtime.py                   # 调度运行时
│  └─ scheduler.py                 # 资源预留与调度逻辑
├─ examples/
│  ├─ sample_resources.json        # mock 工作站与机器人资源
│  ├─ sample_tasks.json            # 示例任务
│  └─ sample_workflow.json         # 示例 workflow
├─ outputs/
│  └─ demo_result.json             # demo 运行结果归档
├─ tests/
│  └─ test_scheduling_runtime.py   # 调度与工具测试
├─ static/                         # 静态资源
├─ software_data/                  # 辅助数据目录
└─ dummy_planner_servers/          # 辅助 planner server 目录
```

## 汇报侧文件

```text
docs/ppt/final/
├─ AIChemMCP_机器人调度结题汇报_v3.pptx
├─ speech.md
├─ preview_images_v3/
├─ project_directory_drawio_style.svg
├─ project_directory_structure.drawio
└─ project_directory_structure.md
```

