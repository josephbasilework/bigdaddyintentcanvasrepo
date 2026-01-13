"""PII (Personally Identifiable Information) detector for sensitive content.

Implements NFR-PRIV-004: PII warning + log redaction rules.

Provides:
- Comprehensive PII pattern detection (email, phone, SSN, credit card, etc.)
- PII warning for Gateway requests before sending to LLM
- Redaction patterns for log sanitization
- Configurable severity levels and action modes
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PIIType(str, Enum):
    """Types of PII that can be detected."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    CREDENTIAL = "credential"
    API_KEY = "api_key"
    IP_ADDRESS = "ip_address"
    DRIVERS_LICENSE = "drivers_license"
    PASSPORT = "passport"
    BANK_ACCOUNT = "bank_account"
    MEDICAL_ID = "medical_id"
    ADDRESS = "address"
    UUID = "uuid"
    TOKEN = "token"


class PIISeverity(str, Enum):
    """Severity levels for PII detection."""

    LOW = "low"  # Email, phone (relatively common)
    MEDIUM = "medium"  # IP address, postal address
    HIGH = "high"  # SSN, credit card, financial info
    CRITICAL = "critical"  # API keys, tokens, passwords


class PIIMode(str, Enum):
    """Action modes when PII is detected."""

    WARN = "warn"  # Log warning but allow
    REDACT = "redact"  # Redact detected PII
    BLOCK = "block"  # Block the request entirely


@dataclass
class PIIPattern:
    """A PII detection pattern."""

    type: PIIType
    pattern: str
    severity: PIISeverity
    description: str


class PIIDetectionResult(BaseModel):
    """Result of PII detection scan.

    Attributes:
        has_pii: Whether any PII was detected.
        detections: List of individual PII detections.
        severity: Highest severity level detected.
        redacted_text: Text with PII redacted (if mode is REDACT).
        warning_message: Human-readable warning message.
    """

    has_pii: bool
    detections: list["PIIMatch"] = Field(default_factory=list)
    severity: PIISeverity = PIISeverity.LOW
    redacted_text: str | None = None
    warning_message: str | None = None

    def __bool__(self) -> bool:
        return self.has_pii


class PIIMatch(BaseModel):
    """A single PII match.

    Attributes:
        type: Type of PII detected.
        severity: Severity level of this PII.
        match: The actual matched text.
        start_pos: Start position in the original text.
        end_pos: End position in the original text.
        pattern: The regex pattern that matched.
    """

    type: PIIType
    severity: PIISeverity
    match: str
    start_pos: int
    end_pos: int
    pattern: str


class PIIDetector:
    """Detector for PII in text content.

    Provides comprehensive PII pattern detection with configurable
    severity levels and action modes.

    Usage:
        detector = PIIDetector(mode=PIIMode.WARN)
        result = detector.scan("Contact me at user@example.com")
        if result.has_pii:
            logger.warning(result.warning_message)
    """

    # PII detection patterns ordered from most specific to least specific
    PATTERNS: list[PIIPattern] = [
        # API Keys and Tokens (highest severity)
        PIIPattern(
            PIIType.API_KEY,
            r"sk-[a-zA-Z0-9]{20,}",
            PIISeverity.CRITICAL,
            "OpenAI API key",
        ),
        PIIPattern(
            PIIType.API_KEY,
            r"sk-ant-[a-zA-Z0-9_-]{20,}",
            PIISeverity.CRITICAL,
            "Anthropic API key",
        ),
        PIIPattern(
            PIIType.API_KEY,
            r"ghp_[a-zA-Z0-9]{36,}",
            PIISeverity.CRITICAL,
            "GitHub personal access token",
        ),
        PIIPattern(
            PIIType.API_KEY,
            r"gho_[a-zA-Z0-9]{36,}",
            PIISeverity.CRITICAL,
            "GitHub OAuth token",
        ),
        PIIPattern(
            PIIType.API_KEY,
            r"xox[baprs]-[a-zA-Z0-9-]{10,}",
            PIISeverity.CRITICAL,
            "Slack token",
        ),
        PIIPattern(
            PIIType.API_KEY,
            r"AKIA[A-Z0-9]{16}",
            PIISeverity.CRITICAL,
            "AWS access key",
        ),
        PIIPattern(
            PIIType.CREDENTIAL,
            r"(?:api[_-]?key|secret|password|auth|token)\s*[:=]\s*[\"']?[a-zA-Z0-9_-]{15,}",
            PIISeverity.HIGH,
            "Credential pattern",
        ),
        # SSN (US format) - high severity
        PIIPattern(
            PIIType.SSN,
            r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
            PIISeverity.HIGH,
            "Social Security Number",
        ),
        # Credit Card numbers - high severity
        PIIPattern(
            PIIType.CREDIT_CARD,
            r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            PIISeverity.HIGH,
            "Credit card number",
        ),
        # Driver's License (US format) - high severity
        PIIPattern(
            PIIType.DRIVERS_LICENSE,
            r"\b[A-Z][a-zA-Z]?\s*?\d{6,8}\b",
            PIISeverity.HIGH,
            "Driver's license number",
        ),
        # Passport numbers - high severity
        PIIPattern(
            PIIType.PASSPORT,
            r"\b[A-Z]{1,2}\d{6,9}\b",
            PIISeverity.HIGH,
            "Passport number",
        ),
        # Bank Account numbers - high severity
        PIIPattern(
            PIIType.BANK_ACCOUNT,
            r"\b(?:account|acct)\s*(?:no|#|number)?\s*[:#]?\s*\d{8,17}\b",
            PIISeverity.HIGH,
            "Bank account number",
        ),
        # Medical ID numbers - high severity
        PIIPattern(
            PIIType.MEDICAL_ID,
            r"\b(?:medical|patient)\s*(?:id|record)?\s*(?:no|#)?\s*[:#]?\s*\d{6,12}\b",
            PIISeverity.HIGH,
            "Medical ID",
        ),
        # Email addresses - low severity (common)
        PIIPattern(
            PIIType.EMAIL,
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            PIISeverity.LOW,
            "Email address",
        ),
        # Phone numbers (US format) - low severity
        PIIPattern(
            PIIType.PHONE,
            r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            PIISeverity.LOW,
            "Phone number",
        ),
        # IP addresses - medium severity
        PIIPattern(
            PIIType.IP_ADDRESS,
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            PIISeverity.MEDIUM,
            "IP address",
        ),
        # Street addresses - medium severity
        PIIPattern(
            PIIType.ADDRESS,
            r"\b\d+\s+[A-Z][a-zA-Z0-9\s,\.]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|Way|Circle|Cir)\b",
            PIISeverity.MEDIUM,
            "Street address",
        ),
        # Generic UUID - could be sensitive
        PIIPattern(
            PIIType.UUID,
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            PIISeverity.LOW,
            "UUID",
        ),
    ]

    # Patterns that should be excluded from detection (false positives)
    EXCLUSION_PATTERNS: list[str] = [
        r"\b\d{4}-\d{2}-\d{2}\b",  # Dates like 2024-01-15 (could match SSN pattern)
        r"\b(?:https?://|www\.)\S+\b",  # URLs (could match various patterns)
        r"\b[a-f0-9]{32}\b",  # MD5 hashes (could match various patterns)
    ]

    def __init__(
        self,
        mode: PIIMode = PIIMode.WARN,
        min_severity: PIISeverity = PIISeverity.LOW,
        enabled_types: set[PIIType] | None = None,
    ) -> None:
        """Initialize the PII detector.

        Args:
            mode: Action mode when PII is detected (WARN, REDACT, BLOCK).
            min_severity: Minimum severity level to report.
            enabled_types: Set of PII types to detect. None = all types.
        """
        self.mode = mode
        self.min_severity = min_severity
        self.enabled_types = enabled_types or set(PIIType)

        # Compile patterns for performance
        self._compiled_patterns = [
            (re.compile(p.pattern, re.IGNORECASE), p)
            for p in self.PATTERNS
            if p.type in self.enabled_types
        ]
        self._exclusion_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.EXCLUSION_PATTERNS
        ]

    def scan(self, text: str, context: str | None = None) -> PIIDetectionResult:
        """Scan text for PII.

        Args:
            text: Text to scan.
            context: Optional context string for warning messages.

        Returns:
            PIIDetectionResult with detection details.
        """
        if not text:
            return PIIDetectionResult(has_pii=False)

        detections: list[PIIMatch] = []
        max_severity = PIISeverity.LOW

        for pattern, pii_pattern in self._compiled_patterns:
            # Check if this pattern's severity meets our threshold
            severity_order = [PIISeverity.LOW, PIISeverity.MEDIUM, PIISeverity.HIGH, PIISeverity.CRITICAL]
            if severity_order.index(pii_pattern.severity) < severity_order.index(self.min_severity):
                continue

            for match in pattern.finditer(text):
                matched_text = match.group()

                # Check exclusions to reduce false positives
                if any(
                    exclusion.search(matched_text)
                    for exclusion in self._exclusion_patterns
                ):
                    continue

                # Update max severity
                if severity_order.index(pii_pattern.severity) > severity_order.index(max_severity):
                    max_severity = pii_pattern.severity

                detections.append(
                    PIIMatch(
                        type=pii_pattern.type,
                        severity=pii_pattern.severity,
                        match=matched_text,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        pattern=pii_pattern.pattern,
                    )
                )

        has_pii = len(detections) > 0

        if not has_pii:
            return PIIDetectionResult(has_pii=False)

        # Build warning message
        context_str = f" in {context}" if context else ""
        type_counts: dict[str, int] = {}
        for d in detections:
            type_counts[d.type.value] = type_counts.get(d.type.value, 0) + 1

        type_summary = ", ".join(f"{count} {t}(s)" for t, count in type_counts.items())
        warning_message = (
            f"PII detected{context_str}: {type_summary}. "
            f"Severity: {max_severity.value}. "
            f"Review content before sending to external services."
        )

        # Log warning
        logger.warning(
            "PII detected in content",
            extra={
                "pii_types": list(type_counts.keys()),
                "severity": max_severity.value,
                "context": context,
            },
        )

        result = PIIDetectionResult(
            has_pii=True,
            detections=detections,
            severity=max_severity,
            warning_message=warning_message,
        )

        # Redact if mode is REDACT
        if self.mode == PIIMode.REDACT:
            result.redacted_text = self._redact(text, detections)

        return result

    def _redact(self, text: str, detections: list[PIIMatch]) -> str:
        """Redact PII from text.

        Args:
            text: Original text.
            detections: List of PII detections to redact.

        Returns:
            Text with PII redacted.
        """
        redacted = text
        # Sort detections by position in reverse order to preserve indices
        sorted_detections = sorted(detections, key=lambda d: d.start_pos, reverse=True)

        for detection in sorted_detections:
            replacement = f"[{detection.type.value.upper()}_REDACTED]"
            redacted = redacted[:detection.start_pos] + replacement + redacted[detection.end_pos:]

        return redacted

    def get_redaction_patterns(self) -> list[str]:
        """Get regex patterns for log redaction.

        Returns list of regex patterns that can be used for
        redacting PII in log messages.

        Returns:
            List of regex pattern strings.
        """
        return [p.pattern for p in self.PATTERNS if p.type in self.enabled_types]

    def is_blocked(self, result: PIIDetectionResult) -> bool:
        """Check if a detection result should trigger a block.

        Args:
            result: PII detection result.

        Returns:
            True if the request should be blocked.
        """
        if not result.has_pii:
            return False

        if self.mode == PIIMode.BLOCK:
            return True

        # Block if critical severity is detected
        if result.severity == PIISeverity.CRITICAL:
            return True

        return False


# Global detector instance
_detector: PIIDetector | None = None


def get_pii_detector(
    mode: PIIMode = PIIMode.WARN,
    min_severity: PIISeverity = PIISeverity.LOW,
) -> PIIDetector:
    """Get the global PII detector instance.

    Args:
        mode: Action mode (only applies on first call).
        min_severity: Minimum severity (only applies on first call).

    Returns:
        PIIDetector instance.
    """
    global _detector
    if _detector is None:
        _detector = PIIDetector(mode=mode, min_severity=min_severity)
    return _detector


def scan_for_pii(text: str, context: str | None = None) -> PIIDetectionResult:
    """Convenience function to scan text for PII.

    Args:
        text: Text to scan.
        context: Optional context string.

    Returns:
        PIIDetectionResult with detection details.
    """
    detector = get_pii_detector()
    return detector.scan(text, context=context)


def redact_pii(text: str) -> str:
    """Convenience function to redact PII from text.

    Always performs redaction regardless of global detector mode.

    Args:
        text: Text to redact.

    Returns:
        Text with PII redacted.
    """
    # Create a temporary detector in REDACT mode
    detector = PIIDetector(mode=PIIMode.REDACT)
    result = detector.scan(text)
    if result.has_pii:
        return result.redacted_text or text
    return text
