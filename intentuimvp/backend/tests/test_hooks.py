"""Tests for deterministic hook execution."""

from __future__ import annotations

from app.database import SessionLocal
from app.models.canvas import Canvas
from app.models.turn import Turn, TurnActor, TurnType
from app.repositories.hook_repo import HookRepository
from app.services.turns import log_turn_for_user_sync


class _DummyStore:
    def persist_turn(self, **_: object) -> None:
        return None


def test_event_hook_fires_and_logs_turn(monkeypatch) -> None:
    """Event hooks should emit a hook_fired turn when matched."""
    monkeypatch.setattr(
        "app.services.turns.get_user_data_store", lambda: _DummyStore()
    )

    db = SessionLocal()
    try:
        canvas = Canvas(user_id="default_user", name="Hook Test Canvas")
        db.add(canvas)
        db.commit()
        db.refresh(canvas)

        repo = HookRepository(db)
        hook = repo.create_hook(
            name="Test node created hook",
            description="Triggers on node created",
            hook_type="event",
            event_type="node.created",
            schedule_type=None,
            trigger={},
            action={"type": "command", "command": "/clear"},
            enabled=True,
            user_id="default_user",
            workspace_id=None,
            session_id=None,
        )

        turn = log_turn_for_user_sync(
            db,
            user_id="default_user",
            workspace_id=canvas.id,
            actor=TurnActor.USER,
            turn_type=TurnType.NODE_CREATED,
            summary="Node created",
            payload={"nodeId": "1"},
        )

        assert turn is not None

        db.expire_all()
        hook_turns = (
            db.query(Turn)
            .filter(Turn.type == TurnType.HOOK_FIRED)
            .all()
        )

        assert hook_turns
        assert any(
            t.get_payload().get("hook_id") == hook.id for t in hook_turns
        )
    finally:
        db.close()
