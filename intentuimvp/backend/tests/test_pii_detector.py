"""Tests for PII detection and redaction.

Implements NFR-PRIV-004: PII warning + log redaction rules.

Tests the pii_detector module which provides:
- Comprehensive PII pattern detection
- PII warning before sending to Gateway
- Redaction patterns for log sanitization
- Configurable severity levels and action modes
"""

from app.pii_detector import (
    PIIDetectionResult,
    PIIDetector,
    PIIMode,
    PIISeverity,
    PIIType,
    get_pii_detector,
    redact_pii,
    scan_for_pii,
)


class TestPIIDetector:
    """Tests for PIIDetector class."""

    def test_detector_initialization_defaults(self):
        """PIIDetector should initialize with default settings."""
        detector = PIIDetector()

        assert detector.mode == PIIMode.WARN
        assert detector.min_severity == PIISeverity.LOW
        assert len(detector.enabled_types) > 0

    def test_detector_initialization_custom_settings(self):
        """PIIDetector should accept custom settings."""
        detector = PIIDetector(
            mode=PIIMode.REDACT,
            min_severity=PIISeverity.HIGH,
            enabled_types={PIIType.EMAIL, PIIType.SSN},
        )

        assert detector.mode == PIIMode.REDACT
        assert detector.min_severity == PIISeverity.HIGH
        assert detector.enabled_types == {PIIType.EMAIL, PIIType.SSN}

    def test_scan_empty_text(self):
        """Scanning empty text should return no PII detected."""
        detector = PIIDetector()
        result = detector.scan("")

        assert result.has_pii is False
        assert len(result.detections) == 0

    def test_scan_text_without_pii(self):
        """Scanning text without PII should return no detections."""
        detector = PIIDetector()
        result = detector.scan("Hello world, this is a test message.")

        assert result.has_pii is False
        assert len(result.detections) == 0

    def test_scan_detects_email(self):
        """Scanning should detect email addresses."""
        detector = PIIDetector()
        # Construct email to avoid secret scanning
        email = "user" + "@" + "example.com"
        result = detector.scan(f"Contact me at {email}")

        assert result.has_pii is True
        assert len(result.detections) >= 1
        assert any(d.type == PIIType.EMAIL for d in result.detections)
        assert result.severity == PIISeverity.LOW

    def test_scan_detects_phone(self):
        """Scanning should detect phone numbers."""
        detector = PIIDetector()
        result = detector.scan("Call me at 555-123-4567")

        assert result.has_pii is True
        assert any(d.type == PIIType.PHONE for d in result.detections)
        assert result.severity == PIISeverity.LOW

    def test_scan_detects_ssn(self):
        """Scanning should detect SSN numbers."""
        detector = PIIDetector()
        result = detector.scan("My SSN is 123-45-6789")

        assert result.has_pii is True
        assert any(d.type == PIIType.SSN for d in result.detections)
        assert result.severity == PIISeverity.HIGH

    def test_scan_detects_credit_card(self):
        """Scanning should detect credit card numbers."""
        detector = PIIDetector()
        result = detector.scan("Card: 4111-1111-1111-1111")

        assert result.has_pii is True
        assert any(d.type == PIIType.CREDIT_CARD for d in result.detections)
        assert result.severity == PIISeverity.HIGH

    def test_scan_detects_api_key(self):
        """Scanning should detect OpenAI API keys."""
        detector = PIIDetector()
        # Construct test key to avoid secret scanning
        test_key = "sk-" + "abc123def456789012345678901234567890"
        result = detector.scan(f"Using key: {test_key}")

        assert result.has_pii is True
        assert any(d.type == PIIType.API_KEY for d in result.detections)
        assert result.severity == PIISeverity.CRITICAL

    def test_scan_detects_github_token(self):
        """Scanning should detect GitHub tokens."""
        detector = PIIDetector()
        # Construct test token to avoid secret scanning
        test_token = "ghp_" + "1234567890" + "abcdefghijklmnopqrstuvwxyz" + "123456"
        result = detector.scan(f"GH token: {test_token}")

        assert result.has_pii is True
        assert any(d.type == PIIType.API_KEY for d in result.detections)
        assert result.severity == PIISeverity.CRITICAL

    def test_scan_detects_multiple_pii_types(self):
        """Scanning should detect multiple PII types in one text."""
        detector = PIIDetector()
        # Construct email to avoid secret scanning
        email = "user" + "@" + "example.com"
        result = detector.scan(f"Contact {email} or call 555-123-4567. SSN: 123-45-6789")

        assert result.has_pii is True
        detected_types = {d.type for d in result.detections}
        assert PIIType.EMAIL in detected_types
        assert PIIType.PHONE in detected_types
        assert PIIType.SSN in detected_types
        assert result.severity == PIISeverity.HIGH  # Highest severity

    def test_scan_with_min_severity_filter(self):
        """Scanning with min_severity should filter out lower severity PII."""
        detector = PIIDetector(min_severity=PIISeverity.HIGH)
        # Construct email to avoid secret scanning
        email = "user" + "@" + "example.com"
        result = detector.scan(f"Email: {email}, SSN: 123-45-6789")

        assert result.has_pii is True
        # Should only detect SSN (HIGH severity), not email (LOW severity)
        assert any(d.type == PIIType.SSN for d in result.detections)
        assert not any(d.type == PIIType.EMAIL for d in result.detections)

    def test_scan_with_enabled_types_filter(self):
        """Scanning with enabled_types should only detect specified types."""
        detector = PIIDetector(enabled_types={PIIType.EMAIL})
        # Construct email to avoid secret scanning
        email = "user" + "@" + "example.com"
        result = detector.scan(f"Email: {email}, Phone: 555-123-4567")

        assert result.has_pii is True
        assert any(d.type == PIIType.EMAIL for d in result.detections)
        assert not any(d.type == PIIType.PHONE for d in result.detections)

    def test_scan_with_context(self):
        """Scanning with context should include context in warning message."""
        detector = PIIDetector()
        # Construct email to avoid secret scanning
        email = "user" + "@" + "example.com"
        result = detector.scan(f"Email: {email}", context="test request")

        assert result.has_pii is True
        assert "test request" in (result.warning_message or "")

    def test_redact_mode_provides_redacted_text(self):
        """REDACT mode should provide redacted text in result."""
        detector = PIIDetector(mode=PIIMode.REDACT)
        result = detector.scan("Email: user@example.com")

        assert result.has_pii is True
        assert result.redacted_text is not None
        assert "[EMAIL_REDACTED]" in result.redacted_text
        assert "user@example.com" not in result.redacted_text

    def test_redact_multiple_items(self):
        """Redaction should handle multiple PII items."""
        detector = PIIDetector(mode=PIIMode.REDACT)
        result = detector.scan("Email: user@example.com, Phone: 555-123-4567")

        assert result.has_pii is True
        assert result.redacted_text is not None
        assert "[EMAIL_REDACTED]" in result.redacted_text
        assert "[PHONE_REDACTED]" in result.redacted_text

    def test_is_blocked_returns_false_for_low_severity(self):
        """is_blocked should return False for low severity PII in WARN mode."""
        detector = PIIDetector(mode=PIIMode.WARN)
        result = detector.scan("Email: user@example.com")

        assert detector.is_blocked(result) is False

    def test_is_blocked_returns_true_for_critical_severity(self):
        """is_blocked should return True for critical severity PII in WARN mode."""
        detector = PIIDetector(mode=PIIMode.WARN)
        # Construct test key to avoid secret scanning
        test_key = "sk-" + "abc123def456789012345678901234567890"
        result = detector.scan(f"API key: {test_key}")

        assert result.severity == PIISeverity.CRITICAL
        assert detector.is_blocked(result) is True

    def test_is_blocked_returns_true_in_block_mode(self):
        """is_blocked should return True for any PII in BLOCK mode."""
        detector = PIIDetector(mode=PIIMode.BLOCK)
        result = detector.scan("Email: user@example.com")

        assert detector.is_blocked(result) is True

    def test_get_redaction_patterns(self):
        """get_redaction_patterns should return list of regex patterns."""
        detector = PIIDetector()
        patterns = detector.get_redaction_patterns()

        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert all(isinstance(p, str) for p in patterns)

    def test_exclusion_patterns_prevent_false_positives(self):
        """Exclusion patterns should prevent false positives like dates."""
        detector = PIIDetector()

        # Date that looks like SSN pattern but should be excluded
        result = detector.scan("Date: 2024-01-15")

        # Should not detect SSN (date exclusion pattern)
        assert not any(d.type == PIIType.SSN for d in result.detections)

    def test_scan_preserves_match_positions(self):
        """Scanning should preserve match positions for each detection."""
        detector = PIIDetector()
        result = detector.scan("Call me at 555-123-4567 today")

        assert result.has_pii is True
        assert any(d.type == PIIType.PHONE for d in result.detections)

        phone_match = next(d for d in result.detections if d.type == PIIType.PHONE)
        assert phone_match.start_pos >= 0
        assert phone_match.end_pos > phone_match.start_pos
        assert phone_match.match == "555-123-4567"


class TestPIIDetectionResult:
    """Tests for PIIDetectionResult model."""

    def test_result_bool_conversion(self):
        """PIIDetectionResult should convert to bool based on has_pii."""
        result_with_pii = PIIDetectionResult(has_pii=True)
        result_without_pii = PIIDetectionResult(has_pii=False)

        assert bool(result_with_pii) is True
        assert bool(result_without_pii) is False


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_pii_detector_returns_singleton(self):
        """get_pii_detector should return the same instance."""
        detector1 = get_pii_detector()
        detector2 = get_pii_detector()

        assert detector1 is detector2

    def test_scan_for_pii_convenience_function(self):
        """scan_for_pii should work as a convenience function."""
        result = scan_for_pii("Email: user@example.com")

        assert result.has_pii is True

    def test_redact_pii_convenience_function(self):
        """redact_pii should redact PII from text."""
        redacted = redact_pii("Email: user@example.com")

        assert "[EMAIL_REDACTED]" in redacted
        assert "user@example.com" not in redacted

    def test_redact_pii_with_no_pii_returns_original(self):
        """redact_pii should return original text when no PII is found."""
        original = "Hello world, no PII here."
        redacted = redact_pii(original)

        assert redacted == original


class TestPIIModes:
    """Tests for different PII modes."""

    def test_warn_mode_does_not_redact(self):
        """WARN mode should not provide redacted text."""
        detector = PIIDetector(mode=PIIMode.WARN)
        result = detector.scan("Email: user@example.com")

        assert result.has_pii is True
        assert result.redacted_text is None

    def test_redact_mode_provides_redacted_text(self):
        """REDACT mode should provide redacted text."""
        detector = PIIDetector(mode=PIIMode.REDACT)
        result = detector.scan("Email: user@example.com")

        assert result.has_pii is True
        assert result.redacted_text is not None
        assert "[EMAIL_REDACTED]" in result.redacted_text


class TestPIIPatterns:
    """Tests for specific PII patterns."""

    def test_detects_slack_token(self):
        """Should detect Slack tokens."""
        detector = PIIDetector()
        # Construct test token to avoid secret scanning
        prefix = "xoxb-"
        mid = "1234567890"
        suffix = "-" + "1234567890123" + "-" + "AbCdEfGhIjKlMnOpQrStUv"
        test_token = prefix + mid + suffix
        result = detector.scan(f"Slack token: {test_token}")

        assert result.has_pii is True
        assert any(d.type == PIIType.API_KEY for d in result.detections)
        assert result.severity == PIISeverity.CRITICAL

    def test_detects_aws_access_key(self):
        """Should detect AWS access keys."""
        detector = PIIDetector()
        # Use constructed key to avoid gitleaks false positive
        test_key = "AKIA" + "ABCDEFGHIJKLMNOPQRST"
        result = detector.scan(f"AWS key: {test_key}")

        assert result.has_pii is True
        assert any(d.type == PIIType.API_KEY for d in result.detections)

    def test_detects_ip_address(self):
        """Should detect IP addresses."""
        detector = PIIDetector()
        result = detector.scan("Server IP: 192.168.1.1")

        assert result.has_pii is True
        assert any(d.type == PIIType.IP_ADDRESS for d in result.detections)
        assert result.severity == PIISeverity.MEDIUM

    def test_detects_uuid(self):
        """Should detect UUID patterns."""
        detector = PIIDetector()
        result = detector.scan("UUID: 550e8400-e29b-41d4-a716-446655440000")

        assert result.has_pii is True
        assert any(d.type == PIIType.UUID for d in result.detections)
        assert result.severity == PIISeverity.LOW

    def test_detects_credential_pattern(self):
        """Should detect credential patterns."""
        detector = PIIDetector()
        result = detector.scan("password=abc123def456789")

        assert result.has_pii is True
        assert any(d.type == PIIType.CREDENTIAL for d in result.detections)
        assert result.severity == PIISeverity.HIGH
