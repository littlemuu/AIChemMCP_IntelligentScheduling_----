import json
import unittest
from pathlib import Path

from scheduling.models import Robot, Task, TaskStatus, Tool, Workstation
from scheduling.runtime import SchedulingRuntime
from scheduling.scheduler import Scheduler
from tools.action_server_tools import ActionServerTools


class TaskModelTests(unittest.TestCase):
    def test_task_model_creation(self):
        task = Task(
            id="TASK-TEST",
            workflow_tools=["reaction_tool"],
            processing_times={"reaction_tool": 5},
        )

        self.assertEqual(task.status, TaskStatus.WAITING)
        self.assertEqual(task.total_steps, 1)
        self.assertTrue(task.is_last_step())

    def test_task_requires_workflow(self):
        with self.assertRaises(ValueError):
            Task(id="BAD", processing_times={})


class SchedulerTests(unittest.TestCase):
    def test_scheduler_basic_reservation(self):
        workstations = {
            "WS_REACTOR_A": Workstation(id="WS_REACTOR_A", tools=[Tool(id="reaction_tool")])
        }
        robots = {"RB_1": Robot(id="RB_1")}
        scheduler = Scheduler(
            workstations,
            robots,
            tool_to_workstation_map={"reaction_tool": "WS_REACTOR_A"},
        )
        task = Task(
            id="TASK-1",
            workflow_tools=["reaction_tool"],
            processing_times={"reaction_tool": 10},
        )

        scheduler.add_task(task)
        commands = scheduler.schedule(current_time=0)

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["target_resource"], "WS_REACTOR_A")
        self.assertEqual(workstations["WS_REACTOR_A"].timeline[0][0], "TASK-1")


class RuntimeTests(unittest.TestCase):
    def test_runtime_submit_status_and_completion(self):
        runtime = SchedulingRuntime()
        submit_result = runtime.submit_reaction(
            recipe={"name": "demo", "estimated_duration": 10},
            vessel_id="VIAL-1",
        )

        self.assertTrue(submit_result["accepted"])
        self.assertEqual(submit_result["task"]["status"], "RUNNING")

        status = runtime.get_runtime_status()
        self.assertEqual(len(status["tasks"]), 1)

        run_result = runtime.run_until_all_complete(max_steps=100)
        self.assertTrue(run_result["all_completed"])
        final_status = run_result["runtime_status"]
        self.assertEqual(final_status["tasks"]["TASK-0001"]["status"], "COMPLETED")

    def test_runtime_advance_time(self):
        runtime = SchedulingRuntime()
        runtime.submit_measurement(sample_id="SAMPLE-1", measurement_type="yield")

        result = runtime.advance_time(steps=5)

        self.assertTrue(result["ok"])
        self.assertEqual(result["advanced_steps"], 5)
        self.assertEqual(result["current_time"], 6)

    def test_runtime_invalid_input(self):
        runtime = SchedulingRuntime()

        with self.assertRaises(ValueError):
            runtime.submit_measurement(sample_id="", measurement_type="yield")

        with self.assertRaises(ValueError):
            runtime.advance_time(steps=0)

    def test_action_tools_return_structured_error(self):
        tools = ActionServerTools()
        result = tools.tool_robotic_measurement(sample_id="", measurement_type="yield")

        self.assertFalse(result["ok"])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "INVALID_INPUT")


class DemoSmokeTests(unittest.TestCase):
    def test_demo_generates_result_file(self):
        import demo

        result = demo.run_demo(verbose=False, write_output=True)
        output_path = Path(demo.DEMO_RESULT_PATH)

        self.assertTrue(result["all_completed"])
        self.assertTrue(output_path.exists())

        with output_path.open("r", encoding="utf-8") as file:
            saved = json.load(file)
        self.assertTrue(saved["all_completed"])
        self.assertIn("resource_usage", saved)


if __name__ == "__main__":
    unittest.main()
