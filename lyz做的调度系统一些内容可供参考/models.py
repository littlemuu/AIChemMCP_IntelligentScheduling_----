"""
models.py
本文件定义了智能调度系统中每个实体的数据模型。
包含以下数据模型：
1. Task：机器化学家系统接收到的任务流信息，由一系列的工作站需求链接而成。
2. Workstation：机器化学家系统中的工作站，负责执行任务。
3. Robot：机器化学家系统中的机器人，负责将样品从一个工作站运输到下一个工作站。
4. Status：定义了任务状态、资源状态等枚举类型。
"""

import enum
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set


class TaskStatus(enum.Enum):
    WAITING = 1
    RUNNING = 2
    COMPLETED = 3
    ERROR = 4

class ResourceStatus(enum.Enum):
    IDLE = 1 
    BUSY = 2 
    RESERVED = 3 
    COMPLETED_WAITING_FOR_PICKUP = 4 
    MOVING_TO_PICKUP = 5             
    TRANSPORTING = 6                 
    ERROR = 7


@dataclass
class Task:

    id: str
    workflow: List[str] 
    #! 为简化问题，将工具和工作站等价，即1个工作站对应1个工具，所以暂不使用工具，用工作站代替即可
    # workflow_tools: List[str]
    processing_times: Dict[str, int] 
    seamless_steps: List[Tuple[int, int]] = field(default_factory=list) 

    status: TaskStatus = TaskStatus.WAITING
    current_step: int = 0
    seamless_indices: Set[Tuple[int, int]] = field(init=False) 
    
    next_step_scheduled = False
    def __post_init__(self):
        self.seamless_indices = set(self.seamless_steps)

@dataclass
class Resource:
    id: str
    status: ResourceStatus = ResourceStatus.IDLE

    timeline: List[tuple] = field(default_factory=list)
    current_task_id: str = None # 目前正在执行的任务id。

    def is_available_at(self, start_time, duration): 
        end_time = start_time + duration
        for _, r_start, r_end in self.timeline:
            if max(start_time, r_start) < min(end_time, r_end):
                return False
        return True


@dataclass
class Tool:
    id: str


@dataclass
class Workstation(Resource):
    tools: List[Tool] = field(default_factory=list)


@dataclass
class Robot(Resource):
    pass
