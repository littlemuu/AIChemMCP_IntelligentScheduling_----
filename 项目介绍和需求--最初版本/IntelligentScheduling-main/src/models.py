"""
models.py
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
    workflow_tools: List[str]
    processing_times: List[str]
    seamless_steps: List[Tuple[int, int]] = field(default_factory=list)

    status: TaskStatus = TaskStatus.WAITING
    current_step: int = 0
    seamless_indices: Set[Tuple[int, int]] = field(init=False)

    def __post_init__(self):
        self.seamless_indices = set(self.seamless_steps)


@dataclass
class Resource:
    id: str
    status: ResourceStatus = ResourceStatus.IDLE
    timeline: List[tuple] = field(default_factory=list)
    current_task_id: str = None

    def is_available_at(self, start_time, duration):
        """Checks if the resource is free for a given time window."""
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
