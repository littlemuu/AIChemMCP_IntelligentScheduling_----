"""Scheduling engine with lookahead reservation for workstations and robots."""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from models import ResourceStatus, Robot, Task, TaskStatus, Workstation


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
        # processing_end_times 专门记录“某一步加工真正结束的时刻”。
        # 之所以单独保存，是因为工作站在普通步骤里经常会出现一种情况：
        # 加工虽然结束了，但样品还没被机器人取走，因此工作站仍然被占住。
        # 这意味着“加工结束时刻”和“工作站释放时刻”可能并不相同。
        # 如果不把这两个概念拆开，状态推进阶段就会误判任务是否已经完成处理。
        self.processing_end_times: Dict[Tuple[str, str, int], int] = {}

    def log(self, time: int, message: str):
        log_message = f"[Time {time:04d}] {message}"
        self.log_messages.append(log_message)
        print(log_message)

    def add_task(self, task: Task):
        self.task_queue.append(task)
        self.tasks[task.id] = task

    def get_buffered_duration(self, base_duration: int) -> int:
        return max(1, int(base_duration * (1 + self.SAFETY_BUFFER_FACTOR)))

    def _resolve_workstation_for_step(self, task: Task, step_index: int) -> str:
        # 这个函数负责把“任务的某一步”解析到具体工作站。
        # 如果任务本身已经明确写了 workflow，就直接使用其中的工作站 ID；
        # 如果任务只写了 workflow_tools，则说明任务只描述了能力需求，
        # 此时需要依赖 tool_to_workstation_map 把工具映射到真实设备。
        # 这一步是调度器从“工艺步骤”落到“物理资源”的关键桥梁。
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
        # 这个判断用于区分“普通步骤”和“无缝衔接步骤”。
        # 对普通步骤而言，即使加工已经结束，样品依然停留在当前工作站上，
        # 所以工作站在机器人真正把样品取走之前都不能接下一个任务。
        # 对无缝步骤而言，机器人会按计划准时接手，因此不需要额外增加等待占位时间。
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
        # 这里负责把某一步任务正式写入工作站时间线。
        # 注意写入的不是单纯的“加工时间”，而是“工作站被该任务占用的完整时间”。
        # 对普通步骤来说，占用时间 = 加工时间 + 机器人取样时间；
        # 对无缝步骤来说，占用时间通常只需要覆盖加工本身，因为机器人会按时接走样品。
        # 同时，这里还会把加工结束时刻单独记下来，供状态机后续使用。
        occupancy_end = start_time + processing_duration
        if self._step_requires_pickup_hold(task, step_index):
            occupancy_end += self.robot_pickup_duration
        workstation.timeline.append((task.id, start_time, occupancy_end))
        self.processing_end_times[(workstation.id, task.id, start_time)] = start_time + processing_duration

    def _pick_task_for_candidates(self, candidates: List[Task]) -> List[Task]:
        # 这里是任务优先级策略的统一入口。
        # 当前为了让框架保持清晰，只实现了两类简单策略：
        # FCFS：保持原队列顺序；
        # SPT：优先安排当前步骤处理时间更短的任务。
        # 如果后续要加入任务等级、紧急程度或全局优化逻辑，也适合继续放在这里扩展。
        if self.priority_policy == "SPT":
            return sorted(candidates, key=lambda task: self._resolve_processing_duration(task, task.current_step))
        return candidates

    def _find_robot_and_pickup_time(
        self,
        earliest_pickup_time: int,
        transport_duration: int,
    ) -> Tuple[Optional[Robot], Optional[int]]:
        # 机器人选择不是简单看“当前有没有空闲机器人”，
        # 而是要看“谁能够在要求的最早时刻之后尽快接手这个运输任务”。
        # 因此这里会扫描所有机器人现有时间线，计算它们各自最早的可接手时间，
        # 再选择 pickup_time 最靠前且时间窗不冲突的那一个。
        # 这种做法更符合事件驱动调度中的前瞻预留思想。
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
        # 这个函数专门处理“普通步骤做完了，但下一步还没衔接上”的任务。
        # 它会扫描所有处于 COMPLETED_WAITING_FOR_PICKUP 的工作站，
        # 尝试为这些任务一次性预留：
        # 1. 一个可接手的机器人；
        # 2. 下一工作站上的处理时间窗。
        # 如果两者都能对齐，就说明当前任务的后续转运是可行的。
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
        # 这是工作站调度的核心函数。
        # 它负责回答一个问题：
        # “当前这个空闲工作站，能不能在 current_time 接下这个任务的当前步骤？”
        # 对普通步骤，只需要检查当前工作站时间窗是否可用；
        # 对无缝步骤，则必须向后多看一步，把机器人和下一工作站一起检查。
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
            # 无缝衔接步骤的关键点在于：
            # 当前工作站完成后，样品不能停留等待，必须立即由机器人接手，
            # 并且下一工作站在样品到达时必须已经空出来。
            # 所以这里不是只给当前站排一个加工时间，而是要同时锁定：
            # 当前站、机器人、下一站，这三个时间窗只要有一个不成立，整个方案都作废。
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
            # 对普通步骤，当前只需要保证这一步能够正常开始加工。
            # 后续是否能马上转运，不在这里立即强求，
            # 而是在任务真正完成当前步骤后，由 _plan_regular_transfers 再做后续预留。
            # 这样能让普通步骤和无缝步骤共存，又保持逻辑分层清晰。
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
        # 调度入口分成两个阶段：
        # 第一阶段，优先处理那些已经做完前一步、正在等待被接走的任务；
        # 第二阶段，再考虑是否让空闲工作站接收新的加工任务。
        # 这样的顺序更符合真实实验室场景，因为被样品占住的工作站往往更紧急。
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
