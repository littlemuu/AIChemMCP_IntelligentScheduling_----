# AIChemMCP Scheduling Prototype

This directory contains the runnable scheduling-integration prototype for the
AIChemMCP engineering practice project. It connects the existing AIMCP action
layer with a small scheduling runtime for a simulated automated chemistry lab.

## What This Prototype Can Show

- Submit mock reaction, measurement, and characterization tasks.
- Allocate tasks to workstations and simulated robot resources.
- Advance a simulation clock and observe task status changes.
- Run until all known tasks complete.
- Export a structured demo result to `outputs/demo_result.json`.
- Exercise the Action Server tool names used by the AIMCP layer:
  `robotic_reaction`, `robotic_measurement`, `robotic_characterization`,
  `scheduler_status`, `scheduler_advance`, and
  `scheduler_run_until_complete`.

This prototype does not connect to real lab hardware. All workstation and robot
activity is simulated.

## Directory Layout

```text
AIChemMCP-main/
  agent.py                     Existing AIMCP demo agent
  demo.py                      One-command scheduling demo
  run_tests.py                 Standard-library test runner
  examples/                    Sample tasks, resources, and workflow data
  outputs/                     Generated demo output
  scheduling/                  Task/resource models, scheduler, runtime
  servers/                     MCP-style server entrypoints
  tools/                       Tool wrappers used by servers
  tests/                       Basic unit and smoke tests
```

## Quick Start

Run the scheduling demo:

```powershell
python demo.py
```

The demo prints a compact console trace suitable for screenshots and writes:

```text
outputs/demo_result.json
```

Run the tests:

```powershell
python run_tests.py
```

If `pytest` is already installed, the same tests can also be run with:

```powershell
pytest
```

## Current Completion

- A scheduling runtime is available under `scheduling/`.
- The Action Server can submit tasks and query or advance the scheduler.
- The demo uses mock resources and example data under `examples/`.
- Basic tests cover task creation, scheduler reservation, runtime operations,
  invalid input handling, and demo output generation.

## Future Extensions

- Connect simulated commands to real hardware or a hardware simulator.
- Add real device acknowledgements and recovery behavior.
- Add richer multi-step workflow dependency handling.
- Integrate LLM planning decisions with scheduler feedback.
- Persist run history to a database for long-running experiments.
