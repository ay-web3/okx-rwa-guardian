"""
report_generator.py — Penetration Test Report assembler for Hack My Contract.

Combines static‑analysis findings and LLM‑powered adversarial findings into a
single, structured report dict that is ready for API serialisation **and**
includes a beautifully formatted Markdown document suitable for delivery to
clients or display in a front‑end viewer.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.analyzer.attack_vectors import Severity


# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: Dict[str, int] = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
}

_SEVERITY_EMOJI: Dict[str, str] = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🔵",
    "INFO": "⚪",
}

_RISK_THRESHOLDS: list[tuple[int, str]] = [
    (80, "CRITICAL"),
    (60, "HIGH"),
    (35, "MEDIUM"),
    (10, "LOW"),
    (0, "SAFE"),
]

_SCORE_WEIGHTS: Dict[str, int] = {
    "CRITICAL": 25,
    "HIGH": 15,
    "MEDIUM": 8,
    "LOW": 3,
    "INFO": 0,
}


# ---------------------------------------------------------------------------
# Helper: extract light metadata from raw Solidity source
# ---------------------------------------------------------------------------

def _extract_contract_metadata(source_code: str) -> Dict[str, Any]:
    """Parse lightweight metadata from Solidity source code.

    This intentionally avoids a full AST parse; it uses simple regex
    heuristics that are *good enough* for report decoration.

    Args:
        source_code: Raw Solidity source text.

    Returns:
        A dict conforming to the ``contract_metadata`` schema.
    """
    lines = source_code.splitlines()

    # Solidity version (first pragma found)
    version_match = re.search(
        r"pragma\s+solidity\s+([^;]+);", source_code
    )
    solidity_version = version_match.group(1).strip() if version_match else "unknown"

    # Function count (named functions + constructor + fallback/receive)
    function_matches = re.findall(
        r"\bfunction\s+\w+\s*\(", source_code
    )
    constructor_matches = re.findall(r"\bconstructor\s*\(", source_code)
    fallback_matches = re.findall(
        r"\b(?:fallback|receive)\s*\(", source_code
    )
    function_count = (
        len(function_matches) + len(constructor_matches) + len(fallback_matches)
    )

    # External calls heuristic
    has_external_calls = bool(
        re.search(r"\.\s*(?:call|send|transfer)\s*[\({]", source_code)
    )

    # Delegatecall usage
    uses_delegatecall = "delegatecall" in source_code

    # Selfdestruct usage
    has_selfdestruct = bool(
        re.search(r"\b(?:selfdestruct|suicide)\s*\(", source_code)
    )

    return {
        "solidity_version": solidity_version,
        "contract_size_lines": len(lines),
        "function_count": function_count,
        "has_external_calls": has_external_calls,
        "uses_delegatecall": uses_delegatecall,
        "has_selfdestruct": has_selfdestruct,
    }


# ---------------------------------------------------------------------------
# Helper: normalise a finding dict
# ---------------------------------------------------------------------------

def _normalise_finding(finding: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Ensure every finding dict has the expected keys with sane defaults.

    Args:
        finding: Raw finding dict from static or LLM analysis.
        index:   Sequence number used to generate a stable ID if absent.

    Returns:
        A new dict with all expected keys populated.
    """
    severity_raw: str = str(finding.get("severity", "INFO")).upper()
    if severity_raw not in _SEVERITY_ORDER:
        severity_raw = "INFO"

    return {
        "id": finding.get("id", f"FINDING-{index:04d}"),
        "title": finding.get("title", "Untitled Finding"),
        "severity": severity_raw,
        "category": finding.get("category", "UNKNOWN"),
        "description": finding.get("description", ""),
        "exploit_scenario": finding.get("exploit_scenario", ""),
        "affected_code": finding.get("affected_code", ""),
        "line_number": finding.get("line_number"),
        "remediation": finding.get("remediation", ""),
        "references": finding.get("references", []),
        "source": finding.get("source", "unknown"),
    }


# ---------------------------------------------------------------------------
# Markdown rendering helpers
# ---------------------------------------------------------------------------

def _risk_bar(score: int, width: int = 20) -> str:
    """Render a text‑based progress bar for the risk score.

    Example output::

        [████████████░░░░░░░░] 60 / 100  ── HIGH

    Args:
        score: Integer 0–100.
        width: Character width of the bar.

    Returns:
        Formatted bar string.
    """
    filled = round(score / 100 * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {score} / 100"


def _severity_badge(severity: str) -> str:
    """Return an emoji + label badge for a severity level."""
    emoji = _SEVERITY_EMOJI.get(severity, "⚪")
    return f"{emoji} **{severity}**"


def _render_markdown_report(
    report_id: str,
    timestamp: str,
    contract_name: str,
    overall_risk_score: int,
    risk_level: str,
    summary: Dict[str, int],
    findings: List[Dict[str, Any]],
    metadata: Dict[str, Any],
) -> str:
    """Build the full Markdown penetration test report.

    Args:
        report_id: UUID of the report.
        timestamp: ISO‑8601 timestamp.
        contract_name: Name of the audited contract.
        overall_risk_score: Computed risk score (0–100).
        risk_level: Human label for the risk tier.
        summary: Count dict (total_findings, critical, …).
        findings: Sorted list of normalised finding dicts.
        metadata: ``contract_metadata`` dict.

    Returns:
        Complete Markdown string.
    """
    sections: list[str] = []

    # ── Title ──────────────────────────────────────────────────────────
    sections.append(
        f"# 💀 PENETRATION TEST REPORT\n"
        f"### Smart Contract Security Assessment\n"
    )

    # ── Meta table ─────────────────────────────────────────────────────
    sections.append(
        "---\n"
        f"| Field | Value |\n"
        f"|---|---|\n"
        f"| **Report ID** | `{report_id}` |\n"
        f"| **Date** | {timestamp} |\n"
        f"| **Target** | `{contract_name}` |\n"
        f"| **Solidity Version** | `{metadata['solidity_version']}` |\n"
        f"| **Contract Size** | {metadata['contract_size_lines']} lines |\n"
        f"| **Functions Analysed** | {metadata['function_count']} |\n"
        "---\n"
    )

    # ── Executive Summary ──────────────────────────────────────────────
    bar = _risk_bar(overall_risk_score)
    sections.append(
        "## 📋 Executive Summary\n\n"
        f"**Overall Risk Score**\n\n"
        f"```\n{bar}  ──  {risk_level}\n```\n\n"
        f"A total of **{summary['total_findings']}** finding(s) were "
        f"identified during the assessment:\n\n"
        f"| Severity | Count |\n"
        f"|---|---:|\n"
        f"| {_severity_badge('CRITICAL')} | {summary['critical']} |\n"
        f"| {_severity_badge('HIGH')} | {summary['high']} |\n"
        f"| {_severity_badge('MEDIUM')} | {summary['medium']} |\n"
        f"| {_severity_badge('LOW')} | {summary['low']} |\n"
        f"| {_severity_badge('INFO')} | {summary['info']} |\n"
    )

    # ── Dangerous features ─────────────────────────────────────────────
    flags: list[str] = []
    if metadata.get("has_external_calls"):
        flags.append("⚠️  Contains **external calls** (`call` / `send` / `transfer`)")
    if metadata.get("uses_delegatecall"):
        flags.append("⚠️  Uses **`delegatecall`** — potential storage collision or injection")
    if metadata.get("has_selfdestruct"):
        flags.append("⚠️  Contains **`selfdestruct`** — contract can be permanently destroyed")

    if flags:
        sections.append(
            "\n### ⚠️ Dangerous Features Detected\n\n"
            + "\n".join(f"- {f}" for f in flags)
            + "\n"
        )

    # ── Findings Overview Table ────────────────────────────────────────
    if findings:
        sections.append(
            "\n---\n"
            "## 🔍 Findings Overview\n\n"
            "| # | ID | Title | Severity | Category | Source |\n"
            "|---:|---|---|---|---|---|\n"
        )
        for idx, f in enumerate(findings, 1):
            sev_badge = _severity_badge(f["severity"])
            sections.append(
                f"| {idx} | `{f['id']}` | {f['title']} "
                f"| {sev_badge} | {f['category']} | {f['source']} |\n"
            )

    # ── Detailed Findings ──────────────────────────────────────────────
    if findings:
        sections.append(
            "\n---\n"
            "## 📝 Detailed Findings\n"
        )
        for f in findings:
            sev_badge = _severity_badge(f["severity"])
            sections.append(
                f"\n### {f['id']} — {f['title']}\n\n"
                f"| | |\n|---|---|\n"
                f"| **Severity** | {sev_badge} |\n"
                f"| **Category** | {f['category']} |\n"
                f"| **Source** | {f['source']} |\n"
            )
            if f.get("line_number") is not None:
                sections.append(f"| **Line** | {f['line_number']} |\n")

            sections.append(f"\n**Description**\n\n{f['description']}\n")

            if f.get("affected_code"):
                sections.append(
                    f"\n**Affected Code**\n\n"
                    f"```solidity\n{f['affected_code']}\n```\n"
                )

            if f.get("exploit_scenario"):
                sections.append(
                    f"\n**Exploit Scenario**\n\n"
                    f"> {f['exploit_scenario']}\n"
                )

            if f.get("remediation"):
                sections.append(
                    f"\n**Remediation**\n\n{f['remediation']}\n"
                )

            if f.get("references"):
                refs = f["references"]
                ref_lines = "\n".join(f"- <{r}>" for r in refs)
                sections.append(f"\n**References**\n\n{ref_lines}\n")

    # ── Remediation Guide ──────────────────────────────────────────────
    sections.append(
        "\n---\n"
        "## 🛡️ Remediation Guide\n\n"
        "The following best practices are recommended based on the findings above:\n\n"
        "1. **Checks‑Effects‑Interactions** — Always update state variables "
        "*before* making external calls to prevent reentrancy.\n"
        "2. **Use OpenZeppelin Libraries** — Leverage battle‑tested "
        "implementations for access control (`Ownable`, `AccessControl`), "
        "reentrancy guards (`ReentrancyGuard`), and safe math.\n"
        "3. **Oracle Hardening** — Use time‑weighted average prices (TWAPs) "
        "and multiple oracle sources to resist spot‑price manipulation.\n"
        "4. **Minimal Privilege** — Restrict privileged functions with "
        "multi‑sig wallets, timelocks, and role‑based access.\n"
        "5. **Comprehensive Testing** — Maintain ≥ 95 % branch coverage with "
        "fuzzing (Foundry, Echidna) and formal verification where possible.\n"
        "6. **Upgrade Safety** — If using proxies, ensure storage layout "
        "compatibility and protect initialisation functions.\n"
    )

    # ── Disclaimer ─────────────────────────────────────────────────────
    sections.append(
        "\n---\n"
        "## Disclaimer\n\n"
        "> This report is generated by **Hack My Contract** - an automated "
        "smart-contract security analysis tool. It is provided on an "
        "'as-is' basis for informational purposes only and does **not** "
        "constitute a formal security audit, legal advice, or guarantee of "
        "contract safety. The authors and operators of this tool accept no "
        "liability for losses arising from the use of, or reliance on, this "
        "report. A professional manual audit by an accredited security firm "
        "is strongly recommended before deploying any contract to mainnet.\n\n"
        f"*Report generated at {timestamp} - Hack My Contract v1.0*\n"
    )

    return "".join(sections)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Assembles analysis findings into a structured penetration test report.

    Usage::

        generator = ReportGenerator()
        report = generator.generate(
            contract_name="VulnerableVault",
            source_code=solidity_src,
            static_findings=slither_results,
            llm_findings=adversarial_results,
        )
    """

    # ------------------------------------------------------------------
    # Core entry point
    # ------------------------------------------------------------------

    def generate(
        self,
        contract_name: str,
        source_code: str,
        static_findings: list[dict],
        llm_findings: list[dict],
    ) -> dict:
        """Generate a complete penetration test report.

        Args:
            contract_name:    Human‑readable name of the target contract.
            source_code:      Raw Solidity source code of the contract.
            static_findings:  Findings produced by static analysis tools
                              (e.g. Slither, custom pattern detectors).
            llm_findings:     Findings produced by the LLM adversarial
                              analysis module.

        Returns:
            A report dict conforming to the documented schema, including a
            ``markdown_report`` key with the full formatted Markdown document.
        """
        report_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # Normalise & tag source ----------------------------------------
        all_findings: list[dict] = []
        for idx, f in enumerate(static_findings):
            normalised = _normalise_finding(f, idx)
            normalised.setdefault("source", "static_analysis")
            if normalised["source"] == "unknown":
                normalised["source"] = "static_analysis"
            all_findings.append(normalised)

        offset = len(static_findings)
        for idx, f in enumerate(llm_findings):
            normalised = _normalise_finding(f, offset + idx)
            normalised.setdefault("source", "llm_adversarial")
            if normalised["source"] == "unknown":
                normalised["source"] = "llm_adversarial"
            all_findings.append(normalised)

        # Sort by severity (CRITICAL first) -----------------------------
        all_findings.sort(key=lambda f: _SEVERITY_ORDER.get(f["severity"], 99))

        # Summary counts -----------------------------------------------
        summary = self._compute_summary(all_findings)

        # Risk score & level --------------------------------------------
        overall_risk_score = self._compute_risk_score(all_findings)
        risk_level = self._risk_level(overall_risk_score)

        # Contract metadata ---------------------------------------------
        contract_metadata = _extract_contract_metadata(source_code)

        # Markdown report -----------------------------------------------
        markdown_report = _render_markdown_report(
            report_id=report_id,
            timestamp=timestamp,
            contract_name=contract_name,
            overall_risk_score=overall_risk_score,
            risk_level=risk_level,
            summary=summary,
            findings=all_findings,
            metadata=contract_metadata,
        )

        return {
            "report_id": report_id,
            "timestamp": timestamp,
            "contract_name": contract_name,
            "overall_risk_score": overall_risk_score,
            "risk_level": risk_level,
            "summary": summary,
            "findings": all_findings,
            "contract_metadata": contract_metadata,
            "markdown_report": markdown_report,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_summary(findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Tally findings by severity level.

        Args:
            findings: List of normalised finding dicts.

        Returns:
            Dict with keys ``total_findings``, ``critical``, ``high``,
            ``medium``, ``low``, ``info``.
        """
        counts: Dict[str, int] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        for f in findings:
            key = f["severity"].lower()
            if key in counts:
                counts[key] += 1

        counts["total_findings"] = len(findings)
        return counts

    @staticmethod
    def _compute_risk_score(findings: List[Dict[str, Any]]) -> int:
        """Derive a 0–100 risk score from severity distribution.

        Scoring rules:
        - Each CRITICAL finding: +25
        - Each HIGH finding:     +15
        - Each MEDIUM finding:   +8
        - Each LOW finding:      +3
        - INFO findings:          0

        The result is capped at 100.

        Args:
            findings: List of normalised finding dicts.

        Returns:
            Integer risk score between 0 and 100 inclusive.
        """
        score = sum(
            _SCORE_WEIGHTS.get(f["severity"], 0) for f in findings
        )
        return min(score, 100)

    @staticmethod
    def _risk_level(score: int) -> str:
        """Map a numeric risk score to a human‑readable label.

        Args:
            score: Integer 0–100.

        Returns:
            One of ``'CRITICAL'``, ``'HIGH'``, ``'MEDIUM'``, ``'LOW'``, or
            ``'SAFE'``.
        """
        for threshold, label in _RISK_THRESHOLDS:
            if score >= threshold:
                return label
        return "SAFE"
