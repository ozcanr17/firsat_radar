from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import RuntimeState
from app.db.session import SessionFactory


@dataclass(frozen=True)
class RuntimeSnapshot:
    scheduler_status: str
    last_job_started_at: datetime | None
    last_job_finished_at: datetime | None
    consecutive_failures: int
    circuit_open_until: datetime | None
    last_error_code: str | None
    last_backup_at: datetime | None
    last_retention_at: datetime | None

    def circuit_is_open(self, now: datetime | None = None) -> bool:
        if self.circuit_open_until is None:
            return False
        active_now = now or datetime.now(UTC)
        return ensure_utc(self.circuit_open_until) > ensure_utc(active_now)


class RuntimeStateService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def get(self) -> RuntimeSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session)
            return snapshot(state)

    def mark_running(self, started_at: datetime) -> RuntimeSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session)
            state.scheduler_status = "running"
            state.last_job_started_at = started_at
            state.last_error_code = None
            return snapshot(state)

    def mark_success(
        self,
        finished_at: datetime,
        backup_at: datetime,
        retention_at: datetime,
    ) -> RuntimeSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session)
            state.scheduler_status = "completed"
            state.last_job_finished_at = finished_at
            state.consecutive_failures = 0
            state.circuit_open_until = None
            state.last_error_code = None
            state.last_backup_at = backup_at
            state.last_retention_at = retention_at
            return snapshot(state)

    def mark_failure(
        self,
        finished_at: datetime,
        error_code: str,
        threshold: int,
        cooldown_hours: int,
        force_open: bool = False,
    ) -> RuntimeSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session)
            state.consecutive_failures += 1
            should_open = force_open or state.consecutive_failures >= threshold
            state.scheduler_status = "circuit_open" if should_open else "failed"
            state.last_job_finished_at = finished_at
            state.last_error_code = error_code
            if should_open:
                state.circuit_open_until = finished_at + timedelta(hours=cooldown_hours)
            return snapshot(state)

    def mark_skipped(self, status: str, error_code: str | None = None) -> RuntimeSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session)
            state.scheduler_status = status
            state.last_error_code = error_code
            return snapshot(state)

    def reset_circuit(self) -> RuntimeSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session)
            state.scheduler_status = "idle"
            state.consecutive_failures = 0
            state.circuit_open_until = None
            state.last_error_code = None
            return snapshot(state)

    def mark_backup(self, completed_at: datetime) -> RuntimeSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session)
            state.last_backup_at = completed_at
            return snapshot(state)

    def mark_retention(self, completed_at: datetime) -> RuntimeSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session)
            state.last_retention_at = completed_at
            return snapshot(state)

    @staticmethod
    def _get_or_create(session: Session) -> RuntimeState:
        state = session.get(RuntimeState, 1)
        if state is None:
            state = RuntimeState(id=1, scheduler_status="idle", consecutive_failures=0)
            session.add(state)
            session.flush()
        return state


def snapshot(state: RuntimeState) -> RuntimeSnapshot:
    return RuntimeSnapshot(
        scheduler_status=state.scheduler_status,
        last_job_started_at=state.last_job_started_at,
        last_job_finished_at=state.last_job_finished_at,
        consecutive_failures=state.consecutive_failures,
        circuit_open_until=state.circuit_open_until,
        last_error_code=state.last_error_code,
        last_backup_at=state.last_backup_at,
        last_retention_at=state.last_retention_at,
    )


def ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
