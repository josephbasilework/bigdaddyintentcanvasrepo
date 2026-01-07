"""Tests for job retry and recovery module."""


from app.jobs.retry import (
    BackoffStrategy,
    CheckpointState,
    FailureType,
    PermanentError,
    RetryPolicy,
    TransientError,
    classify_exception,
)


class TestRetryPolicy:
    """Tests for RetryPolicy dataclass."""

    def test_default_retry_policy(self):
        """Test default retry policy values."""
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.retry_transient_only is True

    def test_custom_retry_policy(self):
        """Test custom retry policy values."""
        policy = RetryPolicy(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.LINEAR,
            base_delay=2.0,
            max_delay=30.0,
            retry_transient_only=False,
        )
        assert policy.max_attempts == 5
        assert policy.backoff_strategy == BackoffStrategy.LINEAR
        assert policy.base_delay == 2.0
        assert policy.max_delay == 30.0
        assert policy.retry_transient_only is False

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=100.0,
        )
        assert policy.calculate_delay(1) == 1.0
        assert policy.calculate_delay(2) == 2.0
        assert policy.calculate_delay(3) == 4.0
        assert policy.calculate_delay(4) == 8.0

    def test_exponential_backoff_with_max_delay(self):
        """Test exponential backoff with max delay cap."""
        policy = RetryPolicy(
            max_attempts=10,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=5.0,
        )
        assert policy.calculate_delay(1) == 1.0
        assert policy.calculate_delay(2) == 2.0
        assert policy.calculate_delay(3) == 4.0
        assert policy.calculate_delay(4) == 5.0  # Capped at max_delay
        assert policy.calculate_delay(5) == 5.0  # Still capped

    def test_linear_backoff_calculation(self):
        """Test linear backoff delay calculation."""
        policy = RetryPolicy(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.LINEAR,
            base_delay=2.0,
            max_delay=100.0,
        )
        assert policy.calculate_delay(1) == 2.0
        assert policy.calculate_delay(2) == 4.0
        assert policy.calculate_delay(3) == 6.0
        assert policy.calculate_delay(4) == 8.0

    def test_fixed_backoff_calculation(self):
        """Test fixed backoff delay calculation."""
        policy = RetryPolicy(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.FIXED,
            base_delay=3.0,
            max_delay=100.0,
        )
        assert policy.calculate_delay(1) == 3.0
        assert policy.calculate_delay(2) == 3.0
        assert policy.calculate_delay(3) == 3.0

    def test_immediate_backoff_calculation(self):
        """Test immediate backoff (no delay)."""
        policy = RetryPolicy(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.IMMEDIATE,
            base_delay=1.0,
            max_delay=100.0,
        )
        assert policy.calculate_delay(1) == 0.0
        assert policy.calculate_delay(2) == 0.0
        assert policy.calculate_delay(3) == 0.0

    def test_should_retry_transient_with_transient_only(self):
        """Test should_retry returns True for transient failures when retry_transient_only is True."""
        policy = RetryPolicy(
            max_attempts=3,
            retry_transient_only=True,
        )
        assert policy.should_retry(1, FailureType.TRANSIENT) is True
        assert policy.should_retry(2, FailureType.TRANSIENT) is True
        assert policy.should_retry(3, FailureType.TRANSIENT) is True
        assert policy.should_retry(4, FailureType.TRANSIENT) is False  # Exceeded max_attempts

    def test_should_not_retry_permanent_with_transient_only(self):
        """Test should_retry returns False for permanent failures when retry_transient_only is True."""
        policy = RetryPolicy(
            max_attempts=3,
            retry_transient_only=True,
        )
        assert policy.should_retry(1, FailureType.PERMANENT) is False
        assert policy.should_retry(2, FailureType.PERMANENT) is False

    def test_should_retry_all_when_transient_only_is_false(self):
        """Test should_retry returns True for all failures when retry_transient_only is False."""
        policy = RetryPolicy(
            max_attempts=3,
            retry_transient_only=False,
        )
        assert policy.should_retry(1, FailureType.TRANSIENT) is True
        assert policy.should_retry(1, FailureType.PERMANENT) is True
        assert policy.should_retry(1, FailureType.UNKNOWN) is True


class TestClassifyException:
    """Tests for exception classification."""

    def test_classify_transient_error(self):
        """Test TransientError is classified as TRANSIENT."""
        error = TransientError("Temporary failure")
        assert classify_exception(error) == FailureType.TRANSIENT

    def test_classify_permanent_error(self):
        """Test PermanentError is classified as PERMANENT."""
        error = PermanentError("Invalid input")
        assert classify_exception(error) == FailureType.PERMANENT

    def test_classify_timeout_error(self):
        """Test timeout exceptions are classified as TRANSIENT."""
        error = TimeoutError("Request timed out")
        assert classify_exception(error) == FailureType.TRANSIENT

    def test_classify_connection_error(self):
        """Test connection errors are classified as TRANSIENT."""
        error = ConnectionError("Failed to connect")
        assert classify_exception(error) == FailureType.TRANSIENT

    def test_classify_authentication_error(self):
        """Test authentication errors are classified as PERMANENT."""
        class AuthError(Exception):
            pass

        error = AuthError("Authentication failed")
        assert classify_exception(error) == FailureType.PERMANENT

    def test_classify_unknown_error(self):
        """Test unknown errors default to UNKNOWN."""
        error = ValueError("Some random error")
        assert classify_exception(error) == FailureType.UNKNOWN


class TestCheckpointState:
    """Tests for CheckpointState dataclass."""

    def test_checkpoint_state_creation(self):
        """Test creating a CheckpointState."""
        state = CheckpointState(
            job_id="test-job-123",
            step_name="process_data",
            step_number=2,
            data={"processed": 100},
        )
        assert state.job_id == "test-job-123"
        assert state.step_name == "process_data"
        assert state.step_number == 2
        assert state.data == {"processed": 100}
        assert state.timestamp is not None

    def test_checkpoint_state_to_dict(self):
        """Test converting CheckpointState to dictionary."""
        state = CheckpointState(
            job_id="test-job-123",
            step_name="process_data",
            step_number=2,
            data={"processed": 100},
        )
        data = state.to_dict()
        assert data["job_id"] == "test-job-123"
        assert data["step_name"] == "process_data"
        assert data["step_number"] == 2
        assert data["data"] == {"processed": 100}
        assert "timestamp" in data

    def test_checkpoint_state_from_dict(self):
        """Test creating CheckpointState from dictionary."""
        data = {
            "job_id": "test-job-123",
            "step_name": "process_data",
            "step_number": 2,
            "data": {"processed": 100},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        state = CheckpointState.from_dict(data)
        assert state.job_id == "test-job-123"
        assert state.step_name == "process_data"
        assert state.step_number == 2
        assert state.data == {"processed": 100}
        assert state.timestamp == "2024-01-01T00:00:00Z"

    def test_checkpoint_state_from_dict_with_missing_fields(self):
        """Test creating CheckpointState from dictionary with missing optional fields."""
        data = {
            "job_id": "test-job-123",
            "step_name": "process_data",
            "step_number": 2,
        }
        state = CheckpointState.from_dict(data)
        assert state.job_id == "test-job-123"
        assert state.step_name == "process_data"
        assert state.step_number == 2
        assert state.data == {}
        assert state.timestamp is not None  # Should have default timestamp
