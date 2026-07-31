from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerState:
    enabled: bool = False
    interval_hours: int = 12
