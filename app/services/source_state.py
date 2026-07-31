from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SourceRuntimeState
from app.db.session import SessionFactory
from app.services.runtime_state import ensure_utc


@dataclass(frozen=True)
class SourceSnapshot:
    source_name: str
    status: str
    consecutive_failures: int
    circuit_open_until: datetime | None
    last_error_code: str | None
    last_run_at: datetime | None
    last_success_at: datetime | None

    def circuit_is_open(self, now: datetime | None = None) -> bool:
        if self.circuit_open_until is None:
            return False
        active_now = now or datetime.now(UTC)
        return ensure_utc(self.circuit_open_until) > ensure_utc(active_now)


class SourceStateService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def get(self, source_name: str) -> SourceSnapshot:
        with self.session_factory.begin() as session:
            return snapshot(self._get_or_create(session, source_name))

    def list_all(self) -> list[SourceSnapshot]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(SourceRuntimeState).order_by(SourceRuntimeState.source_name)
            ).all()
            return [snapshot(row) for row in rows]

    def mark_running(self, source_name: str, started_at: datetime) -> SourceSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session, source_name)
            state.status = "running"
            state.last_run_at = started_at
            return snapshot(state)

    def mark_success(self, source_name: str, finished_at: datetime) -> SourceSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session, source_name)
            state.status = "completed"
            state.consecutive_failures = 0
            state.circuit_open_until = None
            state.last_error_code = None
            state.last_run_at = finished_at
            state.last_success_at = finished_at
            return snapshot(state)

    def mark_failure(
        self,
        source_name: str,
        finished_at: datetime,
        error_code: str,
        threshold: int,
        cooldown_hours: int,
        force_open: bool = False,
    ) -> SourceSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session, source_name)
            state.consecutive_failures += 1
            should_open = force_open or state.consecutive_failures >= threshold
            state.status = "circuit_open" if should_open else "failed"
            state.last_error_code = error_code
            state.last_run_at = finished_at
            if should_open:
                state.circuit_open_until = finished_at + timedelta(hours=cooldown_hours)
            return snapshot(state)

    def mark_throttled(
        self,
        source_name: str,
        finished_at: datetime,
        error_code: str,
    ) -> SourceSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session, source_name)
            state.status = "throttled"
            state.last_error_code = error_code
            state.last_run_at = finished_at
            return snapshot(state)

    def reset_circuit(self, source_name: str) -> SourceSnapshot:
        with self.session_factory.begin() as session:
            state = self._get_or_create(session, source_name)
            state.status = "idle"
            state.consecutive_failures = 0
            state.circuit_open_until = None
            state.last_error_code = None
            return snapshot(state)

    @staticmethod
    def _get_or_create(session: Session, source_name: str) -> SourceRuntimeState:
        state = session.scalar(
            select(SourceRuntimeState).where(SourceRuntimeState.source_name == source_name)
        )
        if state is None:
            state = SourceRuntimeState(source_name=source_name, status="idle")
            session.add(state)
            session.flush()
        return state


def snapshot(state: SourceRuntimeState) -> SourceSnapshot:
    return SourceSnapshot(
        source_name=state.source_name,
        status=state.status,
        consecutive_failures=state.consecutive_failures,
        circuit_open_until=state.circuit_open_until,
        last_error_code=state.last_error_code,
        last_run_at=state.last_run_at,
        last_success_at=state.last_success_at,
    )
