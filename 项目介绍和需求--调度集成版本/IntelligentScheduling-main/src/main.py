"""Simulation entrypoint for the intelligent scheduling framework."""

import json

from models import ResourceStatus, Robot, Task, TaskStatus, Tool, Workstation
from scheduler import Scheduler


def setup_lab():
    # 这里构造一个最小可运行的实验室场景，方便直接验证调度逻辑。
    # 场景中包含 4 个工作站和 2 个机器人。
    # 每个工作站配置若干工具，同时生成一个 tool_to_workstation_map，
    # 让任务可以只按“所需工具”描述流程，再由调度器解析到具体工作站。
    workstations = {
        "W1": Workstation(id="W1", tools=[Tool(id="T1"), Tool(id="T2")]),
        "W2": Workstation(id="W2", tools=[Tool(id="T3"), Tool(id="T4")]),
        "W3": Workstation(id="W3", tools=[Tool(id="T5")]),
        "W4": Workstation(id="W4", tools=[Tool(id="T6")]),
    }
    robots = {
        "R1": Robot(id="R1"),
        "R2": Robot(id="R2"),
    }
    tool_to_workstation_map = {
        tool.id: workstation.id
        for workstation in workstations.values()
        for tool in workstation.tools
    }
    return workstations, robots, tool_to_workstation_map


def setup_tasks():
    # 这里定义两条示例任务，分别用来覆盖不同调度情形：
    # Task-A 的前两步之间是无缝衔接，用来验证“当前站 + 机器人 + 下一站”联合预留；
    # Task-B 是普通多步流程，用来验证加工完成后再做转运规划的逻辑是否正常。
    return [
        Task(
            id="Task-A",
            workflow_tools=["T1", "T3", "T5"],
            processing_times={"T1": 100, "T3": 80, "T5": 90},
            seamless_steps=[(0, 1)],
            sample_id="S-A",
        ),
        Task(
            id="Task-B",
            workflow_tools=["T2", "T4", "T6"],
            processing_times={"T2": 60, "T4": 70, "T6": 75},
            sample_id="S-B",
        ),
    ]


def update_resource_states(current_time: int, scheduler: Scheduler):
    # 这个函数模拟“硬件世界随时间自然推进”的过程。
    # 调度器负责预留未来资源，而这里负责把这些预留转化成真实状态变化，
    # 例如：工作站从 IDLE 变成 BUSY，机器人从 RESERVED 变成 MOVING_TO_PICKUP，
    # 再到 TRANSPORTING，最终把任务推进到下一步。
    workstations = scheduler.workstations
    robots = scheduler.robots

    for workstation in workstations.values():
        if not workstation.timeline:
            continue

        active_segment = None
        for task_id, start_time, end_time in workstation.timeline:
            if start_time <= current_time < end_time:
                active_segment = (task_id, start_time, end_time)
                break

        if active_segment is not None:
            task_id, start_time, end_time = active_segment
            processing_end = scheduler.processing_end_times[(workstation.id, task_id, start_time)]
            task = scheduler.tasks[task_id]
            if current_time < processing_end:
                # 当前时刻还在纯加工区间内，说明工作站正在真正执行实验操作，
                # 此时工作站应该表现为 BUSY，任务也应处于 RUNNING。
                if workstation.status != ResourceStatus.BUSY or workstation.current_task_id != task_id:
                    workstation.status = ResourceStatus.BUSY
                    workstation.current_task_id = task_id
                    task.status = TaskStatus.RUNNING
                    scheduler.log(
                        current_time,
                        f"EVENT: {workstation.id} started task:{task_id} [{start_time}->{processing_end}]. BUSY.",
                    )
            elif workstation.current_task_id == task_id and workstation.status != ResourceStatus.COMPLETED_WAITING_FOR_PICKUP:
                # 到了这里，加工本身已经结束，但工作站占位区间还没结束。
                # 这说明样品虽然已经做完当前步骤，但仍停留在工作站上等待机器人接走。
                # 因此工作站不能立即接收下一个任务，而是进入 WAITING_PICKUP 状态。
                workstation.status = ResourceStatus.COMPLETED_WAITING_FOR_PICKUP
                scheduler.log(
                    current_time,
                    f"EVENT: task {task.id} finished step at {workstation.id}. WAITING_PICKUP.",
                )
        elif workstation.current_task_id is not None and workstation.status == ResourceStatus.BUSY:
            # 如果当前工作站已经不在任何活跃时间窗中，但仍记录着 current_task_id，
            # 通常意味着该任务已经执行到了最后一步，且不再需要后续取样或转运。
            # 在这种情况下，可以直接把任务标记为 COMPLETED，并释放工作站。
            task = scheduler.tasks[workstation.current_task_id]
            if task.is_last_step():
                workstation.status = ResourceStatus.IDLE
                workstation.current_task_id = None
                task.status = TaskStatus.COMPLETED
                scheduler.log(
                    current_time,
                    f"EVENT: task {task.id} completed final step at {workstation.id}. IDLE.",
                )

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
            task_id, pickup_time, drop_time = active_segment
            pickup_finish_time = pickup_time + scheduler.robot_pickup_duration
            if current_time < pickup_finish_time:
                # 机器人执行一个转运任务时，先经历“去取样 / 取样”的阶段，
                # 然后才进入真正的运输阶段。
                # 这里把两段拆开，是为了让状态日志和未来扩展更清晰。
                if robot.status != ResourceStatus.MOVING_TO_PICKUP or robot.current_task_id != task_id:
                    robot.status = ResourceStatus.MOVING_TO_PICKUP
                    robot.current_task_id = task_id
                    scheduler.log(
                        current_time,
                        f"EVENT: Robot {robot.id} MOVING_TO_PICKUP task:{task_id} [{pickup_time}->{pickup_finish_time}].",
                    )
            else:
                if robot.status != ResourceStatus.TRANSPORTING or robot.current_task_id != task_id:
                    robot.status = ResourceStatus.TRANSPORTING
                    robot.current_task_id = task_id
                    task = scheduler.tasks[task_id]
                    completed_ws_id = scheduler._resolve_workstation_for_step(task, task.current_step)
                    source_workstation = workstations[completed_ws_id]
                    if source_workstation.current_task_id == task_id:
                        # 源工作站只有在机器人真正接手样品后才能释放。
                        # 这点非常重要，因为很多冲突都发生在“加工已结束，但样品还没搬走”的窗口。
                        source_workstation.status = ResourceStatus.IDLE
                        source_workstation.current_task_id = None
                    scheduler.log(
                        current_time,
                        f"EVENT: Robot {robot.id} TRANSPORT task:{task_id} [{pickup_finish_time}->{drop_time}], released {completed_ws_id}.",
                    )
        elif next_segment is not None:
            # 如果当前没有正在执行的运输片段，但未来时间线里已有预留任务，
            # 则机器人应该保持 RESERVED，表示它不能再被新的转运任务占用。
            task_id, pickup_time, _ = next_segment
            if robot.status != ResourceStatus.RESERVED or robot.current_task_id != task_id:
                robot.status = ResourceStatus.RESERVED
                robot.current_task_id = task_id
                scheduler.log(
                    current_time,
                    f"EVENT: Robot {robot.id} RESERVED for task:{task_id} (pickup@{pickup_time}).",
                )
        else:
            if was_transporting and previous_task_id is not None:
                # 当机器人离开运输时间窗，说明样品已经被送达目标工作站。
                # 这时需要推进任务步号，让任务正式进入下一步。
                # 如果下一步在之前已经被调度器提前预留，则任务继续保持 RUNNING；
                # 如果还没有被预留，则重新放回队列，等待下一轮工作站调度。
                finished_task = scheduler.tasks[previous_task_id]
                finished_task.current_step += 1

                if finished_task.current_step >= finished_task.total_steps:
                    finished_task.status = TaskStatus.COMPLETED
                    scheduler.log(current_time, f"EVENT: task {finished_task.id} finished all steps via drop-off.")
                else:
                    if finished_task.next_step_scheduled:
                        finished_task.status = TaskStatus.RUNNING
                        scheduler.log(
                            current_time,
                            f"EVENT: task {finished_task.id} step advanced; next step already scheduled.",
                        )
                    else:
                        finished_task.status = TaskStatus.WAITING
                        if finished_task not in scheduler.task_queue:
                            scheduler.task_queue.append(finished_task)
                        scheduler.log(
                            current_time,
                            f"EVENT: task {finished_task.id} re-queued after drop-off.",
                        )

                finished_task.next_step_scheduled = False

            if robot.status != ResourceStatus.IDLE or robot.current_task_id is not None:
                robot.status = ResourceStatus.IDLE
                robot.current_task_id = None
                scheduler.log(current_time, f"EVENT: Robot {robot.id} now IDLE.")


def execute_commands(commands: list, scheduler: Scheduler, current_time: int):
    # 这里的 execute_commands 只是一个本地模拟器。
    # 在真实系统中，这一层通常会替换成：
    # 1. 向硬件控制端发送 API 请求；
    # 2. 或通过消息总线下发执行命令；
    # 3. 再结合 ACK / 回执去更新任务真实状态。
    # 当前为了聚焦调度算法本身，只保留最小的状态更新逻辑。
    if not commands:
        return

    scheduler.log(current_time, "COMMAND_EXECUTION: Platform is executing new commands.")
    for command in commands:
        if command["action"] != "START_PROCESSING":
            continue

        task = scheduler.tasks[command["params"]["task_id"]]
        workstation = scheduler.workstations[command["target_resource"]]
        workstation.status = ResourceStatus.BUSY
        workstation.current_task_id = task.id
        task.status = TaskStatus.RUNNING


def run_simulation(max_time: int = 1000):
    # 这是整个仿真的主循环。
    # 每一个时间刻都严格按照以下顺序运行：
    # 1. 先根据既有时间线推进资源状态；
    # 2. 再让调度器根据当前状态做新的决策；
    # 3. 最后模拟平台执行这些新命令。
    # 这种顺序可以避免“先调度、后结算旧状态”带来的逻辑混乱。
    workstations, robots, tool_to_workstation_map = setup_lab()
    tasks_to_run = setup_tasks()
    scheduler = Scheduler(
        workstations,
        robots,
        tool_to_workstation_map=tool_to_workstation_map,
        safety_buffer_factor=0.1,
    )

    for task in tasks_to_run:
        scheduler.add_task(task)

    scheduler.log(0, f"task_queue: {[task.id for task in scheduler.task_queue]}")
    scheduler.log(0, "--- Simulation Starting ---")

    for current_time in range(max_time):
        update_resource_states(current_time, scheduler)
        new_commands = scheduler.schedule(current_time)

        if new_commands:
            print(f"\n[Time {current_time:04d}] --- SCHEDULER DECISION (JSON) ---")
            print(json.dumps(new_commands, indent=2))
            print("-------------------------------------\n")
            execute_commands(new_commands, scheduler, current_time)

        if all(task.status == TaskStatus.COMPLETED for task in tasks_to_run):
            scheduler.log(current_time, "--- All tasks completed. Simulation finished. ---")
            break


if __name__ == "__main__":
    run_simulation()
