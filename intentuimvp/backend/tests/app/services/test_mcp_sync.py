"""Tests for Multi-MCP Task DAG sync helpers."""

from datetime import UTC, datetime, timedelta

from app.services.mcp_sync import (
    ExternalTaskUpdate,
    compute_task_status_changes,
    reconcile_external_task_updates,
    select_next_ready_task,
)


def test_compute_task_status_changes_detects_completion() -> None:
    prev = [{"id": "task-1", "status": "pending"}]
    next_tasks = [{"id": "task-1", "status": "completed"}]

    changes = compute_task_status_changes(prev, next_tasks)

    assert len(changes) == 1
    change = changes[0]
    assert change.task_id == "task-1"
    assert change.prev_status == "pending"
    assert change.next_status == "completed"


def test_select_next_ready_task_respects_dependencies() -> None:
    dag = {
        "tasks": [
            {"id": "task-a", "title": "A", "status": "completed"},
            {"id": "task-b", "title": "B", "status": "pending"},
            {"id": "task-c", "title": "C", "status": "pending"},
        ],
        "dependencies": [
            {"task_id": "task-b", "depends_on_task_id": "task-a"},
        ],
    }

    next_task = select_next_ready_task(dag)

    assert next_task is not None
    assert next_task["id"] == "task-b"


def test_reconcile_external_updates_prefers_newest() -> None:
    local_time = datetime(2026, 1, 19, 12, 0, tzinfo=UTC)
    external_time = local_time + timedelta(hours=1)

    dag = {
        "tasks": [
            {
                "id": "task-1",
                "title": "Setup",
                "status": "pending",
                "status_updated_at": local_time.isoformat(),
            }
        ]
    }
    updates = [
        ExternalTaskUpdate(
            task_id="task-1",
            status="completed",
            updated_at=external_time,
            source="docs",
        )
    ]

    updated_dag, conflicts, changed = reconcile_external_task_updates(
        dag, updates, policy="newest", now=external_time
    )

    assert changed is True
    assert conflicts == []
    assert updated_dag["tasks"][0]["status"] == "completed"


def test_reconcile_external_updates_records_conflict_when_local_newer() -> None:
    local_time = datetime(2026, 1, 19, 12, 0, tzinfo=UTC)
    external_time = local_time - timedelta(hours=1)

    dag = {
        "tasks": [
            {
                "id": "task-1",
                "title": "Setup",
                "status": "in_progress",
                "status_updated_at": local_time.isoformat(),
            }
        ]
    }
    updates = [
        ExternalTaskUpdate(
            task_id="task-1",
            status="completed",
            updated_at=external_time,
            source="docs",
        )
    ]

    updated_dag, conflicts, changed = reconcile_external_task_updates(
        dag, updates, policy="newest", now=local_time
    )

    assert changed is False
    assert updated_dag["tasks"][0]["status"] == "in_progress"
    assert len(conflicts) == 1
    assert conflicts[0]["task_id"] == "task-1"
