"""Core data models for the intelligent scheduling simulation."""

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


class TaskStatus(enum.Enum):
    # TaskStatus 用于描述任务在调度系统中的生命周期。
    # WAITING 表示任务当前还没有被某个工作站正式接收，仍处于候选队列中；
    # RUNNING 表示任务已经进入某个工作站或后续联动步骤的执行流程；
    # COMPLETED 表示任务的全部步骤已经执行完成；
    # ERROR 预留给未来异常恢复、硬件故障或执行失败场景。
    WAITING = 1
    RUNNING = 2
    COMPLETED = 3
    ERROR = 4


class ResourceStatus(enum.Enum):
    # ResourceStatus 同时服务于工作站和机器人两类资源。
    # 这样做的好处是调度器可以用统一方式处理“资源是否可用、是否已被预留”。
    # 其中 IDLE、BUSY、RESERVED 是通用状态；
    # COMPLETED_WAITING_FOR_PICKUP 更偏向工作站状态；
    # MOVING_TO_PICKUP、TRANSPORTING 更偏向机器人状态；
    # ERROR 仍然是为后续真实系统中的异常处理预留。
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
    processing_times: Dict[str, int]
    workflow: List[str] = field(default_factory=list)
    workflow_tools: List[str] = field(default_factory=list)
    seamless_steps: List[Tuple[int, int]] = field(default_factory=list)
    sample_id: Optional[str] = None
    status: TaskStatus = TaskStatus.WAITING
    current_step: int = 0
    next_step_scheduled: bool = False
    seamless_indices: Set[Tuple[int, int]] = field(init=False)

    def __post_init__(self):
        # 一个任务至少必须能描述出一条完整的执行步骤链。
        # 这里允许两种建模方式：
        # 1. 直接用 workflow 给出每一步对应的工作站；
        # 2. 用 workflow_tools 给出每一步所需工具，再由调度器映射到具体工作站。
        # 这样设计是为了兼容“先按工具定义工艺流程，再由系统匹配设备”的真实场景。
        if not self.workflow and not self.workflow_tools:
            raise ValueError("Task requires workflow or workflow_tools.")
        if self.workflow and self.workflow_tools and len(self.workflow) != len(self.workflow_tools):
            raise ValueError("workflow and workflow_tools must have the same length when both are provided.")
        self.seamless_indices = set(self.seamless_steps)

    @property
    def total_steps(self) -> int:
        return len(self.workflow or self.workflow_tools)

    def is_last_step(self) -> bool:
        return self.current_step >= self.total_steps - 1

    def current_workstation_id(self) -> Optional[str]:
        if not self.workflow:
            return None
        return self.workflow[self.current_step]

    def current_tool_id(self) -> Optional[str]:
        if not self.workflow_tools:
            return None
        return self.workflow_tools[self.current_step]

    def processing_key_for_step(self, step_index: int) -> str:
        # processing_times 的索引键必须和任务的建模方式一致。
        # 如果任务是按工作站建模，就用工作站 ID 取时长；
        # 如果任务是按工具建模，就用工具 ID 取时长。
        # 这样可以避免调度层反复判断“当前步骤到底应该按哪个字段找处理时间”。
        if self.workflow:
            return self.workflow[step_index]
        return self.workflow_tools[step_index]


@dataclass
class Resource:
    id: str
    status: ResourceStatus = ResourceStatus.IDLE
    timeline: List[Tuple[str, int, int]] = field(default_factory=list)
    current_task_id: Optional[str] = None

    def is_available_at(self, start_time: int, duration: int) -> bool:
        # timeline 记录的是资源未来已经被占用或已经被预留的时间区间。
        # 这里的判断逻辑很直接：
        # 只要候选时间窗和 timeline 中任意一个区间发生重叠，
        # 就说明该资源在这段时间内不可用，当前调度方案不可行。
        # 这是整个“前瞻预留”机制最基础的判断函数。
        end_time = start_time + duration
        for _, reserved_start, reserved_end in self.timeline:
            if max(start_time, reserved_start) < min(end_time, reserved_end):
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
