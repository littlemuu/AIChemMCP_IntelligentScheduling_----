import json
from models import Task, Workstation, Robot, ResourceStatus, TaskStatus
from scheduler import Scheduler


def setup_lab():
    workstations = {'W1': Workstation(id='W1'), 'W2': Workstation(id='W2'), 'W3': Workstation(id='W3')}
    robots = {'R1': Robot(id='R1'), 'R2': Robot(id='R2')}
    return workstations, robots


def setup_tasks():
    tasks = [
        Task(id='T1',
             workflow=['W1', 'W2', 'W1', 'W3'],
             processing_times={'W1': 50, 'W2': 60},
             seamless_steps=[(0, 1)]),
        Task(id='T2',
             workflow=['W3', 'W2'],
             processing_times={'W3': 70, 'W2': 80}),
    ]
    return tasks


def update_resource_states(current_time: int, scheduler: Scheduler):
    workstations = scheduler.workstations
    robots = scheduler.robots

    for ws in workstations.values():
        if ws.status == ResourceStatus.BUSY and ws.timeline:
            _, _, end_time = ws.timeline[-1]
            if current_time >= end_time:
                task = scheduler.tasks[ws.current_task_id]
                is_last_step = task.current_step >= len(task.workflow) - 1

                if is_last_step:
                    ws.status = ResourceStatus.IDLE
                    task.status = TaskStatus.COMPLETED
                    scheduler.log(current_time, f"EVENT: Task {task.id} completed final step at {ws.id}. IDLE.")
                    ws.current_task_id = None
                else:
                    ws.status = ResourceStatus.COMPLETED_WAITING_FOR_PICKUP
                    scheduler.log(current_time, f"EVENT: Task {task.id} finished step at {ws.id}. WAITING_PICKUP.")

    for robot in robots.values():
        if robot.status == ResourceStatus.RESERVED and robot.timeline:
            task_id, start_time, _ = robot.timeline[-1]
            if current_time >= start_time:
                robot.status = ResourceStatus.TRANSPORTING
                robot.current_task_id = task_id
                task = scheduler.tasks[task_id]
                completed_ws_id = task.workflow[task.current_step]
                workstations[completed_ws_id].status = ResourceStatus.IDLE
                workstations[completed_ws_id].current_task_id = None
                scheduler.log(current_time, f"EVENT: Robot {robot.id} picked up for T:{task.id}. {completed_ws_id} is now IDLE.")

    for robot in robots.values():
        if robot.status == ResourceStatus.TRANSPORTING and robot.timeline:
            task_id, _, end_time = robot.timeline[-1]
            if current_time >= end_time:
                robot.status = ResourceStatus.IDLE
                robot.current_task_id = None
                task = scheduler.tasks[task_id]
                task.current_step += 1
                next_ws_id = task.workflow[task.current_step]
                workstations[next_ws_id].status = ResourceStatus.BUSY
                workstations[next_ws_id].current_task_id = task.id
                scheduler.log(current_time, f"EVENT: Robot {robot.id} dropped off for T:{task.id} at {next_ws_id}. Now BUSY.")


def execute_commands(commands: list, scheduler: Scheduler, current_time: int):
    if not commands:
        return

    scheduler.log(current_time, "COMMAND_EXECUTION: Platform is executing new commands.")
    for cmd in commands:
        resource_id = cmd['target_resource']
        if cmd['action'] == 'START_PROCESSING':
            task = scheduler.tasks[cmd['task_id']]
            ws = scheduler.workstations[resource_id]
            ws.status = ResourceStatus.BUSY
            ws.current_task_id = task.id

            if cmd['is_seamless_next']:
                pass


def run_simulation():
    workstations, robots = setup_lab()
    tasks_to_run = setup_tasks()

    scheduler = Scheduler(workstations, robots, safety_buffer_factor=0.1)
    for task in tasks_to_run:
        scheduler.add_task(task)

    scheduler.log(0, "--- Simulation Starting ---")

    for current_time in range(1000):
        update_resource_states(current_time, scheduler)
        new_commands = scheduler.schedule(current_time)

        if new_commands:
            print(f"\n[Time {current_time:04d}] --- SCHEDULER DECISION (JSON) ---")
            print(json.dumps(new_commands, indent=2))
            print("-------------------------------------\n")
            execute_commands(new_commands, scheduler, current_time)

        if all(t.status == TaskStatus.COMPLETED for t in tasks_to_run):
            scheduler.log(current_time, "--- All tasks completed. Simulation finished. ---")
            break


if __name__ == "__main__":
    run_simulation()
