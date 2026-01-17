"""Unit tests for Turn model and TurnRepository with session scoping."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.canvas import Canvas
from app.models.node import Node, NodeType
from app.models.turn import Turn, TurnActor, TurnType
from app.repositories.turn_repo import TurnRepository


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(in_memory_db):
    """Create a database session for testing."""
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=in_memory_db)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_canvas(db_session: Session) -> Canvas:
    """Create a test canvas."""
    canvas = Canvas(user_id="test-user", name="Test Canvas")
    db_session.add(canvas)
    db_session.commit()
    db_session.refresh(canvas)
    return canvas


@pytest.fixture
def test_node(db_session: Session, test_canvas: Canvas) -> Node:
    """Create a test node."""
    node = Node(
        canvas_id=test_canvas.id,
        type=NodeType.TEXT,
        label="Test Node",
        position='{"x": 0, "y": 0, "z": 0}',
    )
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)
    return node


class TestTurnModel:
    """Tests for Turn model."""

    def test_create_turn(self, db_session: Session):
        """Test creating a turn."""
        turn = Turn(
            session_id="test-session-123",
            sequence_number=1,
            actor=TurnActor.USER,
            type=TurnType.USER_INPUT,
            summary="User entered a command",
        )
        db_session.add(turn)
        db_session.commit()
        db_session.refresh(turn)

        assert turn.id is not None
        assert turn.session_id == "test-session-123"
        assert turn.sequence_number == 1
        assert turn.actor == TurnActor.USER
        assert turn.type == TurnType.USER_INPUT
        assert turn.timestamp is not None

    def test_turn_payload(self, db_session: Session):
        """Test turn payload get/set."""
        turn = Turn(
            session_id="test-session-123",
            sequence_number=1,
            actor=TurnActor.SYSTEM,
            type=TurnType.NODE_CREATED,
            summary="Created a node",
        )
        turn.set_payload({"nodeId": 42, "label": "Test"})
        db_session.add(turn)
        db_session.commit()
        db_session.refresh(turn)

        payload = turn.get_payload()
        assert payload["nodeId"] == 42
        assert payload["label"] == "Test"

    def test_turn_to_dict(self, db_session: Session):
        """Test turn serialization."""
        turn = Turn(
            session_id="test-session-123",
            sequence_number=1,
            actor=TurnActor.AGENT,
            type=TurnType.AGENT_RESPONSE,
            summary="Agent responded",
        )
        turn.set_payload({"response": "Hello"})
        db_session.add(turn)
        db_session.commit()
        db_session.refresh(turn)

        result = turn.to_dict()
        assert result["sessionId"] == "test-session-123"
        assert result["sequenceNumber"] == 1
        assert result["actor"] == "agent"
        assert result["type"] == "agent_response"
        assert result["payload"]["response"] == "Hello"

    def test_turn_with_related_node(self, db_session: Session, test_node: Node):
        """Test turn with related node reference."""
        turn = Turn(
            session_id="test-session-123",
            sequence_number=1,
            actor=TurnActor.SYSTEM,
            type=TurnType.NODE_CREATED,
            summary="Created node",
            related_node_id=test_node.id,
        )
        db_session.add(turn)
        db_session.commit()
        db_session.refresh(turn)

        assert turn.related_node_id == test_node.id
        result = turn.to_dict()
        assert result["relatedNodeId"] == test_node.id


class TestTurnRepository:
    """Tests for TurnRepository with session scoping."""

    def test_create_turn(self, db_session: Session):
        """Test creating a turn via repository."""
        repo = TurnRepository(db_session)
        turn = repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="User command",
        )

        assert turn.id is not None
        assert turn.session_id == "session-1"
        assert turn.sequence_number == 1  # First turn

    def test_create_turn_with_payload(self, db_session: Session):
        """Test creating a turn with payload."""
        repo = TurnRepository(db_session)
        turn = repo.create_turn(
            session_id="session-1",
            actor=TurnActor.SYSTEM,
            turn_type=TurnType.NODE_CREATED,
            summary="Node created",
            payload={"nodeId": 1, "type": "text"},
        )

        assert turn.get_payload()["nodeId"] == 1

    def test_sequence_number_increments(self, db_session: Session):
        """Test that sequence numbers auto-increment per session."""
        repo = TurnRepository(db_session)

        turn1 = repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Turn 1",
        )
        turn2 = repo.create_turn(
            session_id="session-1",
            actor=TurnActor.AGENT,
            turn_type=TurnType.AGENT_RESPONSE,
            summary="Turn 2",
        )
        turn3 = repo.create_turn(
            session_id="session-1",
            actor=TurnActor.SYSTEM,
            turn_type=TurnType.NODE_CREATED,
            summary="Turn 3",
        )

        assert turn1.sequence_number == 1
        assert turn2.sequence_number == 2
        assert turn3.sequence_number == 3

    def test_sequence_numbers_independent_per_session(self, db_session: Session):
        """Test that sequence numbers are independent between sessions."""
        repo = TurnRepository(db_session)

        turn1_s1 = repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Session 1, Turn 1",
        )
        turn1_s2 = repo.create_turn(
            session_id="session-2",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Session 2, Turn 1",
        )
        turn2_s1 = repo.create_turn(
            session_id="session-1",
            actor=TurnActor.AGENT,
            turn_type=TurnType.AGENT_RESPONSE,
            summary="Session 1, Turn 2",
        )

        assert turn1_s1.sequence_number == 1
        assert turn1_s2.sequence_number == 1  # Independent!
        assert turn2_s1.sequence_number == 2

    def test_get_turns_for_session(self, db_session: Session):
        """Test getting all turns for a session."""
        repo = TurnRepository(db_session)

        # Create turns in two sessions
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="S1 T1",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.AGENT,
            turn_type=TurnType.AGENT_RESPONSE,
            summary="S1 T2",
        )
        repo.create_turn(
            session_id="session-2",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="S2 T1",
        )

        turns = repo.get_turns_for_session("session-1")
        assert len(turns) == 2
        assert turns[0].summary == "S1 T1"
        assert turns[1].summary == "S1 T2"

    def test_get_turns_for_session_ordered(self, db_session: Session):
        """Test that turns are returned in sequence order."""
        repo = TurnRepository(db_session)

        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="First",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.AGENT,
            turn_type=TurnType.AGENT_RESPONSE,
            summary="Second",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.SYSTEM,
            turn_type=TurnType.NODE_CREATED,
            summary="Third",
        )

        turns = repo.get_turns_for_session("session-1")
        assert [t.sequence_number for t in turns] == [1, 2, 3]

    def test_get_turns_with_limit(self, db_session: Session):
        """Test limiting number of returned turns."""
        repo = TurnRepository(db_session)

        for i in range(5):
            repo.create_turn(
                session_id="session-1",
                actor=TurnActor.USER,
                turn_type=TurnType.USER_INPUT,
                summary=f"Turn {i + 1}",
            )

        turns = repo.get_turns_for_session("session-1", limit=3)
        assert len(turns) == 3
        assert turns[0].sequence_number == 1
        assert turns[2].sequence_number == 3

    def test_get_turns_after_sequence(self, db_session: Session):
        """Test getting turns after a specific sequence number."""
        repo = TurnRepository(db_session)

        for i in range(5):
            repo.create_turn(
                session_id="session-1",
                actor=TurnActor.USER,
                turn_type=TurnType.USER_INPUT,
                summary=f"Turn {i + 1}",
            )

        turns = repo.get_turns_for_session("session-1", after_sequence=2)
        assert len(turns) == 3
        assert turns[0].sequence_number == 3
        assert turns[2].sequence_number == 5

    def test_get_turns_for_session_filter_actor(self, db_session: Session):
        """Test filtering turns by actor in session query."""
        repo = TurnRepository(db_session)

        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="User input",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.SYSTEM,
            turn_type=TurnType.NODE_CREATED,
            summary="System event",
        )

        user_turns = repo.get_turns_for_session("session-1", actor=TurnActor.USER)
        assert len(user_turns) == 1
        assert user_turns[0].actor == TurnActor.USER

    def test_get_turns_by_type(self, db_session: Session):
        """Test filtering turns by type."""
        repo = TurnRepository(db_session)

        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Input 1",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.AGENT,
            turn_type=TurnType.AGENT_RESPONSE,
            summary="Response 1",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Input 2",
        )

        input_turns = repo.get_turns_by_type("session-1", TurnType.USER_INPUT)
        assert len(input_turns) == 2
        assert all(t.type == TurnType.USER_INPUT for t in input_turns)

    def test_get_latest_turn(self, db_session: Session):
        """Test getting the most recent turn."""
        repo = TurnRepository(db_session)

        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="First",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.AGENT,
            turn_type=TurnType.AGENT_RESPONSE,
            summary="Last",
        )

        latest = repo.get_latest_turn("session-1")
        assert latest is not None
        assert latest.summary == "Last"
        assert latest.sequence_number == 2

    def test_get_latest_turn_empty_session(self, db_session: Session):
        """Test get_latest_turn returns None for empty session."""
        repo = TurnRepository(db_session)
        latest = repo.get_latest_turn("nonexistent-session")
        assert latest is None

    def test_count_turns(self, db_session: Session):
        """Test counting turns in a session."""
        repo = TurnRepository(db_session)

        for i in range(3):
            repo.create_turn(
                session_id="session-1",
                actor=TurnActor.USER,
                turn_type=TurnType.USER_INPUT,
                summary=f"Turn {i + 1}",
            )

        count = repo.count_turns("session-1")
        assert count == 3

    def test_count_turns_empty_session(self, db_session: Session):
        """Test counting turns in empty session returns 0."""
        repo = TurnRepository(db_session)
        count = repo.count_turns("nonexistent-session")
        assert count == 0

    def test_get_turn_by_sequence(self, db_session: Session):
        """Test getting a specific turn by sequence number."""
        repo = TurnRepository(db_session)

        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="First",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.AGENT,
            turn_type=TurnType.AGENT_RESPONSE,
            summary="Second",
        )

        turn = repo.get_turn_by_sequence("session-1", 2)
        assert turn is not None
        assert turn.summary == "Second"

    def test_get_turn_by_sequence_not_found(self, db_session: Session):
        """Test get_turn_by_sequence returns None for invalid sequence."""
        repo = TurnRepository(db_session)
        turn = repo.get_turn_by_sequence("session-1", 999)
        assert turn is None

    def test_session_isolation(self, db_session: Session):
        """Test that operations on one session don't affect another."""
        repo = TurnRepository(db_session)

        # Create 3 turns in session-1
        for i in range(3):
            repo.create_turn(
                session_id="session-1",
                actor=TurnActor.USER,
                turn_type=TurnType.USER_INPUT,
                summary=f"S1 Turn {i + 1}",
            )

        # Create 2 turns in session-2
        for i in range(2):
            repo.create_turn(
                session_id="session-2",
                actor=TurnActor.USER,
                turn_type=TurnType.USER_INPUT,
                summary=f"S2 Turn {i + 1}",
            )

        # Verify isolation
        assert repo.count_turns("session-1") == 3
        assert repo.count_turns("session-2") == 2

        s1_turns = repo.get_turns_for_session("session-1")
        s2_turns = repo.get_turns_for_session("session-2")

        assert all(t.session_id == "session-1" for t in s1_turns)
        assert all(t.session_id == "session-2" for t in s2_turns)
