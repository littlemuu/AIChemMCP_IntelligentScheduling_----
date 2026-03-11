"""Scheduling engine with lookahead reservation for workstations and robots."""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from .models import ResourceStatus, Robot, Task, TaskStatus, Workstation


class Scheduler:
    def __init__(
        self,
        workstations: Dict[str, Workstation],
        robots: Dict[str, Robot],
        tool_to_workstation_map: Optional[Dict[str, str]] = None,
        safety_buffer_factor: float = 0.1,
        robot_pickup_duration: int = 20,
        robot_transport_duration: int = 20,
        priority_policy: str = "FCFS",
    ):
        self.workstations = workstations
        self.robots = robots
        self.tool_to_workstation_map = tool_to_workstation_map or {}
        self.task_queue: List[Task] = []
        self.tasks: Dict[str, Task] = {}
        self.SAFETY_BUFFER_FACTOR = safety_buffer_factor
        self.robot_pickup_duration = robot_pickup_duration
        self.robot_transport_duration = robot_transport_duration
        self.priority_policy = priority_policy.upper()
        self.log_messages: List[str] = []
        self.processing_end_times: Dict[Tuple[str, str, int], int] = {}

    def log(self, time: int, message: str):
        log_message = f"[Time {time:04d}] {message}"
        self.log_messages.append(log_message)

    def add_task(self, task: Task):
        self.task_queue.append(task)
        self.tasks[task.id] = task

    def get_buffered_duration(self, base_duration: int) -> int:
        return max(1, int(base_duration * (1 + self.SAFETY_BUFFER_FACTOR)))

    def _resolve_workstation_for_step(self, task: Task, step_index: int) -> str:
        if task.workflow:
            return task.workflow[step_index]
        tool_id = task.workflow_tools[step_index]
        if tool_id not in self.tool_to_workstation_map:
            raise KeyError(f"Tool {tool_id} is not mapped to any workstation.")
        return self.tool_to_workstation_map[tool_id]

    def _resolve_tool_for_step(self, task: Task, step_index: int) -> Optional[str]:
        if task.workflow_tools:
            return task.workflow_tools[step_index]
        return None

    def _resolve_processing_duration(self, task: Task, step_index: int) -> int:
        key = task.processing_key_for_step(step_index)
        return self.get_buffered_duration(task.processing_times[key])

    def _transport_total_duration(self) -> int:
        return self.robot_pickup_duration + self.robot_transport_duration

    def _step_requires_pickup_hold(self, task: Task, step_index: int) -> bool:
        if step_index >= task.total_steps - 1:
            return False
        return (step_index, step_index + 1) not in task.seamless_indices

    def _reserve_workstation_interval(
        self,
        workstation: Workstation,
        task: Task,
        step_index: int,
        start_time: int,
        processing_duration: int,
    ):
        occupancy_end = start_time + processing_duration
        if self._step_requires_pickup_hold(task, step_index):
            occupancy_end += self.robot_pickup_duration
        workstation.timeline.append((task.id, start_time, occupancy_end))
        self.processing_end_times[(workstation.id, task.id, start_time)] = start_time + processing_duration

    def _pick_task_for_candidates(self, candidates: List[Task]) -> List[Task]:
        if self.priority_policy == "SPT":
            return sorted(candidates, key=lambda task: self._resolve_processing_duration(task, task.current_step))
        return candidates

    def _find_robot_and_pickup_time(
        self,
        earliest_pickup_time: int,
        transport_duration: int,
    ) -> Tuple[Optional[Robot], Optional[int]]:
        best_robot: Optional[Robot] = None
        best_pickup: Optional[int] = None
        best_time = float("inf")

        for robot in self.robots.values():
            robot_free_time = 0
            if robot.timeline:
                robot_free_time = max(end_time for _, _, end_time in robot.timeline)
            pickup_time = max(robot_free_time, earliest_pickup_time)
            if not robot.is_available_at(pickup_time, transport_duration):
                continue
            if pickup_time < best_time:
                best_robot = robot
                best_pickup = pickup_time
                best_time = pickup_time

        return best_robot, best_pickup

    def _plan_regular_transfers(self, current_time: int):
        candidates: List[Tuple[Workstation, Task]] = []
        for workstation in self.workstations.values():
            if workstation.status != ResourceStatus.COMPLETED_WAITING_FOR_PICKUP:
                continue
            if workstation.current_task_id is None:
                continue

            task = self.tasks[workstation.current_task_id]
            if task.is_last_step():
                continue
            if (task.current_step, task.current_step + 1) in task.seamless_indices:
                continue
            candidates.append((workstation, task))

        for source_ws, task in candidates:
            next_step = task.current_step + 1
            next_ws_id = self._resolve_workstation_for_step(task, next_step)
            next_ws = self.workstations[next_ws_id]
            next_duration = self._resolve_processing_duration(task, next_step)
            transport_duration = self._transport_total_duration()

            robot, pickup_time = self._find_robot_and_pickup_time(current_time, transport_duration)
            if robot is None or pickup_time is None:
                continue

            drop_time = pickup_time + transport_duration
            if not next_ws.is_available_at(drop_time, next_duration):
                continue

            robot.timeline.append((task.id, pickup_time, drop_time))
            self._reserve_workstation_interval(next_ws, task, next_step, drop_time, next_duration)
            task.next_step_scheduled = True

            if pickup_time > current_time:
                robot.status = ResourceStatus.RESERVED
                robot.current_task_id = task.id

            self.log(
                current_time,
                "RESERVATION: "
                f"Task {task.id} [REGULAR-TRANSFER] {source_ws.id} -> {next_ws.id}, "
                f"pickup@{pickup_time}, drop@{drop_time}.",
            )

    def _reserve_step(
        self,
        task: Task,
        workstation: Workstation,
        current_time: int,
        commands: List[Dict[str, Any]],
    ) -> bool:
        step_index = task.current_step
        current_ws_id = self._resolve_workstation_for_step(task, step_index)
        current_tool_id = self._resolve_tool_for_step(task, step_index)
        current_duration = self._resolve_processing_duration(task, step_index)

        if workstation.id != current_ws_id:
            return False
        if not workstation.is_available_at(current_time, current_duration):
            return False

        is_last_step = task.is_last_step()
        needs_seamless = (not is_last_step) and ((step_index, step_index + 1) in task.seamless_indices)

        if needs_seamless:
            finish_time = current_time + current_duration
            pickup_time = max(current_time, finish_time - self.robot_pickup_duration)
            robot, pickup_time = self._find_robot_and_pickup_time(
                pickup_time,
                self._transport_total_duration(),
            )
            if robot is None or pickup_time is None:
                return False

            next_step = step_index + 1
            next_ws_id = self._resolve_workstation_for_step(task, next_step)
            next_ws = self.workstations[next_ws_id]
            next_duration = self._resolve_processing_duration(task, next_step)
            drop_time = pickup_time + self._transport_total_duration()

            if not next_ws.is_available_at(drop_time, next_duration):
                return False

            self._reserve_workstation_interval(workstation, task, step_index, current_time, current_duration)
            robot.timeline.append((task.id, pickup_time, drop_time))
            self._reserve_workstation_interval(next_ws, task, next_step, drop_time, next_duration)
            task.next_step_scheduled = True
            robot.status = ResourceStatus.RESERVED
            robot.current_task_id = task.id

            self.log(
                current_time,
                "RESERVATION: "
                f"Task {task.id} [SEAMLESS] {current_ws_id}@{workstation.id} -> {next_ws_id}, "
                f"pickup@{pickup_time}, drop@{drop_time}.",
            )
        else:
            self._reserve_workstation_interval(workstation, task, step_index, current_time, current_duration)
            self.log(
                current_time,
                f"RESERVATION: Task {task.id} [REGULAR] approved for {current_ws_id}@{workstation.id}.",
            )

        commands.append(
            {
                "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
                "target_resource": workstation.id,
                "action": "START_PROCESSING",
                "params": {
                    "task_id": task.id,
                    "workstation_id": current_ws_id,
                    "tool_id": current_tool_id,
                    "step_index": step_index,
                    "duration_estimate": current_duration,
                    "is_seamless_next": needs_seamless,
                },
            }
        )
        return True

    def schedule(self, current_time: int) -> List[Dict[str, Any]]:
        commands: List[Dict[str, Any]] = []
        self._plan_regular_transfers(current_time)

        idle_workstations = [ws for ws in self.workstations.values() if ws.status == ResourceStatus.IDLE]
        if not idle_workstations:
            return commands

        for workstation in idle_workstations:
            if workstation.status != ResourceStatus.IDLE:
                continue

            waiting_candidates = [
                task
                for task in self.task_queue
                if task.status == TaskStatus.WAITING
                and self._resolve_workstation_for_step(task, task.current_step) == workstation.id
            ]

            for task in self._pick_task_for_candidates(waiting_candidates):
                if self._reserve_step(task, workstation, current_time, commands):
                    self.task_queue.remove(task)
                    break

        return commands

