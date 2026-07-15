"""
static_analysis.py — Pattern-based static analysis for Solidity smart contracts.

This module provides a pure-Python static analyzer that uses regex-based
pattern matching to detect common vulnerability patterns in Solidity source
code. It does NOT depend on any external tools (e.g., Slither, Mythril).

Detected vulnerability classes:
    SCA-001  Reentrancy
    SCA-002  Unchecked Return Values
    SCA-003  tx.origin Authentication
    SCA-004  Unprotected selfdestruct
    SCA-005  Floating Pragma
    SCA-006  Unsafe Arithmetic (pre-0.8.0)
    SCA-007  Delegatecall to User Input
    SCA-008  Unbounded Loops
    SCA-009  Missing Access Control
    SCA-010  Hardcoded Addresses

Usage:
    >>> analyzer = StaticAnalyzer()
    >>> findings = analyzer.analyze(solidity_source_code)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Location:
    """Source-code location for a finding."""

    line_number: int
    code_snippet: str

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {"line_number": self.line_number, "code_snippet": self.code_snippet}


@dataclass
class Finding:
    """A single vulnerability finding produced by the static analyser."""

    id: str
    title: str
    severity: str
    category: str
    description: str
    location: Location
    recommendation: str

    def to_dict(self) -> dict:
        """Serialise to the canonical dict schema expected by callers."""
        data = asdict(self)
        data["location"] = self.location.to_dict()
        return data


# ---------------------------------------------------------------------------
# Compiled regex patterns (module-level constants for performance)
# ---------------------------------------------------------------------------

# Matches `.call{...}(`, `.call(`, `.send(`, `.transfer(`
_RE_EXTERNAL_CALL = re.compile(
    r"\.\s*(?:call\s*(?:\{[^}]*\})?\s*\(|send\s*\(|transfer\s*\()", re.MULTILINE
)

# Matches state-variable assignment  `varName = ...;`  or `varName += ...;`
_RE_STATE_ASSIGNMENT = re.compile(
    r"^\s*\w+\s*(?:\[.*?\])?\s*(?:=|\+=|-=|\*=|/=)\s*", re.MULTILINE
)

# NOTE: Unchecked-call detection is handled line-by-line in
# _check_unchecked_return() rather than via a single compiled regex,
# because variable-width lookbehinds are not supported in Python ≥3.13.

# `tx.origin` inside a conditional / require
_RE_TX_ORIGIN = re.compile(r"\btx\.origin\b", re.MULTILINE)

# selfdestruct / suicide
_RE_SELFDESTRUCT = re.compile(r"\b(?:selfdestruct|suicide)\s*\(", re.MULTILINE)

# Floating pragma
_RE_FLOATING_PRAGMA = re.compile(
    r"pragma\s+solidity\s+[\^~>=<]*\s*\d+\.\d+\.\d+", re.MULTILINE
)
_RE_LOCKED_PRAGMA = re.compile(
    r"pragma\s+solidity\s+(\d+\.\d+\.\d+)\s*;", re.MULTILINE
)

# Pragma version extraction
_RE_PRAGMA_VERSION = re.compile(
    r"pragma\s+solidity\s+[\^~>=<\s]*(\d+)\.(\d+)\.(\d+)", re.MULTILINE
)

# Arithmetic operators (for pre-0.8 contracts)
_RE_ARITHMETIC = re.compile(r"[^=!<>/*+\-]\s*(\+|-|\*|/)\s*[^=*/]", re.MULTILINE)

# SafeMath usage
_RE_SAFEMATH = re.compile(r"\busing\s+SafeMath\b", re.MULTILINE)

# delegatecall
_RE_DELEGATECALL = re.compile(r"\.delegatecall\s*\(", re.MULTILINE)

# For / while loops over dynamic array `.length`
_RE_UNBOUNDED_LOOP = re.compile(
    r"\b(?:for|while)\s*\(.*?\.length\b", re.MULTILINE | re.DOTALL
)

# Public / external function declarations
_RE_FUNCTION_DECL = re.compile(
    r"\bfunction\s+(\w+)\s*\([^)]*\)\s*((?:public|external)[\s\w]*)\s*(?:returns\s*\([^)]*\)\s*)?\{",
    re.MULTILINE,
)

# Access-control modifiers commonly found after visibility keyword
_RE_ACCESS_MODIFIERS = re.compile(
    r"\b(?:onlyOwner|onlyAdmin|onlyRole|onlyMinter|onlyGovernance|onlyAuthorized|"
    r"auth|restricted|whenNotPaused|initializer|nonReentrant)\b",
    re.MULTILINE,
)

# `require(msg.sender` or `if (msg.sender` access checks
_RE_MSG_SENDER_CHECK = re.compile(
    r"(?:require|if)\s*\(\s*msg\.sender\b", re.MULTILINE
)

# Hardcoded Ethereum addresses (0x followed by 40 hex chars)
_RE_ETH_ADDRESS = re.compile(r"\b0x[0-9a-fA-F]{40}\b")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _lines(source: str) -> list[str]:
    """Split source into lines, preserving 1-based indexing semantics."""
    return source.splitlines()


def _snippet(line: str, max_len: int = 120) -> str:
    """Return a trimmed code snippet for display, capped at *max_len* chars."""
    stripped = line.strip()
    if len(stripped) <= max_len:
        return stripped
    return stripped[: max_len - 3] + "..."


def _extract_function_body(source: str, func_start_line: int, lines: list[str]) -> str:
    """Extract the body of a function starting at *func_start_line* (0-based).

    Uses a simple brace-depth counter to find the matching closing ``}``.
    Returns the full text of the function body (including braces).
    """
    depth = 0
    body_lines: list[str] = []
    started = False

    for i in range(func_start_line, len(lines)):
        line = lines[i]
        for ch in line:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
        body_lines.append(line)
        if started and depth <= 0:
            break

    return "\n".join(body_lines)


# ---------------------------------------------------------------------------
# StaticAnalyzer
# ---------------------------------------------------------------------------

class StaticAnalyzer:
    """Pure-Python pattern-based static analyser for Solidity source code.

    Usage::

        analyzer = StaticAnalyzer()
        findings = analyzer.analyze(source_code)

    Each element of *findings* is a ``dict`` conforming to the finding schema
    (see :class:`Finding`).
    """

    def analyze(self, source_code: str) -> list[dict]:
        """Run all vulnerability checks against *source_code*.

        Args:
            source_code: Raw Solidity source code as a single string.

        Returns:
            A list of finding dictionaries ordered by line number.
        """
        lines = _lines(source_code)
        findings: list[Finding] = []

        findings.extend(self._check_reentrancy(source_code, lines))
        findings.extend(self._check_unchecked_return(source_code, lines))
        findings.extend(self._check_tx_origin(source_code, lines))
        findings.extend(self._check_unprotected_selfdestruct(source_code, lines))
        findings.extend(self._check_floating_pragma(source_code, lines))
        findings.extend(self._check_unsafe_arithmetic(source_code, lines))
        findings.extend(self._check_delegatecall(source_code, lines))
        findings.extend(self._check_unbounded_loops(source_code, lines))
        findings.extend(self._check_missing_access_control(source_code, lines))
        findings.extend(self._check_hardcoded_addresses(source_code, lines))

        # Sort by line number for deterministic, readable output
        findings.sort(key=lambda f: f.location.line_number)
        return [f.to_dict() for f in findings]

    # ------------------------------------------------------------------
    # SCA-001 — Reentrancy
    # ------------------------------------------------------------------

    def _check_reentrancy(self, source: str, lines: list[str]) -> list[Finding]:
        """Detect external calls that precede state-variable updates.

        The classic reentrancy pattern is:
            1. External call (`.call`, `.send`, `.transfer`)
            2. State variable mutation *after* the call

        This detector scans each function body for that ordering.
        """
        findings: list[Finding] = []
        func_matches = list(_RE_FUNCTION_DECL.finditer(source))

        for func_match in func_matches:
            func_name = func_match.group(1)
            func_start_offset = func_match.start()
            # Determine the 0-based line index of the function start
            func_start_line = source[:func_start_offset].count("\n")
            body_text = _extract_function_body(source, func_start_line, lines)
            body_lines = body_text.splitlines()

            # Locate external calls and state assignments within the body
            ext_call_line_offsets: list[int] = []
            state_assign_line_offsets: list[int] = []

            for offset, bline in enumerate(body_lines):
                if _RE_EXTERNAL_CALL.search(bline):
                    ext_call_line_offsets.append(offset)
                if _RE_STATE_ASSIGNMENT.search(bline) and not bline.strip().startswith(
                    ("uint", "int", "bool", "address", "string", "bytes", "mapping", "//", "/*", "*")
                ):
                    state_assign_line_offsets.append(offset)

            # Flag if any state assignment follows an external call
            for call_offset in ext_call_line_offsets:
                for assign_offset in state_assign_line_offsets:
                    if assign_offset > call_offset:
                        line_no = func_start_line + call_offset + 1  # 1-based
                        code = _snippet(body_lines[call_offset])
                        findings.append(
                            Finding(
                                id="SCA-001",
                                title="Reentrancy Vulnerability",
                                severity="CRITICAL",
                                category="Reentrancy",
                                description=(
                                    f"Function `{func_name}` performs an external call "
                                    f"before updating state variables. An attacker can "
                                    f"re-enter the function and exploit the stale state."
                                ),
                                location=Location(line_number=line_no, code_snippet=code),
                                recommendation=(
                                    "Apply the checks-effects-interactions pattern: "
                                    "update all state variables before making external "
                                    "calls. Consider using OpenZeppelin's ReentrancyGuard."
                                ),
                            )
                        )
                        break  # one finding per external call is enough

        return findings

    # ------------------------------------------------------------------
    # SCA-002 — Unchecked Return Values
    # ------------------------------------------------------------------

    def _check_unchecked_return(self, source: str, lines: list[str]) -> list[Finding]:
        """Detect ``.call()`` invocations whose boolean return value is not checked."""
        findings: list[Finding] = []

        for line_idx, line in enumerate(lines, start=1):
            if ".call" not in line:
                continue

            # Skip lines that already check the return value
            stripped = line.strip()
            if stripped.startswith(("require", "if", "assert", "(bool")):
                continue
            # Check for `(bool success,` or `(bool ok` captures
            if re.search(r"\(\s*bool\s+\w+", stripped):
                continue
            # Check for require/if on the same line wrapping the call
            if re.search(r"(?:require|if|assert)\s*\(.*\.call", stripped):
                continue

            if _RE_EXTERNAL_CALL.search(line):
                findings.append(
                    Finding(
                        id="SCA-002",
                        title="Unchecked Return Value",
                        severity="HIGH",
                        category="Unchecked Low-Level Call",
                        description=(
                            "The return value of a low-level `.call()` is not checked. "
                            "If the call fails silently, the contract will continue "
                            "execution with incorrect assumptions."
                        ),
                        location=Location(line_number=line_idx, code_snippet=_snippet(stripped)),
                        recommendation=(
                            "Always check the boolean success value returned by "
                            "`.call()`. Use `require(success, ...)` or handle the "
                            "failure explicitly."
                        ),
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # SCA-003 — tx.origin Authentication
    # ------------------------------------------------------------------

    def _check_tx_origin(self, source: str, lines: list[str]) -> list[Finding]:
        """Detect use of ``tx.origin`` for authentication/authorisation checks."""
        findings: list[Finding] = []

        for line_idx, line in enumerate(lines, start=1):
            if "tx.origin" not in line:
                continue

            stripped = line.strip()
            # Only flag when used in a conditional / require context
            if re.search(r"(?:require|if|assert)\s*\(.*\btx\.origin\b", stripped):
                findings.append(
                    Finding(
                        id="SCA-003",
                        title="tx.origin Used for Authentication",
                        severity="HIGH",
                        category="Access Control",
                        description=(
                            "`tx.origin` is used in an authorisation check. "
                            "A malicious contract can trick a user into calling it, "
                            "and then forward the call to this contract, passing the "
                            "`tx.origin` check (phishing attack)."
                        ),
                        location=Location(line_number=line_idx, code_snippet=_snippet(stripped)),
                        recommendation=(
                            "Replace `tx.origin` with `msg.sender` for access control. "
                            "`msg.sender` represents the immediate caller and cannot be "
                            "spoofed through intermediary contracts."
                        ),
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # SCA-004 — Unprotected selfdestruct
    # ------------------------------------------------------------------

    def _check_unprotected_selfdestruct(
        self, source: str, lines: list[str]
    ) -> list[Finding]:
        """Detect ``selfdestruct`` / ``suicide`` calls without access control."""
        findings: list[Finding] = []
        func_matches = list(_RE_FUNCTION_DECL.finditer(source))

        for func_match in func_matches:
            func_name = func_match.group(1)
            modifiers_area = func_match.group(2)
            func_start_offset = func_match.start()
            func_start_line = source[:func_start_offset].count("\n")
            body_text = _extract_function_body(source, func_start_line, lines)

            if not _RE_SELFDESTRUCT.search(body_text):
                continue

            # Check for access-control modifiers in the declaration
            has_modifier = bool(_RE_ACCESS_MODIFIERS.search(modifiers_area))
            # Check for msg.sender require/if inside the body
            has_sender_check = bool(_RE_MSG_SENDER_CHECK.search(body_text))

            if has_modifier or has_sender_check:
                continue

            # Find the exact line with selfdestruct
            for offset, bline in enumerate(body_text.splitlines()):
                if _RE_SELFDESTRUCT.search(bline):
                    line_no = func_start_line + offset + 1
                    findings.append(
                        Finding(
                            id="SCA-004",
                            title="Unprotected selfdestruct",
                            severity="CRITICAL",
                            category="Access Control",
                            description=(
                                f"Function `{func_name}` contains a `selfdestruct` "
                                f"call with no access control. Anyone can destroy "
                                f"this contract and drain its Ether balance."
                            ),
                            location=Location(
                                line_number=line_no,
                                code_snippet=_snippet(bline),
                            ),
                            recommendation=(
                                "Restrict `selfdestruct` behind an `onlyOwner` "
                                "modifier or a `require(msg.sender == owner)` check. "
                                "Consider removing `selfdestruct` entirely as it is "
                                "deprecated after the Dencun upgrade."
                            ),
                        )
                    )
                    break

        return findings

    # ------------------------------------------------------------------
    # SCA-005 — Floating Pragma
    # ------------------------------------------------------------------

    def _check_floating_pragma(self, source: str, lines: list[str]) -> list[Finding]:
        """Detect floating (unlocked) pragma directives."""
        findings: list[Finding] = []

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped.startswith("pragma solidity"):
                continue

            # A locked pragma has exactly one version, no range operators
            if _RE_LOCKED_PRAGMA.match(stripped):
                continue  # Properly locked — no issue

            # If it contains ^, ~, >=, >, <, <=  it is floating
            if re.search(r"[\^~]|>=|<=|>|<", stripped):
                findings.append(
                    Finding(
                        id="SCA-005",
                        title="Floating Pragma",
                        severity="LOW",
                        category="Best Practices",
                        description=(
                            "The pragma directive does not lock the compiler version. "
                            "Contracts should be deployed with the same compiler "
                            "version they were tested with."
                        ),
                        location=Location(line_number=line_idx, code_snippet=_snippet(stripped)),
                        recommendation=(
                            "Lock the pragma to a specific version, e.g. "
                            "`pragma solidity 0.8.20;` instead of `pragma solidity ^0.8.20;`."
                        ),
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # SCA-006 — Unsafe Arithmetic (pre-0.8.0)
    # ------------------------------------------------------------------

    def _check_unsafe_arithmetic(
        self, source: str, lines: list[str]
    ) -> list[Finding]:
        """Detect arithmetic operations in pre-0.8.0 contracts without SafeMath."""
        findings: list[Finding] = []

        # Determine the pragma version
        version_match = _RE_PRAGMA_VERSION.search(source)
        if not version_match:
            return findings

        major = int(version_match.group(1))
        minor = int(version_match.group(2))

        # Solidity >=0.8.0 has built-in overflow checks
        if (major, minor) >= (0, 8):
            return findings

        # Check if SafeMath is used
        if _RE_SAFEMATH.search(source):
            return findings

        # Flag arithmetic operations
        arithmetic_ops = re.compile(
            r"(?<!=)\s*(\+|\-|\*)\s*(?!=)", re.MULTILINE
        )

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Skip comments, pragmas, imports, and string literals
            if stripped.startswith(("//", "/*", "*", "pragma", "import", '"', "'")):
                continue
            # Skip increment/decrement operators (++, --, +=, -=)
            cleaned = re.sub(r"\+\+|--|\+=|-=|\*=|/=", "", stripped)
            # Skip lines that are pure declarations
            if re.match(r"^\s*(?:uint|int|mapping|address|bool|string|bytes)\b", cleaned):
                continue

            if arithmetic_ops.search(cleaned):
                findings.append(
                    Finding(
                        id="SCA-006",
                        title="Unsafe Arithmetic (No Overflow Protection)",
                        severity="HIGH",
                        category="Arithmetic",
                        description=(
                            f"Arithmetic operation detected in a Solidity <0.8.0 "
                            f"contract without SafeMath. Integer overflow or "
                            f"underflow may occur."
                        ),
                        location=Location(line_number=line_idx, code_snippet=_snippet(stripped)),
                        recommendation=(
                            "Use OpenZeppelin's SafeMath library for all arithmetic "
                            "operations, or upgrade to Solidity >=0.8.0 which has "
                            "built-in overflow checking."
                        ),
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # SCA-007 — Delegatecall to User Input
    # ------------------------------------------------------------------

    def _check_delegatecall(self, source: str, lines: list[str]) -> list[Finding]:
        """Detect ``delegatecall`` usage with potentially user-controlled targets."""
        findings: list[Finding] = []

        func_matches = list(_RE_FUNCTION_DECL.finditer(source))

        for func_match in func_matches:
            func_name = func_match.group(1)
            func_start_offset = func_match.start()
            func_start_line = source[:func_start_offset].count("\n")
            body_text = _extract_function_body(source, func_start_line, lines)

            for offset, bline in enumerate(body_text.splitlines()):
                if ".delegatecall(" not in bline:
                    continue

                # Heuristic: if the delegatecall target or data comes from
                # a function parameter (not a hardcoded address), flag it.
                # We look for variables rather than address literals.
                has_literal_address = bool(_RE_ETH_ADDRESS.search(bline))
                if has_literal_address:
                    continue  # calling a known address — lower risk

                line_no = func_start_line + offset + 1
                findings.append(
                    Finding(
                        id="SCA-007",
                        title="Delegatecall with Potentially Controllable Target",
                        severity="CRITICAL",
                        category="Delegatecall Injection",
                        description=(
                            f"Function `{func_name}` uses `delegatecall` with a "
                            f"target that may be user-controllable. An attacker "
                            f"can execute arbitrary code in this contract's context."
                        ),
                        location=Location(
                            line_number=line_no,
                            code_snippet=_snippet(bline),
                        ),
                        recommendation=(
                            "Never pass user-supplied data as the target of "
                            "`delegatecall`. Use a whitelisted, immutable "
                            "implementation address and validate all inputs."
                        ),
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # SCA-008 — Unbounded Loops
    # ------------------------------------------------------------------

    def _check_unbounded_loops(self, source: str, lines: list[str]) -> list[Finding]:
        """Detect loops iterating over dynamic-length arrays (gas DoS risk)."""
        findings: list[Finding] = []

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Match `for (... i < arr.length ...)` or `while (i < arr.length)`
            if re.search(
                r"\b(?:for|while)\s*\(.*\w+\.length\b", stripped
            ):
                findings.append(
                    Finding(
                        id="SCA-008",
                        title="Unbounded Loop Over Dynamic Array",
                        severity="MEDIUM",
                        category="Denial of Service",
                        description=(
                            "A loop iterates up to a dynamic array's `.length`. "
                            "If the array grows large, the transaction may exceed "
                            "the block gas limit, causing a permanent denial of "
                            "service."
                        ),
                        location=Location(line_number=line_idx, code_snippet=_snippet(stripped)),
                        recommendation=(
                            "Avoid unbounded loops. Use pagination, limit the "
                            "maximum array size, or use a pull-over-push pattern "
                            "so users process their own data."
                        ),
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # SCA-009 — Missing Access Control
    # ------------------------------------------------------------------

    def _check_missing_access_control(
        self, source: str, lines: list[str]
    ) -> list[Finding]:
        """Detect public/external state-mutating functions with no access control."""
        findings: list[Finding] = []
        func_matches = list(_RE_FUNCTION_DECL.finditer(source))

        # State-changing operations (writes to storage)
        state_mutators = re.compile(
            r"(?:"
            r"\w+\s*(?:\[.*?\])?\s*(?:=|\+=|-=|\*=|/=)\s*"  # assignments
            r"|\bdelete\s+\w+"                               # delete
            r"|\.\s*push\s*\("                               # array push
            r"|\.\s*pop\s*\("                                # array pop
            r")",
            re.MULTILINE,
        )

        for func_match in func_matches:
            func_name = func_match.group(1)
            modifiers_area = func_match.group(2)
            func_start_offset = func_match.start()
            func_start_line = source[:func_start_offset].count("\n")
            body_text = _extract_function_body(source, func_start_line, lines)

            # Skip view / pure functions
            if re.search(r"\b(?:view|pure)\b", modifiers_area):
                continue

            # Skip constructors / fallback / receive
            if func_name in ("constructor", "fallback", "receive"):
                continue

            # Check if function modifies state
            body_without_decl = "\n".join(body_text.splitlines()[1:])
            if not state_mutators.search(body_without_decl):
                continue

            # Check for access-control modifiers in the declaration
            has_modifier = bool(_RE_ACCESS_MODIFIERS.search(modifiers_area))
            if has_modifier:
                continue

            # Check for inline msg.sender / owner checks in the body
            has_sender_check = bool(_RE_MSG_SENDER_CHECK.search(body_text))
            if has_sender_check:
                continue

            line_no = func_start_line + 1  # 1-based
            code = _snippet(lines[func_start_line])
            findings.append(
                Finding(
                    id="SCA-009",
                    title="Missing Access Control",
                    severity="HIGH",
                    category="Access Control",
                    description=(
                        f"Function `{func_name}` is public/external and modifies "
                        f"state but has no access control. Any external account or "
                        f"contract can call it."
                    ),
                    location=Location(line_number=line_no, code_snippet=code),
                    recommendation=(
                        "Add an access control modifier such as `onlyOwner` or "
                        "use `require(msg.sender == owner)`. Consider OpenZeppelin's "
                        "Ownable or AccessControl contracts."
                    ),
                )
            )

        return findings

    # ------------------------------------------------------------------
    # SCA-010 — Hardcoded Addresses
    # ------------------------------------------------------------------

    def _check_hardcoded_addresses(
        self, source: str, lines: list[str]
    ) -> list[Finding]:
        """Detect hardcoded Ethereum addresses (centralisation / maintainability risk)."""
        findings: list[Finding] = []

        # Common benign addresses to ignore (zero address, dead address, precompiles)
        _BENIGN_ADDRESSES = {
            "0x" + "0" * 40,                      # address(0)
            "0x" + "0" * 39 + "1",                 # ecrecover precompile
            "0x" + "0" * 39 + "2",                 # SHA-256 precompile
            "0x" + "0" * 39 + "3",                 # RIPEMD-160
            "0x" + "0" * 39 + "4",                 # identity
            "0x" + "0" * 39 + "5",                 # modexp
            "0x" + "f" * 40,                       # common burn address
            "0x" + "F" * 40,
            "0x000000000000000000000000000000000000dEaD",  # dead address
        }

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith(("//", "/*", "*")):
                continue

            for addr_match in _RE_ETH_ADDRESS.finditer(line):
                address = addr_match.group(0)
                if address.lower() in {a.lower() for a in _BENIGN_ADDRESSES}:
                    continue

                findings.append(
                    Finding(
                        id="SCA-010",
                        title="Hardcoded Ethereum Address",
                        severity="INFO",
                        category="Centralisation Risk",
                        description=(
                            f"Hardcoded address `{address}` detected. Hardcoded "
                            f"addresses reduce upgradeability and may introduce "
                            f"centralisation risk if they represent privileged roles."
                        ),
                        location=Location(line_number=line_idx, code_snippet=_snippet(stripped)),
                        recommendation=(
                            "Use constructor parameters, configuration contracts, "
                            "or environment-based deployment scripts to inject "
                            "addresses at deploy time instead of hardcoding them."
                        ),
                    )
                )

        return findings
