import json
from models import Task, Workstation, Robot, ResourceStatus, TaskStatus, Tool, Resource
from scheduler import Scheduler


def setup_lab():    
    workstations = {
                    'W1': Workstation(id='W1', tools=[Tool(id='t1'), Tool(id='t2')]),
                    'W2': Workstation(id='W2', tools=[Tool(id='t2'), Tool(id='t4')]),
                    'W3': Workstation(id='W3', tools=[Tool(id='t3'), Tool(id='t6')]),
                    'W4': Workstation(id='W4', tools=[Tool(id='t4'), Tool(id='t8')])
                    }
    robots = {'R1': Robot(id='R1'), 'R2': Robot(id='R2'), 'R3': Robot(id='R3')}

    return workstations, robots

def setup_tasks():
    
    tasks = [
        Task(id='T1',
             workflow=['W1', 'W2', 'W3', 'W4'],
             processing_times={'W1': 100, 'W2': 100, 'W3': 100, 'W4':100},
             seamless_steps=[(0, 1)])
    ]
    return tasks


def update_resource_states(current_time: int, scheduler: Scheduler):
    workstations = scheduler.workstations
    robots = scheduler.robots
    # ---------- 1) 工作站：由时间线推断 BUSY / 完成 ----------
    for ws in workstations.values():
        if not ws.timeline:
            continue

        active_segment = None
        for (task_id, start_time, end_time) in ws.timeline:
            if start_time <= current_time < end_time:
                active_segment = (task_id, start_time, end_time)
                break  # 当前时刻有任务安排

        # --- 1.1 正在干 ---
        if active_segment is not None:
            task_id, start_time, end_time = active_segment
            if ws.status != ResourceStatus.BUSY or ws.current_task_id != task_id:
                ws.status = ResourceStatus.BUSY
                ws.current_task_id = task_id
                # 对于“无缝预留”的下一站，schedule 已经写了 timeline，这里自然进入 RUNNING
                task = scheduler.tasks[task_id]
                task.status = TaskStatus.RUNNING
                scheduler.log(current_time, f"EVENT: {ws.id} started task:{task_id} [{start_time}->{end_time}]. BUSY.")

        # --- 1.2 刚干完，完成任务或者等待取样 ---
        elif ws.status == ResourceStatus.BUSY and ws.current_task_id is not None:
            # 以当前任务 id 找到它对应的那段 segment_end_time ，确认已完成
            segment_end_time  = None
            for (task_id, start_time, end_time ) in reversed(ws.timeline):
                if task_id == ws.current_task_id:
                    segment_end_time  = end_time 
                    break
            if segment_end_time  is not None and current_time >= segment_end_time :
                task = scheduler.tasks[ws.current_task_id]
                is_last_step = task.current_step >= len(task.workflow) - 1

                if is_last_step:
                    ws.status = ResourceStatus.IDLE
                    task.status = TaskStatus.COMPLETED
                    scheduler.log(current_time, f"EVENT: task {task.id} completed final step at {ws.id}. IDLE.")
                    ws.current_task_id = None
                else:
                    ws.status = ResourceStatus.COMPLETED_WAITING_FOR_PICKUP
                    scheduler.log(current_time, f"EVENT: task {task.id} finished step at {ws.id}. WAITING_PICKUP.")
                    
    # ---------- 2) 机器人：扫描时间线，驱动 RESERVED / TRANSPORTING / IDLE ----------
    for robot in robots.values():
        # 获取上时刻机器人的状态
        was_moving_to_pickup = (robot.status == ResourceStatus.MOVING_TO_PICKUP and robot.current_task_id is not None)
        was_transporting = (robot.status == ResourceStatus.TRANSPORTING and robot.current_task_id is not None)
        previous_task_id = robot.current_task_id if (was_moving_to_pickup or was_transporting) else None

        active_segment = None
        next_segment = None

        if robot.timeline:
            for (task_id, pickup_time, drop_time) in robot.timeline:
                # 机器人时间线的“活动段”仍是 [pickup_time, drop_time)
                if pickup_time <= current_time < drop_time:
                    active_segment = (task_id, pickup_time, drop_time)
                    break
                if current_time < pickup_time:
                    next_segment = (task_id, pickup_time, drop_time)
                    break

        if active_segment is not None:
            task_id, pickup_time, drop_time = active_segment
            pickup_finish_time = pickup_time + scheduler.robot_pickup_duration

            # 阶段 2：MOVING_TO_PICKUP （取样中：pickup_time ~ pickup_time+取样耗时）
            if current_time < pickup_finish_time:
                if robot.status != ResourceStatus.MOVING_TO_PICKUP or robot.current_task_id != task_id:
                    robot.status = ResourceStatus.MOVING_TO_PICKUP
                    robot.current_task_id = task_id
                    scheduler.log(current_time, f"EVENT: Robot {robot.id} MOVING_TO_PICKUP task:{task_id} [{pickup_time}->{pickup_finish_time}].")
            # 阶段 3：TRANSPORTING （运输中：取样完成 ~ drop_time）
            else:  
                first_enter_transporting = (robot.status != ResourceStatus.TRANSPORTING or robot.current_task_id != task_id)
                if first_enter_transporting:
                    robot.status = ResourceStatus.TRANSPORTING
                    robot.current_task_id = task_id

                    task = scheduler.tasks[task_id]
                    completed_workstation_id = task.workflow[task.current_step]
                    source_workstation = workstations[completed_workstation_id]
                    if source_workstation.status == ResourceStatus.COMPLETED_WAITING_FOR_PICKUP:
                        source_workstation.status = ResourceStatus.IDLE
                        source_workstation.current_task_id = None
                    scheduler.log(current_time, f"EVENT: Robot {robot.id} TRANSPORT task:{task_id} [{pickup_finish_time}->{drop_time}], released {completed_workstation_id}.")
                    
        elif next_segment is not None:
            task_id, pickup_time, drop_time = next_segment
            if robot.status != ResourceStatus.RESERVED or robot.current_task_id != task_id:
                robot.status = ResourceStatus.RESERVED
                robot.current_task_id = task_id
                scheduler.log(current_time, f"EVENT: Robot {robot.id} RESERVED for task:{task_id} (pickup@{pickup_time}).")

        else:
            # 没有活动段也没有未来段：若上一刻在运输，则刚刚 drop 完成 → 推进任务一步并入队
            if was_transporting and previous_task_id is not None:
                finished_task = scheduler.tasks[previous_task_id]

                # 推进步数
                finished_task.current_step += 1

                if finished_task.current_step >= len(finished_task.workflow):
                    finished_task.status = TaskStatus.COMPLETED
                    scheduler.log(current_time, f"EVENT: task {finished_task.id} finished all steps via drop-off.")
                else:
                    # 如果下一工位处理已预排，就不要入队；保持 RUNNING
                    if finished_task.next_step_scheduled:
                        finished_task.status = TaskStatus.RUNNING
                        scheduler.log(current_time, f"EVENT: task {finished_task.id} step advanced; next step already scheduled.")
                    else:
                        finished_task.status = TaskStatus.WAITING
                        if finished_task not in scheduler.task_queue:
                            scheduler.task_queue.append(finished_task)
                        scheduler.log(current_time, f"EVENT: task {finished_task.id} re-queued after drop-off (append).")

                # 无论是否入队，都把“预排标记”清回 False，供下一轮使用
                finished_task.next_step_scheduled = False

            if robot.status != ResourceStatus.IDLE or robot.current_task_id is not None:
                robot.status = ResourceStatus.IDLE
                robot.current_task_id = None
                scheduler.log(current_time, f"EVENT: Robot {robot.id} now IDLE.")

# 执行命令，仅设置工作站状态为忙碌，以及记录当前工作站的任务ID
def execute_commands(commands: list, scheduler: Scheduler, current_time: int):
    """模拟硬件平台执行收到的指令"""
    if not commands:
        return

    scheduler.log(current_time, "COMMAND_EXECUTION: Platform is executing new commands.")
    for cmd in commands:
        resource_id = cmd['target_resource']

        # 简化执行逻辑：只更新状态。真实系统会通过API调用硬件。
        if cmd['action'] == 'START_PROCESSING': 
            task = scheduler.tasks[cmd['params']['task_id']]  
            ws = scheduler.workstations[resource_id] 
            ws.status = ResourceStatus.BUSY  
            ws.current_task_id = task.id 

            # 如果是无缝连接，相关的资源已被内部预留
            if cmd['params']['is_seamless_next']:  # 如果下一步是无缝连接
                pass  # 占位，实际系统可在此扩展更多操作


def run_simulation():
    """运行模拟主循环"""

    # 定义存在的工作站，机器人
    # 定义初始任务
    workstations, robots = setup_lab()
    tasks_to_run = setup_tasks()
    scheduler = Scheduler(workstations, robots, safety_buffer_factor=0.1) # 实例化调度器

    # 将所有新任务加入调度器的任务队列
    for task in tasks_to_run: 
        scheduler.add_task(task)

    scheduler.log(0, f"self.task_queue: {[t.id for t in scheduler.task_queue]}")  # 记录当前任务队列状态

    scheduler.log(0, "--- Simulation Starting ---")

    # 每个时刻 1.更新任务/资源状态，2.生成调度指令并执行 3.检查是否完成所有任务
    for current_time in range(1000): # 模拟时间从0到999
        # 任务/资源状态
        update_resource_states(current_time, scheduler)
        # scheduler.log(current_time, f"self.task_queue: {[t.id for t in scheduler.task_queue]}")  # 记录当前任务队列状态
        new_commands = scheduler.schedule(current_time)

        # 对于非空指令任务，开始执行命令
        if new_commands:
            print(f"\n[Time {current_time:04d}] --- SCHEDULER DECISION (JSON) ---")
            print(json.dumps(new_commands, indent=2)) 
            print("-------------------------------------\n")
            execute_commands(new_commands, scheduler, current_time)

        # 检查是否所有任务都已完成，如果没有完成所有任务，则在时间范围内继续循环调度
        if all(t.status == TaskStatus.COMPLETED for t in tasks_to_run):
            scheduler.log(current_time, "--- All tasks completed. Simulation finished. ---")
            break


if __name__ == "__main__":
    run_simulation()
