"""Runtime wrapper that keeps scheduler state alive inside the Action server."""

from __future__ import annotations

from itertools import count
from typing import Dict, List, Optional

from .models import ResourceStatus, Robot, Task, TaskStatus, Tool, Workstation
from .scheduler import Scheduler


class SchedulingRuntime:
    """Stateful runtime that translates Action requests into scheduled tasks."""

    def __init__(self):
        self.current_time = 0
        self._task_counter = count(1)
        self._sample_counter = count(1)
        self.workstations, self.robots, self.tool_to_workstation_map = self._setup_lab()
        self.scheduler = Scheduler(
            self.workstations,
            self.robots,
            tool_to_workstation_map=self.tool_to_workstation_map,
            safety_buffer_factor=0.1,
        )

    def _setup_lab(self):
        workstations = {
            "WS_REACTOR_A": Workstation(id="WS_REACTOR_A", tools=[Tool(id="reaction_tool")]),
            "WS_MEASURE_A": Workstation(
                id="WS_MEASURE_A",
                tools=[Tool(id="yield_measurement_tool"), Tool(id="ph_measurement_tool")],
            ),
            "WS_CHAR_A": Workstation(
                id="WS_CHAR_A",
                tools=[Tool(id="hplc_tool"), Tool(id="nmr_tool"), Tool(id="characterization_tool")],
            ),
        }
        robots = {
            "RB_1": Robot(id="RB_1"),
            "RB_2": Robot(id="RB_2"),
        }
        tool_to_workstation_map = {
            tool.id: workstation.id
            for workstation in workstations.values()
            for tool in workstation.tools
        }
        return workstations, robots, tool_to_workstation_map

    def _new_task_id(self) -> str:
        return f"TASK-{next(self._task_counter):04d}"

    def _new_sample_id(self) -> str:
        return f"SAMPLE-{next(self._sample_counter):04d}"

    def _update_resource_states(self):
        workstations = self.scheduler.workstations
        robots = self.scheduler.robots
        current_time = self.current_time

        for workstation in workstations.values():
            if not workstation.timeline:
                continue

            active_segment = None
            for task_id, start_time, end_time in workstation.timeline:
                if start_time <= current_time < end_time:
                    active_segment = (task_id, start_time, end_time)
                    break

            if active_segment is not None:
                task_id, start_time, _ = active_segment
                processing_end = self.scheduler.processing_end_times[(workstation.id, task_id, start_time)]
                task = self.scheduler.tasks[task_id]
                if current_time < processing_end:
                    workstation.status = ResourceStatus.BUSY
                    workstation.current_task_id = task_id
                    task.status = TaskStatus.RUNNING
                elif workstation.current_task_id == task_id:
                    workstation.status = ResourceStatus.COMPLETED_WAITING_FOR_PICKUP
            elif workstation.current_task_id is not None and workstation.status == ResourceStatus.BUSY:
                task = self.scheduler.tasks[workstation.current_task_id]
                if task.is_last_step():
                    workstation.status = ResourceStatus.IDLE
                    workstation.current_task_id = None
                    task.status = TaskStatus.COMPLETED

        for robot in robots.values():
            was_transporting = robot.status == ResourceStatus.TRANSPORTING and robot.current_task_id is not None
            previous_task_id = robot.current_task_id if was_transporting else None

            active_segment = None
            next_segment = None
            for task_id, pickup_time, drop_time in robot.timeline:
                if pickup_time <= current_time < drop_time:
                    active_segment = (task_id, pickup_time, drop_time)
                    break
                if current_time < pickup_time:
                    next_segment = (task_id, pickup_time, drop_time)
                    break

            if active_segment is not None:
                task_id, pickup_time, _ = active_segment
                pickup_finish_time = pickup_time + self.scheduler.robot_pickup_duration
                if current_time < pickup_finish_time:
                    robot.status = ResourceStatus.MOVING_TO_PICKUP
                    robot.current_task_id = task_id
                else:
                    robot.status = ResourceStatus.TRANSPORTING
                    robot.current_task_id = task_id
                    task = self.scheduler.tasks[task_id]
                    completed_ws_id = self.scheduler._resolve_workstation_for_step(task, task.current_step)
                    source_workstation = workstations[completed_ws_id]
                    if source_workstation.current_task_id == task_id:
                        source_workstation.status = ResourceStatus.IDLE
                        source_workstation.current_task_id = None
            elif next_segment is not None:
                task_id, _, _ = next_segment
                robot.status = ResourceStatus.RESERVED
                robot.current_task_id = task_id
            else:
                if was_transporting and previous_task_id is not None:
                    finished_task = self.scheduler.tasks[previous_task_id]
                    finished_task.current_step += 1
                    if finished_task.current_step >= finished_task.total_steps:
                        finished_task.status = TaskStatus.COMPLETED
                    else:
                        if finished_task.next_step_scheduled:
                            finished_task.status = TaskStatus.RUNNING
                        else:
                            finished_task.status = TaskStatus.WAITING
                            if finished_task not in self.scheduler.task_queue:
                                self.scheduler.task_queue.append(finished_task)
                    finished_task.next_step_scheduled = False

                robot.status = ResourceStatus.IDLE
                robot.current_task_id = None

    def _execute_commands(self, commands: List[dict]):
        for command in commands:
            if command["action"] != "START_PROCESSING":
                continue
            task = self.scheduler.tasks[command["params"]["task_id"]]
            workstation = self.scheduler.workstations[command["target_resource"]]
            workstation.status = ResourceStatus.BUSY
            workstation.current_task_id = task.id
            task.status = TaskStatus.RUNNING

    def _summarize_commands(self, commands: List[dict]) -> List[dict]:
        return [
            {
                "command_id": command["command_id"],
                "action": command["action"],
                "target_resource": command["target_resource"],
                "task_id": command["params"]["task_id"],
                "step_index": command["params"]["step_index"],
                "tool_id": command["params"]["tool_id"],
            }
            for command in commands
        ]

    def _task_snapshot(self, task: Task) -> Dict[str, object]:
        return {
            "task_id": task.id,
            "sample_id": task.sample_id,
            "status": task.status.name,
            "current_step": task.current_step,
            "total_steps": task.total_steps,
            "workflow_tools": task.workflow_tools,
            "metadata": task.metadata,
        }

    def _collect_completion_events(self, previous_statuses: Dict[str, str]) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        for task_id, task in self.scheduler.tasks.items():
            previous_status = previous_statuses.get(task_id)
            if previous_status != TaskStatus.COMPLETED.name and task.status == TaskStatus.COMPLETED:
                events.append(
                    {
                        "event": "TASK_COMPLETED",
                        "task_id": task.id,
                        "sample_id": task.sample_id,
                        "completed_at": self.current_time,
                    }
                )
        return events

    def submit_task(
        self,
        *,
        workflow_tools: List[str],
        processing_times: Dict[str, int],
        seamless_steps: Optional[List[tuple]] = None,
        sample_id: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        task = Task(
            id=self._new_task_id(),
            sample_id=sample_id or self._new_sample_id(),
            workflow_tools=workflow_tools,
            processing_times=processing_times,
            seamless_steps=seamless_steps or [],
            metadata=metadata or {},
        )
        self.scheduler.add_task(task)
        commands = self.tick(steps=1)
        return {
            "accepted": True,
            "task": self._task_snapshot(task),
            "scheduled_commands": self._summarize_commands(commands),
            "current_time": self.current_time,
        }

    def tick(self, steps: int = 1) -> List[dict]:
        executed_commands: List[dict] = []
        for _ in range(steps):
            self._update_resource_states()
            commands = self.scheduler.schedule(self.current_time)
            if commands:
                self._execute_commands(commands)
                executed_commands.extend(commands)
            self.current_time += 1
        return executed_commands

    def advance_time(self, steps: int = 1) -> Dict[str, object]:
        if steps < 1:
            raise ValueError("steps must be at least 1.")

        previous_statuses = {
            task_id: task.status.name
            for task_id, task in self.scheduler.tasks.items()
        }
        commands = self.tick(steps=steps)
        return {
            "advanced_steps": steps,
            "current_time": self.current_time,
            "scheduled_commands": self._summarize_commands(commands),
            "completion_events": self._collect_completion_events(previous_statuses),
            "runtime_status": self.get_runtime_status(),
        }

    def run_until_all_complete(self, max_steps: int = 1000) -> Dict[str, object]:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1.")

        all_commands: List[dict] = []
        completion_events: List[Dict[str, object]] = []
        steps_run = 0

        while steps_run < max_steps:
            if self.scheduler.tasks and all(task.status == TaskStatus.COMPLETED for task in self.scheduler.tasks.values()):
                break

            previous_statuses = {
                task_id: task.status.name
                for task_id, task in self.scheduler.tasks.items()
            }
            commands = self.tick(steps=1)
            all_commands.extend(commands)
            completion_events.extend(self._collect_completion_events(previous_statuses))
            steps_run += 1

            if self.scheduler.tasks and all(task.status == TaskStatus.COMPLETED for task in self.scheduler.tasks.values()):
                break

        return {
            "steps_run": steps_run,
            "current_time": self.current_time,
            "all_completed": bool(self.scheduler.tasks)
            and all(task.status == TaskStatus.COMPLETED for task in self.scheduler.tasks.values()),
            "scheduled_commands": self._summarize_commands(all_commands),
            "completion_events": completion_events,
            "runtime_status": self.get_runtime_status(),
        }

    def submit_reaction(self, recipe: Dict[str, object], vessel_id: str) -> Dict[str, object]:
        workflow_tools = ["reaction_tool"]
        processing_times = {"reaction_tool": int(recipe.get("estimated_duration", 300))}
        metadata = {"task_type": "reaction", "recipe": recipe, "vessel_id": vessel_id}
        return self.submit_task(
            workflow_tools=workflow_tools,
            processing_times=processing_times,
            metadata=metadata,
        )

    def submit_measurement(self, sample_id: str, measurement_type: str) -> Dict[str, object]:
        tool_id = {
            "yield": "yield_measurement_tool",
            "ph": "ph_measurement_tool",
        }.get(measurement_type, "yield_measurement_tool")
        processing_times = {tool_id: 60}
        metadata = {"task_type": "measurement", "measurement_type": measurement_type}
        return self.submit_task(
            workflow_tools=[tool_id],
            processing_times=processing_times,
            sample_id=sample_id,
            metadata=metadata,
        )

    def submit_characterization(self, sample_id: str, analysis_method: str) -> Dict[str, object]:
        tool_id = {
            "HPLC": "hplc_tool",
            "NMR": "nmr_tool",
        }.get(analysis_method.upper(), "characterization_tool")
        processing_times = {tool_id: 120}
        metadata = {"task_type": "characterization", "analysis_method": analysis_method}
        return self.submit_task(
            workflow_tools=[tool_id],
            processing_times=processing_times,
            sample_id=sample_id,
            metadata=metadata,
        )

    def get_runtime_status(self) -> Dict[str, object]:
        return {
            "current_time": self.current_time,
            "queued_tasks": [task.id for task in self.scheduler.task_queue],
            "tasks": {
                task_id: self._task_snapshot(task)
                for task_id, task in self.scheduler.tasks.items()
            },
            "workstations": {
                ws_id: {
                    "status": workstation.status.name,
                    "current_task_id": workstation.current_task_id,
                }
                for ws_id, workstation in self.scheduler.workstations.items()
            },
            "robots": {
                robot_id: {
                    "status": robot.status.name,
                    "current_task_id": robot.current_task_id,
                }
                for robot_id, robot in self.scheduler.robots.items()
            },
        }
