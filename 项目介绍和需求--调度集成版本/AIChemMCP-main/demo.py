"""One-command simulation demo for the AIMCP scheduling prototype."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

from scheduling import SchedulingRuntime


PROJECT_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = PROJECT_DIR / "examples"
OUTPUTS_DIR = PROJECT_DIR / "outputs"
DEMO_RESULT_PATH = OUTPUTS_DIR / "demo_result.json"


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def print_section(title: str, verbose: bool = True) -> None:
    if verbose:
        print()
        print("=" * 72)
        print(title)
        print("=" * 72)


def print_task_table(status: Dict[str, object], verbose: bool = True) -> None:
    if not verbose:
        return
    tasks = status["tasks"]
    if not tasks:
        print("No tasks have been submitted.")
        return

    print(f"{'Task':<12} {'Sample':<16} {'Status':<12} {'Step':<8} {'Tools'}")
    print("-" * 72)
    for task_id, task in tasks.items():
        step = f"{task['current_step'] + 1}/{task['total_steps']}"
        tools = " -> ".join(task["workflow_tools"])
        print(f"{task_id:<12} {str(task['sample_id']):<16} {task['status']:<12} {step:<8} {tools}")


def print_resource_table(status: Dict[str, object], verbose: bool = True) -> None:
    if not verbose:
        return
    print(f"{'Resource':<14} {'Status':<28} {'Current task'}")
    print("-" * 72)
    for group_name in ("workstations", "robots"):
        for resource_id, resource in status[group_name].items():
            current_task = resource["current_task_id"] or "-"
            print(f"{resource_id:<14} {resource['status']:<28} {current_task}")


def submit_sample_task(runtime: SchedulingRuntime, task: Dict[str, object]) -> Dict[str, object]:
    task_type = task["task_type"]
    if task_type == "reaction":
        return runtime.submit_reaction(
            recipe=task["recipe"],
            vessel_id=task["vessel_id"],
        )
    if task_type == "measurement":
        return runtime.submit_measurement(
            sample_id=task["sample_id"],
            measurement_type=task["measurement_type"],
        )
    if task_type == "characterization":
        return runtime.submit_characterization(
            sample_id=task["sample_id"],
            analysis_method=task["analysis_method"],
        )
    raise ValueError(f"Unsupported sample task type: {task_type}")


def build_final_result(
    submitted_tasks: List[Dict[str, object]],
    process_summary: List[Dict[str, object]],
    final_run: Dict[str, object],
) -> Dict[str, object]:
    final_status = final_run["runtime_status"]
    return {
        "demo_mode": "simulation",
        "submitted_tasks": submitted_tasks,
        "scheduling_process_summary": process_summary,
        "final_task_status": final_status["tasks"],
        "simulation_time": final_status["current_time"],
        "resource_usage": final_status["resource_usage"],
        "execution_history": final_status["execution_history"],
        "all_completed": final_run["all_completed"],
    }


def run_demo(verbose: bool = True, write_output: bool = True) -> Dict[str, object]:
    resources = load_json(EXAMPLES_DIR / "sample_resources.json")
    sample_tasks = load_json(EXAMPLES_DIR / "sample_tasks.json")
    sample_workflow = load_json(EXAMPLES_DIR / "sample_workflow.json")

    runtime = SchedulingRuntime()
    submitted_tasks: List[Dict[str, object]] = []
    process_summary: List[Dict[str, object]] = []

    print_section("AIChemMCP Scheduling Prototype Demo", verbose)
    if verbose:
        print("Mode: simulation/mock hardware")
        print(f"Loaded resources: {len(resources['workstations'])} workstations, {len(resources['robots'])} robots")

    print_section("1. Submit sample tasks", verbose)
    for task in sample_tasks["tasks"]:
        result = submit_sample_task(runtime, task)
        submitted_tasks.append(
            {
                "source_id": task["id"],
                "task_type": task["task_type"],
                "runtime_task": result["task"],
            }
        )
        if verbose:
            print(f"Accepted {task['id']} -> {result['task']['task_id']} ({result['task']['status']})")

    workflow_result = runtime.submit_task(
        workflow_tools=sample_workflow["workflow_tools"],
        processing_times=sample_workflow["processing_times"],
        seamless_steps=sample_workflow["seamless_steps"],
        sample_id=sample_workflow["sample_id"],
        metadata=sample_workflow["metadata"],
    )
    submitted_tasks.append(
        {
            "source_id": sample_workflow["workflow_id"],
            "task_type": "integrated_workflow",
            "runtime_task": workflow_result["task"],
        }
    )
    if verbose:
        print(
            f"Accepted {sample_workflow['workflow_id']} -> "
            f"{workflow_result['task']['task_id']} ({workflow_result['task']['status']})"
        )

    status_after_submit = runtime.get_runtime_status()
    process_summary.append(
        {
            "stage": "after_submit",
            "time": status_after_submit["current_time"],
            "task_count": len(status_after_submit["tasks"]),
            "queued_tasks": status_after_submit["queued_tasks"],
        }
    )
    print_task_table(status_after_submit, verbose)
    print_resource_table(status_after_submit, verbose)

    print_section("2. Advance simulated time", verbose)
    advance_result = runtime.advance_time(steps=35)
    process_summary.append(
        {
            "stage": "after_advance",
            "time": advance_result["current_time"],
            "completion_events": advance_result["completion_events"],
        }
    )
    if verbose:
        print(f"Advanced steps: {advance_result['advanced_steps']}")
        print(f"Current simulation time: {advance_result['current_time']}")
        if advance_result["completion_events"]:
            print(f"New completion events: {len(advance_result['completion_events'])}")
    print_task_table(advance_result["runtime_status"], verbose)
    print_resource_table(advance_result["runtime_status"], verbose)

    print_section("3. Run until all tasks complete", verbose)
    final_run = runtime.run_until_all_complete(max_steps=500)
    process_summary.append(
        {
            "stage": "final",
            "time": final_run["current_time"],
            "steps_run": final_run["steps_run"],
            "all_completed": final_run["all_completed"],
            "completion_events": final_run["completion_events"],
        }
    )
    if verbose:
        print(f"Steps run: {final_run['steps_run']}")
        print(f"All completed: {final_run['all_completed']}")
        print(f"Final simulation time: {final_run['current_time']}")
    print_task_table(final_run["runtime_status"], verbose)
    print_resource_table(final_run["runtime_status"], verbose)

    result = build_final_result(submitted_tasks, process_summary, final_run)
    if write_output:
        OUTPUTS_DIR.mkdir(exist_ok=True)
        with DEMO_RESULT_PATH.open("w", encoding="utf-8") as file:
            json.dump(result, file, indent=2, ensure_ascii=False)
        if verbose:
            print_section("4. Output", verbose)
            print(f"Demo result saved to: {DEMO_RESULT_PATH}")

    return result


def main() -> int:
    try:
        result = run_demo(verbose=True, write_output=True)
    except Exception as exc:
        print()
        print("Demo failed.")
        print(f"Reason: {exc}")
        print("Please run from AIChemMCP-main and check examples/*.json.")
        return 1

    if not result["all_completed"]:
        print("Demo finished, but not all tasks completed within the step budget.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
