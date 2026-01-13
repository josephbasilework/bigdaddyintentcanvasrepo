"""Safety Guardrails with action classification for agent operations.

Provides:
- Action classification (safe, requires_approval, blocked)
- Tool-based action classification per PRD matrix (§13.1)
- Novel action handling for unknown tools
- Content filtering for agent outputs
- Prompt injection detection
- Rate limiting per user/agent
- Audit logging for security events
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ActionDomain(str, Enum):
    """Action domains per PRD §13.1 Action Classification Matrix."""

    CANVAS = "canvas"
    DOCUMENTS = "documents"
    JOBS = "jobs"
    MCP = "mcp"
    EXTERNAL = "external"


class ActionApproval(str, Enum):
    """Approval requirement levels per PRD §13.1."""

    SAFE = "safe"  # No confirmation required
    NEEDS_CONFIRM = "needs_confirm"  # Requires user approval
    BLOCKED = "blocked"  # Not allowed


class ActionRiskLevel(str, Enum):
    """Risk level classification for agent actions."""

    SAFE = "safe"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    BLOCKED = "blocked"


class ActionCategory(str, Enum):
    """Categories of agent actions."""

    READ_ONLY = "read_only"
    DATA_MUTATION = "data_mutation"
    EXTERNAL_API = "external_api"
    FILE_OPERATION = "file_operation"
    SYSTEM_COMMAND = "system_command"
    NETWORK_REQUEST = "network_request"
    DATA_EXPORT = "data_export"
    DESTRUCTIVE = "destructive"
    OTHER = "other"


@dataclass
class ActionClassification:
    """Classification result for an agent action."""

    risk_level: ActionRiskLevel
    category: ActionCategory
    reason: str
    requires_approval: bool = False
    confidence: float = 1.0
    patterns_matched: list[str] = field(default_factory=list)


class SafetyCheckResult(BaseModel):
    """Result from a safety check."""

    allowed: bool
    risk_level: ActionRiskLevel
    category: ActionCategory
    reason: str
    requires_approval: bool = False
    filtered_content: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ToolActionClassification(BaseModel):
    """Classification result for a tool action per PRD §13.1."""

    domain: ActionDomain
    approval: ActionApproval
    reason: str
    requires_approval: bool = False
    is_blocked: bool = False


class SecurityEvent(BaseModel):
    """Audit log entry for security events."""

    timestamp: datetime
    agent_name: str
    action_type: str
    risk_level: ActionRiskLevel
    allowed: bool
    reason: str
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InjectionSeverity(str, Enum):
    """Severity levels for injection detection."""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class InjectionCheckResult:
    """Result of prompt injection check with severity and threshold info."""

    is_suspicious: bool
    severity: InjectionSeverity
    matched_patterns: list[str]
    requires_hitl: bool
    warning_message: str | None
    confidence: float


class PromptInjectionDetector:
    """Detects potential prompt injection attempts."""

    # Patterns that suggest prompt injection
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above|earlier)\s+instructions",
        r"disregard\s+(all\s+)?(previous|above|earlier)\s+instructions",
        r"forget\s+(all\s+)?(previous|above|earlier)\s+instructions",
        r"override\s+(your\s+)?(programming|instructions|training)",
        r"jailbreak",
        r"act\s+as\s+(if\s+you\s+)?(a\s+)?(unrestricted|uncensored)",
        r"developer\s+mode",
        r"admin\s+mode",
        r"print\s+(your\s+)?(system\s+)?prompt",
        r"show\s+(your\s+)?(system\s+)?instructions",
        r"repeat\s+(the\s+)?(above|everything)",
        r"translate\s+.*\s+to\s+(base64|hex|binary)",
        r"<\|.*\|>",
        r"<<.*>>",
        r"\[SYSTEM\]",
        r"\[ADMIN\]",
        # More flexible patterns for common injections
        r"disregard\s+everything",
        r"ignore\s+everything",
        r"forget\s+everything",
        r"disregard\s+(all|everything)\s+above",
        r"ignore\s+(all|everything)\s+above",
        # Command execution patterns
        r"(?:exec|eval|executes|run|execute)\s+(?:this\s+)?(?:command|code|script)",
        r"system\s*\(",
        r"os\.system",
        r"subprocess",
        # Context manipulation patterns
        r"new\s+system\s+prompt",
        r"replace\s+(?:your\s+)?(?:system\s+)?instructions",
        r"from\s+now\s+on.*(?:you\s+)?(?:are|will|do)",
    ]

    # Severity mapping: pattern -> severity level
    PATTERN_SEVERITY = {
        r"ignore\s+(all\s+)?(previous|above|earlier)\s+instructions": InjectionSeverity.HIGH,
        r"disregard\s+(all\s+)?(previous|above|earlier)\s+instructions": InjectionSeverity.HIGH,
        r"forget\s+(all\s+)?(previous|above|earlier)\s+instructions": InjectionSeverity.HIGH,
        r"override\s+(your\s+)?(programming|instructions|training)": InjectionSeverity.HIGH,
        r"jailbreak": InjectionSeverity.CRITICAL,
        r"act\s+as\s+(if\s+you\s+)?(a\s+)?(unrestricted|uncensored)": InjectionSeverity.CRITICAL,
        r"developer\s+mode": InjectionSeverity.HIGH,
        r"admin\s+mode": InjectionSeverity.HIGH,
        r"print\s+(your\s+)?(system\s+)?prompt": InjectionSeverity.HIGH,
        r"show\s+(your\s+)?(system\s+)?instructions": InjectionSeverity.HIGH,
        r"repeat\s+(the\s+)?(above|everything)": InjectionSeverity.MEDIUM,
        r"translate\s+.*\s+to\s+(base64|hex|binary)": InjectionSeverity.MEDIUM,
        r"<\|.*\|>": InjectionSeverity.MEDIUM,
        r"<<.*>>": InjectionSeverity.MEDIUM,
        r"\[SYSTEM\]": InjectionSeverity.MEDIUM,
        r"\[ADMIN\]": InjectionSeverity.MEDIUM,
        r"disregard\s+everything": InjectionSeverity.HIGH,
        r"ignore\s+everything": InjectionSeverity.HIGH,
        r"forget\s+everything": InjectionSeverity.HIGH,
        r"disregard\s+(all|everything)\s+above": InjectionSeverity.HIGH,
        r"ignore\s+(all|everything)\s+above": InjectionSeverity.HIGH,
        r"(?:exec|eval|executes|run|execute)\s+(?:this\s+)?(?:command|code|script)": InjectionSeverity.CRITICAL,
        r"system\s*\(": InjectionSeverity.CRITICAL,
        r"os\.system": InjectionSeverity.CRITICAL,
        r"subprocess": InjectionSeverity.HIGH,
        r"new\s+system\s+prompt": InjectionSeverity.HIGH,
        r"replace\s+(?:your\s+)?(?:system\s+)?instructions": InjectionSeverity.HIGH,
        r"from\s+now\s+on.*(?:you\s+)?(?:are|will|do)": InjectionSeverity.MEDIUM,
    }

    def __init__(
        self,
        hitl_threshold: InjectionSeverity = InjectionSeverity.HIGH,
        max_patterns: int = 3,
    ) -> None:
        """Initialize the detector.

        Args:
            hitl_threshold: Severity level at which to trigger HITL gate.
            max_patterns: Maximum number of matched patterns before triggering HITL.
        """
        self.hitl_threshold = hitl_threshold
        self.max_patterns = max_patterns
        self.patterns = [
            re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for pattern in self.INJECTION_PATTERNS
        ]

    def detect(self, text: str) -> tuple[bool, list[str]]:
        """Detect potential prompt injection in text.

        Args:
            text: Text to analyze.

        Returns:
            Tuple of (is_suspicious, matched_patterns).
        """
        matched: list[str] = []
        for pattern in self.patterns:
            if pattern.search(text):
                matched.append(pattern.pattern)

        return len(matched) > 0, matched

    def check_with_threshold(self, text: str) -> InjectionCheckResult:
        """Check for injection with threshold-based HITL triggering.

        Args:
            text: Text to analyze.

        Returns:
            InjectionCheckResult with severity and HITL decision.
        """
        matched: list[tuple[str, InjectionSeverity]] = []
        for pattern in self.patterns:
            if pattern.search(text):
                severity = self.PATTERN_SEVERITY.get(pattern.pattern, InjectionSeverity.MEDIUM)
                matched.append((pattern.pattern, severity))

        if not matched:
            return InjectionCheckResult(
                is_suspicious=False,
                severity=InjectionSeverity.SAFE,
                matched_patterns=[],
                requires_hitl=False,
                warning_message=None,
                confidence=1.0,
            )

        # Determine overall severity (highest severity wins)
        max_severity = max(severity for _, severity in matched)

        # Determine if HITL is required
        highest_severity = InjectionSeverity(max_severity)
        threshold_order = [
            InjectionSeverity.SAFE,
            InjectionSeverity.LOW,
            InjectionSeverity.MEDIUM,
            InjectionSeverity.HIGH,
            InjectionSeverity.CRITICAL,
        ]
        threshold_idx = threshold_order.index(self.hitl_threshold)
        highest_idx = threshold_order.index(highest_severity)

        requires_hitl = highest_idx >= threshold_idx or len(matched) >= self.max_patterns

        # Build warning message
        warning_message: str | None = None
        if requires_hitl:
            pattern_strs = [p[0] for p in matched[:5]]  # Show first 5 patterns
            warning_message = (
                f"Potential prompt injection detected: {len(matched)} pattern(s) matched. "
                f"Severity: {highest_severity.value}. HITL gate triggered."
            )
            logger.warning(
                "Prompt injection detected",
                extra={
                    "severity": highest_severity.value,
                    "matched_patterns": pattern_strs,
                    "requires_hitl": True,
                },
            )

        return InjectionCheckResult(
            is_suspicious=True,
            severity=highest_severity,
            matched_patterns=[p[0] for p in matched],
            requires_hitl=requires_hitl,
            warning_message=warning_message,
            confidence=min(0.5 + (len(matched) * 0.1), 0.95),  # Confidence increases with more matches
        )

    def sanitize(self, text: str, max_length: int = 10000) -> str:
        """Sanitize text by limiting length and removing null bytes.

        Args:
            text: Text to sanitize.
            max_length: Maximum allowed length.

        Returns:
            Sanitized text.
        """
        # Remove null bytes and other control characters
        sanitized = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "... [truncated]"
        return sanitized


class ContentFilter:
    """Filters potentially harmful content from agent outputs."""

    # Patterns for sensitive information (basic detection)
    SENSITIVE_PATTERNS = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "EMAIL"),
        (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "PHONE"),
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "CREDIT_CARD"),
        (r"\b(?:API|SECRET|TOKEN|PASSWORD|KEY|API_KEY|SECRET_KEY|ACCESS_TOKEN)\s*[:=]\s*\S+", "CREDENTIAL"),
    ]

    def __init__(self) -> None:
        """Initialize the content filter."""
        self.patterns = [
            (re.compile(pattern, re.IGNORECASE), label)
            for pattern, label in self.SENSITIVE_PATTERNS
        ]

    def filter(self, text: str, redact: bool = True) -> tuple[str, list[str]]:
        """Filter sensitive content from text.

        Args:
            text: Text to filter.
            redact: If True, replace matches with [REDACTED].

        Returns:
            Tuple of (filtered_text, list of detected_labels).
        """
        result = text
        detected: set[str] = set()

        for pattern, label in self.patterns:
            matches = pattern.findall(result)
            if matches:
                detected.add(label)
                if redact:
                    result = pattern.sub(f"[{label}_REDACTED]", result)

        return result, list(detected)


class RateLimiter:
    """Rate limiter for agent execution."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute.
            requests_per_hour: Maximum requests per hour.
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self._requests: dict[str, list[datetime]] = {}
        self._lock = asyncio.Lock()

    async def check_limit(
        self, key: str, window: timedelta = timedelta(minutes=1)
    ) -> tuple[bool, int]:
        """Check if a request is within rate limits.

        Args:
            key: Identifier for rate limiting (user_id, agent_name, etc.).
            window: Time window to check.

        Returns:
            Tuple of (allowed, request_count).
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - window

            # Get or initialize request history
            if key not in self._requests:
                self._requests[key] = []

            # Filter old requests
            self._requests[key] = [
                ts for ts in self._requests[key] if ts > cutoff
            ]

            count = len(self._requests[key])

            # Determine limit based on window
            if window <= timedelta(minutes=1):
                limit = self.requests_per_minute
            else:
                limit = self.requests_per_hour

            allowed = count < limit

            if allowed:
                self._requests[key].append(now)
                count += 1  # Update count to reflect the new request

            return allowed, count

    def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Identifier to reset.
        """
        self._requests.pop(key, None)


class SafetyGuardrails:
    """Main safety guardrails system for agent operations."""

    def __init__(self) -> None:
        """Initialize the safety guardrails."""
        self.injection_detector = PromptInjectionDetector()
        self.content_filter = ContentFilter()
        self.rate_limiter = RateLimiter()
        self._audit_log: list[SecurityEvent] = []

        # Define action classification rules
        self._action_rules: dict[ActionCategory, ActionRiskLevel] = {
            ActionCategory.READ_ONLY: ActionRiskLevel.SAFE,
            ActionCategory.DATA_MUTATION: ActionRiskLevel.MEDIUM_RISK,
            ActionCategory.EXTERNAL_API: ActionRiskLevel.LOW_RISK,
            ActionCategory.FILE_OPERATION: ActionRiskLevel.MEDIUM_RISK,
            ActionCategory.SYSTEM_COMMAND: ActionRiskLevel.HIGH_RISK,
            ActionCategory.NETWORK_REQUEST: ActionRiskLevel.LOW_RISK,
            ActionCategory.DATA_EXPORT: ActionRiskLevel.MEDIUM_RISK,
            ActionCategory.DESTRUCTIVE: ActionRiskLevel.BLOCKED,
            ActionCategory.OTHER: ActionRiskLevel.LOW_RISK,
        }

        # PRD §13.1 Action Classification Matrix
        # Maps domain actions to approval requirements
        self._tool_action_matrix: dict[ActionDomain, dict[str, ActionApproval]] = {
            ActionDomain.CANVAS: {
                "create_node": ActionApproval.SAFE,
                "update_label": ActionApproval.SAFE,
                "move": ActionApproval.SAFE,
                "update_node": ActionApproval.SAFE,
                "delete_node": ActionApproval.NEEDS_CONFIRM,
                "clear_canvas": ActionApproval.NEEDS_CONFIRM,
            },
            ActionDomain.DOCUMENTS: {
                "create": ActionApproval.SAFE,
                "update": ActionApproval.SAFE,
                "delete": ActionApproval.NEEDS_CONFIRM,
            },
            ActionDomain.JOBS: {
                "create": ActionApproval.SAFE,
                "query": ActionApproval.SAFE,
                "cancel": ActionApproval.NEEDS_CONFIRM,
                "delete_history": ActionApproval.NEEDS_CONFIRM,
            },
            ActionDomain.MCP: {
                "query_": ActionApproval.SAFE,  # Prefix match for query_*
                "write_": ActionApproval.NEEDS_CONFIRM,
                "send_": ActionApproval.NEEDS_CONFIRM,
                "configure_global": ActionApproval.BLOCKED,
            },
            ActionDomain.EXTERNAL: {
                "calendar_create": ActionApproval.NEEDS_CONFIRM,
                "email_draft": ActionApproval.NEEDS_CONFIRM,
                "email_send_bulk": ActionApproval.BLOCKED,
                "email_send": ActionApproval.NEEDS_CONFIRM,
            },
        }

        # Verbs that suggest dangerous actions for novel action handling
        self._dangerous_verbs = {
            "delete",
            "remove",
            "clear",
            "send",
            "upload",
            "destroy",
            "drop",
            "truncate",
        }

        # Targets that suggest dangerous actions
        self._dangerous_targets = {
            "system",
            "config",
            "external",
            "global",
            "admin",
            "root",
        }

    def classify_action(
        self,
        agent_name: str,
        input_data: dict[str, Any],
    ) -> ActionClassification:
        """Classify an agent action by risk level and category.

        Args:
            agent_name: Name of the agent.
            input_data: Input data for the agent.

        Returns:
            ActionClassification with risk assessment.
        """
        # Determine category from agent name and input
        category = self._determine_category(agent_name, input_data)

        # Get base risk level
        risk_level = self._action_rules.get(category, ActionRiskLevel.LOW_RISK)

        # Check for prompt injection with threshold-based HITL
        text_input = str(input_data.get("text", ""))
        injection_result = self.injection_detector.check_with_threshold(text_input)

        if injection_result.is_suspicious:
            # Map injection severity to risk level
            severity_to_risk = {
                InjectionSeverity.LOW: ActionRiskLevel.LOW_RISK,
                InjectionSeverity.MEDIUM: ActionRiskLevel.MEDIUM_RISK,
                InjectionSeverity.HIGH: ActionRiskLevel.BLOCKED,
                InjectionSeverity.CRITICAL: ActionRiskLevel.BLOCKED,
            }
            risk_level = severity_to_risk.get(
                injection_result.severity, ActionRiskLevel.MEDIUM_RISK
            )
            return ActionClassification(
                risk_level=risk_level,
                category=category,
                reason=injection_result.warning_message or "Potential prompt injection detected",
                requires_approval=injection_result.requires_hitl,
                confidence=injection_result.confidence,
                patterns_matched=injection_result.matched_patterns,
            )

        # Check for suspicious patterns in input
        suspicious = self._check_suspicious_patterns(input_data)
        if suspicious and risk_level == ActionRiskLevel.SAFE:
            risk_level = ActionRiskLevel.MEDIUM_RISK

        requires_approval = risk_level in (
            ActionRiskLevel.MEDIUM_RISK,
            ActionRiskLevel.HIGH_RISK,
        )

        return ActionClassification(
            risk_level=risk_level,
            category=category,
            reason=f"Action classified as {risk_level.value}",
            requires_approval=requires_approval,
            patterns_matched=[],
        )

    def _determine_category(
        self, agent_name: str, input_data: dict[str, Any]
    ) -> ActionCategory:
        """Determine the action category from agent and input.

        Args:
            agent_name: Name of the agent.
            input_data: Input data.

        Returns:
            ActionCategory for the action.
        """
        name_lower = agent_name.lower()

        # Check for destructive operations
        if any(
            x in name_lower
            for x in ["delete", "destroy", "drop", "truncate", "remove"]
        ):
            return ActionCategory.DESTRUCTIVE

        # Check for system commands
        if any(x in name_lower for x in ["exec", "command", "shell", "system"]):
            return ActionCategory.SYSTEM_COMMAND

        # Check for file operations
        if any(x in name_lower for x in ["file", "write", "upload", "download"]):
            return ActionCategory.FILE_OPERATION

        # Check for data mutations
        if any(
            x in name_lower
            for x in ["create", "update", "modify", "change", "store", "save"]
        ):
            return ActionCategory.DATA_MUTATION

        # Check for data export
        if any(x in name_lower for x in ["export", "report", "dump"]):
            return ActionCategory.DATA_EXPORT

        # Check for external API calls
        if any(
            x in name_lower for x in ["api", "fetch", "request", "calendar", "mcp"]
        ):
            return ActionCategory.EXTERNAL_API

        # Check for network requests
        if any(x in name_lower for x in ["http", "url", "download", "fetch"]):
            return ActionCategory.NETWORK_REQUEST

        # Default to read-only
        return ActionCategory.READ_ONLY

    def _check_suspicious_patterns(self, input_data: dict[str, Any]) -> bool:
        """Check for suspicious patterns in input data.

        Args:
            input_data: Input data to check.

        Returns:
            True if suspicious patterns found.
        """
        text = str(input_data.get("text", ""))

        # Check for very long inputs (potential DoS)
        if len(text) > 50000:
            return True

        # Check for excessive special characters
        special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace())
        if len(text) > 0 and special_char_ratio / len(text) > 0.5:
            return True

        return False

    def classify_tool_action(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> ToolActionClassification:
        """Classify a tool action using the PRD §13.1 Action Classification Matrix.

        Args:
            tool_name: Name of the tool being called (e.g., "canvas.create_node").
            arguments: Optional tool arguments for context.

        Returns:
            ToolActionClassification with domain and approval requirement.
        """
        # Parse the tool name to extract domain and action
        domain = self._parse_tool_domain(tool_name)
        action = self._extract_action_name(tool_name)

        # Look up in the matrix
        if domain in self._tool_action_matrix:
            domain_actions = self._tool_action_matrix[domain]

            # Check for exact match first
            if action in domain_actions:
                approval = domain_actions[action]
                return ToolActionClassification(
                    domain=domain,
                    approval=approval,
                    reason=f"Tool '{tool_name}' found in {domain.value} matrix",
                    requires_approval=approval == ActionApproval.NEEDS_CONFIRM,
                    is_blocked=approval == ActionApproval.BLOCKED,
                )

            # Check for prefix matches (e.g., "query_" for MCP)
            for matrix_action, matrix_approval in domain_actions.items():
                if matrix_action.endswith("_") and action.startswith(matrix_action):
                    return ToolActionClassification(
                        domain=domain,
                        approval=matrix_approval,
                        reason=f"Tool '{tool_name}' matches prefix '{matrix_action}' in {domain.value} matrix",
                        requires_approval=matrix_approval == ActionApproval.NEEDS_CONFIRM,
                        is_blocked=matrix_approval == ActionApproval.BLOCKED,
                    )

        # Not found in matrix - use novel action handling (PRD §13.2)
        return self._classify_novel_action(tool_name, action, domain)

    def _parse_tool_domain(self, tool_name: str) -> ActionDomain:
        """Extract the domain from a tool name.

        Args:
            tool_name: Full tool name (e.g., "canvas.create_node", "mcp.query_calendar").

        Returns:
            ActionDomain for the tool.
        """
        tool_lower = tool_name.lower()

        # Check for domain prefixes
        if tool_lower.startswith("canvas."):
            return ActionDomain.CANVAS
        if tool_lower.startswith("document") or "_document" in tool_lower:
            return ActionDomain.DOCUMENTS
        if tool_lower.startswith("job") or "_job" in tool_lower:
            return ActionDomain.JOBS
        if tool_lower.startswith("mcp.") or tool_lower.startswith("mcp_"):
            return ActionDomain.MCP

        # Check for external integrations
        for external_keyword in ["calendar", "email", "slack", "notion", "github"]:
            if external_keyword in tool_lower:
                return ActionDomain.EXTERNAL

        # Default to canvas for unknown tools
        return ActionDomain.CANVAS

    def _extract_action_name(self, tool_name: str) -> str:
        """Extract the action name from a tool name.

        Args:
            tool_name: Full tool name (e.g., "canvas.create_node").

        Returns:
            Action name (e.g., "create_node").
        """
        # Remove domain prefix if present
        if "." in tool_name:
            return tool_name.split(".", 1)[1].lower()
        return tool_name.lower()

    def _classify_novel_action(
        self, tool_name: str, action: str, domain: ActionDomain
    ) -> ToolActionClassification:
        """Classify a novel action not in the matrix using PRD §13.2 rules.

        Args:
            tool_name: Full tool name.
            action: Extracted action name.
            domain: Inferred domain.

        Returns:
            ToolActionClassification for the novel action.
        """
        action_lower = action.lower()
        tool_lower = tool_name.lower()

        # Extract verb (first word before underscore or the whole action)
        verb = action_lower.split("_")[0] if "_" in action_lower else action_lower

        # PRD §13.2 Rule 1: If verb in dangerous set → Needs Confirm
        if verb in self._dangerous_verbs:
            return ToolActionClassification(
                domain=domain,
                approval=ActionApproval.NEEDS_CONFIRM,
                reason=f"Novel action '{tool_name}': verb '{verb}' requires confirmation",
                requires_approval=True,
                is_blocked=False,
            )

        # PRD §13.2 Rule 2: If target in dangerous set → Needs Confirm
        for target in self._dangerous_targets:
            if target in tool_lower or target in action_lower:
                return ToolActionClassification(
                    domain=domain,
                    approval=ActionApproval.NEEDS_CONFIRM,
                    reason=f"Novel action '{tool_name}': target '{target}' requires confirmation",
                    requires_approval=True,
                    is_blocked=False,
                )

        # PRD §13.2 Rule 3: Default to Safe
        return ToolActionClassification(
            domain=domain,
            approval=ActionApproval.SAFE,
            reason=f"Novel action '{tool_name}': defaulting to safe",
            requires_approval=False,
            is_blocked=False,
        )

    async def check_safety(
        self,
        agent_name: str,
        input_data: dict[str, Any],
        user_id: str | None = None,
    ) -> SafetyCheckResult:
        """Perform comprehensive safety check before agent execution.

        Args:
            agent_name: Name of the agent to execute.
            input_data: Input data for the agent.
            user_id: Optional user identifier for rate limiting.

        Returns:
            SafetyCheckResult with determination.
        """
        warnings: list[str] = []

        # Classify the action
        classification = self.classify_action(agent_name, input_data)

        # Check rate limits
        if user_id:
            rate_key = f"{user_id}:{agent_name}"
            allowed, count = await self.rate_limiter.check_limit(rate_key)
            if not allowed:
                return SafetyCheckResult(
                    allowed=False,
                    risk_level=ActionRiskLevel.HIGH_RISK,
                    category=classification.category,
                    reason=f"Rate limit exceeded: {count} requests",
                    requires_approval=False,
                    warnings=["Rate limit exceeded"],
                )
            warnings.append(f"Rate limit: {count} requests")

        # Check if blocked
        if classification.risk_level == ActionRiskLevel.BLOCKED:
            self._log_event(
                SecurityEvent(
                    timestamp=datetime.now(),
                    agent_name=agent_name,
                    action_type="execute",
                    risk_level=classification.risk_level,
                    allowed=False,
                    reason=classification.reason,
                    user_id=user_id,
                    metadata={"patterns": classification.patterns_matched},
                )
            )
            return SafetyCheckResult(
                allowed=False,
                risk_level=classification.risk_level,
                category=classification.category,
                reason=classification.reason,
                requires_approval=False,
                warnings=warnings,
            )

        # Sanitize input
        text_input = input_data.get("text", "")
        if isinstance(text_input, str):
            input_data["text"] = self.injection_detector.sanitize(text_input)

        return SafetyCheckResult(
            allowed=True,
            risk_level=classification.risk_level,
            category=classification.category,
            reason=classification.reason,
            requires_approval=classification.requires_approval,
            warnings=warnings,
        )

    def filter_output(self, text: str, redact: bool = True) -> SafetyCheckResult:
        """Filter agent output for sensitive content.

        Args:
            text: Output text to filter.
            redact: If True, redact sensitive content.

        Returns:
            SafetyCheckResult with filtered content.
        """
        filtered, detected = self.content_filter.filter(text, redact=redact)

        return SafetyCheckResult(
            allowed=True,
            risk_level=ActionRiskLevel.SAFE,
            category=ActionCategory.OTHER,
            reason="Content filtered",
            requires_approval=False,
            filtered_content=filtered,
            warnings=[f"Detected: {', '.join(detected)}"] if detected else [],
        )

    def log_approval_event(
        self,
        session_id: str,
        assumption_id: str,
        action: str,
        category: str,
        original_text: str,
        final_text: str,
        feedback: str | None = None,
        source: str = "assumption_store",
    ) -> None:
        """Log a HITL approval decision to the audit log."""
        metadata = {
            "session_id": session_id,
            "assumption_id": assumption_id,
            "action": action,
            "category": category,
            "source": source,
            "edited": action == "edit",
            "has_feedback": bool(feedback),
            "original_text_length": len(original_text),
            "final_text_length": len(final_text),
        }
        event = SecurityEvent(
            timestamp=datetime.now(),
            agent_name="hitl",
            action_type="approval",
            risk_level=ActionRiskLevel.MEDIUM_RISK,
            allowed=action != "reject",
            reason=f"HITL approval {action}",
            metadata=metadata,
        )
        self._log_event(event)

    def _log_event(self, event: SecurityEvent) -> None:
        """Log a security event to the audit log.

        Args:
            event: Security event to log.
        """
        self._audit_log.append(event)

        # Keep log size manageable
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]

        logger.info(
            "Security event logged",
            extra={
                "agent": event.agent_name,
                "risk_level": event.risk_level,
                "allowed": event.allowed,
            },
        )

    def get_audit_log(
        self,
        agent_name: str | None = None,
        min_risk_level: ActionRiskLevel = ActionRiskLevel.MEDIUM_RISK,
        limit: int = 100,
    ) -> list[SecurityEvent]:
        """Get audit log entries.

        Args:
            agent_name: Optional agent filter.
            min_risk_level: Minimum risk level to include.
            limit: Maximum number of entries.

        Returns:
            List of SecurityEvent.
        """
        events = self._audit_log

        if agent_name:
            events = [e for e in events if e.agent_name == agent_name]

        # Define risk level ordering
        risk_order = [
            ActionRiskLevel.SAFE,
            ActionRiskLevel.LOW_RISK,
            ActionRiskLevel.MEDIUM_RISK,
            ActionRiskLevel.HIGH_RISK,
            ActionRiskLevel.BLOCKED,
        ]

        min_idx = risk_order.index(min_risk_level)
        events = [
            e
            for e in events
            if risk_order.index(e.risk_level) >= min_idx
        ]

        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]


# Global safety instance
_safety: SafetyGuardrails | None = None


def get_safety() -> SafetyGuardrails:
    """Get the global safety guardrails instance.

    Returns:
        SafetyGuardrails instance.
    """
    global _safety
    if _safety is None:
        _safety = SafetyGuardrails()
    return _safety
