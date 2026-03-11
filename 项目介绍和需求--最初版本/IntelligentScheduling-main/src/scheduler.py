import uuid
from models import Task, Workstation, Robot, ResourceStatus, TaskStatus
from typing import List, Dict, Optional, Any


class Scheduler:
    def __init__(self, workstations: Dict[str, Workstation], robots: Dict[str, Robot],
                 tool_to_workstation_map: Dict[str, str], safety_buffer_factor: float = 0.1):
        self.workstations = workstations
        self.robots = robots
        self.tool_to_workstation_map = tool_to_workstation_map
        self.task_queue: List[Task] = []
        self.tasks: Dict[str, Task] = {}
        self.SAFETY_BUFFER_FACTOR = safety_buffer_factor
        self.log_messages = []

    def log(self, time: int, message: str):
        log_message = f"[Time {time:04d}] {message}"
        self.log_messages.append(log_message)
        print(log_message)

    def add_task(self, task: Task):
        self.task_queue.append(task)
        self.tasks[task.id] = task

    def get_buffered_duration(self, base_duration: int) -> int:
        return int(base_duration * (1 + self.SAFETY_BUFFER_FACTOR))

    def _find_best_robot_for_transport(self, pickup_time: int, transport_base_duration: int) -> Optional[Robot]:
        transport_duration = self.get_buffered_duration(transport_base_duration)
        for robot in self.robots.values():
            if robot.is_available_at(pickup_time, transport_duration):
                return robot
        return None

    def _attempt_reservation_and_generate_commands(self, task: Task, ws: Workstation, current_time: int,
                                                   commands: list):
        current_tool_id = task.workflow[task.current_step]
        is_last_step = task.current_step >= len(task.workflow) - 1
        needs_continuous = not is_last_step and (task.current_step, task.current_step + 1) in task.seamless_indices

        if needs_continuous:
            next_tool_id = task.workflow[task.current_step + 1]
            next_ws_id = self.tool_to_workstation_map[next_tool_id]
            next_ws = self.workstations[next_ws_id]

            processing_duration = self.get_buffered_duration(task.processing_times[current_tool_id])
            finish_time = current_time + processing_duration

            robot = self._find_best_robot_for_transport(finish_time, 20)
            if not robot:
                return False

            transport_duration = self.get_buffered_duration(20)
            arrival_time_at_next_ws = finish_time + transport_duration
            next_processing_duration = self.get_buffered_duration(task.processing_times[next_tool_id])

            if not next_ws.is_available_at(arrival_time_at_next_ws, next_processing_duration):
                return False

            self.log(
                current_time,
                f"RESERVATION: Task {task.id} [SEAMLESS] approved for Tool:{current_tool_id}@{ws.id} -> Tool:{next_tool_id}@{next_ws_id}.")

            ws.timeline.append((task.id, current_time, finish_time))
            robot.timeline.append((task.id, finish_time, arrival_time_at_next_ws))
            next_ws.timeline.append((task.id, arrival_time_at_next_ws, arrival_time_at_next_ws + next_processing_duration))

            commands.append({
                "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
                "target_resource": ws.id,
                "action": "START_PROCESSING",
                "params": {
                    "task_id": task.id,
                    "tool_id": current_tool_id,
                    "step_index": task.current_step,
                    "duration_estimate": processing_duration,
                    "is_seamless_next": True
                }
            })
        else:
            processing_duration = self.get_buffered_duration(task.processing_times[current_tool_id])
            if not ws.is_available_at(current_time, processing_duration):
                return False

            self.log(current_time, f"RESERVATION: Task {task.id} [REGULAR] approved for Tool:{current_tool_id}@{ws.id}.")
            ws.timeline.append((task.id, current_time, current_time + processing_duration))
            commands.append({
                "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
                "target_resource": ws.id,
                "action": "START_PROCESSING",
                "params": {
                    "task_id": task.id,
                    "tool_id": current_tool_id,
                    "step_index": task.current_step,
                    "duration_estimate": processing_duration,
                    "is_seamless_next": False
                }
            })

        task.status = TaskStatus.RUNNING
        return True

    def schedule(self, current_time: int) -> List[Dict[str, Any]]:
        commands = []
        idle_workstations = [ws for ws in self.workstations.values() if ws.status == ResourceStatus.IDLE]

        if not idle_workstations:
            return commands

        for ws in idle_workstations:
            if ws.status != ResourceStatus.IDLE:
                continue

            task_to_remove_from_queue = None
            for task in self.task_queue:
                if task.status == TaskStatus.WAITING:
                    required_tool_id = task.workflow[task.current_step]
                    host_ws_id = self.tool_to_workstation_map.get(required_tool_id)

                    if host_ws_id == ws.id:
                        if self._attempt_reservation_and_generate_commands(task, ws, current_time, commands):
                            task_to_remove_from_queue = task
                            break

            if task_to_remove_from_queue:
                self.task_queue.remove(task_to_remove_from_queue)

        return commands
