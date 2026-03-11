"""Core scheduling data models used by the AIMCP action layer."""

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


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
    processing_times: Dict[str, int]
    workflow: List[str] = field(default_factory=list)
    workflow_tools: List[str] = field(default_factory=list)
    seamless_steps: List[Tuple[int, int]] = field(default_factory=list)
    sample_id: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.WAITING
    current_step: int = 0
    next_step_scheduled: bool = False
    seamless_indices: Set[Tuple[int, int]] = field(init=False)

    def __post_init__(self):
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

    def processing_key_for_step(self, step_index: int) -> str:
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

