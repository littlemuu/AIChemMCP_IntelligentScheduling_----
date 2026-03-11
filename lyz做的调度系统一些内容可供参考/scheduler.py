import uuid
from models import Task, Workstation, Robot, ResourceStatus, TaskStatus, Tool, Resource
from typing import List, Dict, Optional, Any

class Scheduler:
    def __init__(self, workstations: Dict[str, Workstation], robots: Dict[str, Robot],
                 tool_to_workstation_map: Dict[str, str] = None, safety_buffer_factor: float = 0.1):
        self.workstations = workstations
        self.robots = robots
        self.robot_pickup_duration = 20 
        self.robot_trasnport_duration = 20
        # NEW: A critical map for finding which workstation hosts a given tool
        self.tool_to_workstation_map = tool_to_workstation_map or {}
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

    # 遍历所有机器人，找到第一个在指定时间窗内可用的机器人
    def _find_best_robot_for_transport(self, pickup_time: int, transport_base_duration: int) -> Optional[Robot]:
        transport_duration = self.get_buffered_duration(transport_base_duration)  # 计算运输所需的总时间（加上安全缓冲）
        for robot in self.robots.values(): 
            if robot.is_available_at(pickup_time, transport_duration):  # 选择遍历到的第一个空闲机器人
                return robot  
        return None  # 如果没有可用机器人，返回 None

    def _find_robot_and_pickup_time(self, earliest_pickup_time: int, transport_duration: int):
        """
        在所有机器人里找一个最早可在 >= earliest_pickup_time 进行取样的机器人。
        返回 (robot_obj, assigned_pickup_time)。若无解返回 (None, None)。
        规则：以机器人 timeline 最后段结束时刻作为其空闲时间，再与 earliest_pickup_time 取 max。
        """
        best_robot, best_pickup = None, None
        best_time = float('inf')
        for r in self.robots.values():
            r_free_time = 0
            if r.timeline:
                # 机器人最后一段的 drop_time
                r_free_time = max(t2 for (_, _, t2) in r.timeline)
            pickup_t = max(r_free_time, earliest_pickup_time)
            if pickup_t < best_time:
                best_robot, best_pickup = r, pickup_t
                best_time = pickup_t
        return best_robot, best_pickup

    def _plan_regular_transfers(self, current_time: int):
        """
        为所有“已完成一步且在工位等待取样”的 REGULAR 任务，尝试一次性预留：
        - 机器人 (pickup_time ~ drop_time)
        - 下一工位 (drop_time ~ drop_time + next_proc)
        只有两者都能满足才落表；否则保持等待。
        """
        # 1) 收集等待取样的源工位与任务
        candidates = []
        for ws in self.workstations.values():
            if ws.status == ResourceStatus.COMPLETED_WAITING_FOR_PICKUP and ws.current_task_id is not None:
                task = self.tasks[ws.current_task_id]
                # 跳过最后一步和无缝场景；它们分别已完成/另有处理
                is_last_step = task.current_step >= len(task.workflow) - 1
                needs_continuous = (not is_last_step) and ((task.current_step, task.current_step + 1) in task.seamless_indices)
                if not is_last_step and not needs_continuous:
                    candidates.append((ws, task))

        # 2) 尝试为每个候选安排“取样→运输→下一工位”
        for src_ws, task in candidates:
            current_ws_id = task.workflow[task.current_step]

            # 机器人参数
            pick_dur = self.robot_pickup_duration
            trans_dur = self.robot_trasnport_duration
            transport_duration = pick_dur + trans_dur

            # 下一工位与处理时长
            next_ws_id = task.workflow[task.current_step + 1]
            next_ws = self.workstations[next_ws_id]
            next_proc = self.get_buffered_duration(task.processing_times[next_ws_id])

            # 设定最早可取样时间（当前就可取）
            earliest_pickup = current_time

            # 选机器人 + 分配 pickup_time
            robot, pickup_time = self._find_robot_and_pickup_time(earliest_pickup, transport_duration)
            if robot is None:
                continue  # 没有可用机器人，继续等

            drop_time = pickup_time + transport_duration

            # 确认下一工位在到达时段可用
            if not next_ws.is_available_at(drop_time, next_proc):
                continue  # 下一工位此刻排不开，下一轮再试

            robot.timeline.append((task.id, pickup_time, drop_time))
            next_ws.timeline.append((task.id, drop_time, drop_time + next_proc))
            task.next_step_scheduled = True

            # 如果 pickup 在未来，把机器人标记为 RESERVED（状态会按时间推进）
            if pickup_time > current_time:
                if robot.status != ResourceStatus.RESERVED or robot.current_task_id != task.id:
                    robot.status = ResourceStatus.RESERVED
                    robot.current_task_id = task.id
                    self.log(current_time, f"EVENT: Robot {robot.id} RESERVED for task:{task.id} (pickup@{pickup_time}).")

            self.log(current_time,
                    f"RESERVATION: Task {task.id} [REGULAR-TRANSFER] "
                    f"src:{current_ws_id}@{src_ws.id} -> next:{next_ws_id}@{next_ws.id}, "
                    f"pickup@{pickup_time}, drop@{drop_time}.")

    # update_resource_states 在“模拟时间前进”时根据 timeline 来完成任务，资源状态更新
    def _attempt_reservation_and_generate_commands(self, task: Task, ws: Workstation, current_time: int,
                                                   commands: list):
        current_ws_id = task.workflow[task.current_step]
        is_last_step = task.current_step >= len(task.workflow) - 1
        needs_continuous = not is_last_step and (task.current_step, task.current_step + 1) in task.seamless_indices

        # --- Strategy 1: Seamless Connection ---
        if needs_continuous:
            processing_duration = self.get_buffered_duration(task.processing_times[current_ws_id])
            finish_time = current_time + processing_duration 
            pickup_time = finish_time - self.robot_pickup_duration  
            if not ws.is_available_at(current_time, processing_duration): return False

            # 统一固定机器人取样，运输时间是20
            robot = self._find_best_robot_for_transport(pickup_time, self.robot_pickup_duration + self.robot_trasnport_duration)
            if not robot: return False
            robot_duration = self.robot_pickup_duration + self.robot_trasnport_duration
            arrival_time_at_next_ws = pickup_time + robot_duration

            next_ws_id = task.workflow[task.current_step + 1]
            next_ws = self.workstations[next_ws_id]
            next_processing_duration = self.get_buffered_duration(task.processing_times[next_ws_id])
            if not next_ws.is_available_at(arrival_time_at_next_ws, next_processing_duration): return False

            self.log(current_time,
                     f"RESERVATION: Task {task.id} [SEAMLESS] approved for workstation:{current_ws_id}@{ws.id} -> workstation:{next_ws_id}@{next_ws_id}.")

            # 生成时间安排
            ws.timeline.append((task.id, current_time, finish_time))
            robot.timeline.append((task.id, pickup_time, arrival_time_at_next_ws))
            next_ws.timeline.append((task.id, arrival_time_at_next_ws, arrival_time_at_next_ws + next_processing_duration))
            task.next_step_scheduled = True

            commands.append({
                "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
                "target_resource": ws.id,
                "action": "START_PROCESSING",
                "params": {
                    "task_id": task.id,
                    "workstation_id": current_ws_id,
                    "step_index": task.current_step,
                    "duration_estimate": processing_duration,
                    "is_seamless_next": True
                }
            })

        # --- Strategy 2: Regular Step ---
        else:
            processing_duration = self.get_buffered_duration(task.processing_times[current_ws_id])
  
            if not ws.is_available_at(current_time, processing_duration): return False

            self.log(current_time,
                     f"RESERVATION: Task {task.id} [REGULAR] approved for workstation:{current_ws_id}@{ws.id}.")
            
            #* 生成时间安排
            ws.timeline.append((task.id, current_time, current_time + processing_duration))

            commands.append({
                "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
                "target_resource": ws.id,
                "action": "START_PROCESSING",
                "params": {
                    "task_id": task.id,
                    "workstation_id": current_ws_id,
                    "step_index": task.current_step,
                    "duration_estimate": processing_duration,
                    "is_seamless_next": False
                }
            })
        
        return True
    

    def schedule(self, current_time: int) -> List[Dict[str, Any]]:
        commands = []  

        # 先尝试为 REGULAR 的“已完成一步、等取样”的任务安排取样→运输→下一工位
        self._plan_regular_transfers(current_time)

        # 收集所有空闲工作站
        idle_workstations = [ws for ws in self.workstations.values() if ws.status == ResourceStatus.IDLE]

        # 如果不存在空闲的工作站，返回空指令列表
        if not idle_workstations: return commands

        # 遍历所有空闲工作站，为每个工作站分配任务
        for ws in idle_workstations: 
            if ws.status != ResourceStatus.IDLE: continue
            task_has_been_scheduled = False
            for task in self.task_queue: 
                if task.status == TaskStatus.WAITING:
                    required_ws_id = task.workflow[task.current_step]
                    if required_ws_id == ws.id:
                        if self._attempt_reservation_and_generate_commands(task, ws, current_time, commands):
                            task_has_been_scheduled = True
                            break  

            if task_has_been_scheduled:
                self.task_queue.remove(task)

        return commands 

