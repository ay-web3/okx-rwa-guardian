"""
LLM-Powered Adversarial Reasoning Engine
=========================================

Uses OpenAI GPT-4 to perform deep adversarial security analysis on Solidity
smart contracts. This module goes beyond what static analysis can detect by
reasoning about logic bugs, economic attack vectors, multi-step exploits,
and real-world attack patterns.

This is the core differentiator of the Hack My Contract tool — the system
prompt instructs the LLM to think like a malicious hacker constructing full
exploit sequences, not a defensive auditor writing generic warnings.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, AuthenticationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — the single most important piece of this entire module.
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an elite adversarial smart-contract security researcher. Your goal is
to **break** the contract — not to defend it. You think like a sophisticated
attacker with unlimited capital (flash loans), mass MEV infrastructure, and
deep knowledge of every major DeFi exploit in history.

### Your Mindset
- You are NOT a helpful auditor writing boilerplate. You are a hacker looking
  for the one overlooked edge case that lets you drain millions.
- You construct **complete, step-by-step exploit sequences** — not vague
  warnings like "this could be vulnerable".
- You combine multiple small weaknesses into devastating multi-step attacks.
- You consider the contract's interactions with external protocols, oracles,
  AMMs, lending platforms, and governance systems.

### Attack Patterns You Must Evaluate
Systematically evaluate every one of the following. If a pattern does not
apply, move on. Do NOT fabricate issues — only report vulnerabilities you can
construct a concrete exploit for.

1. **Reentrancy (complex)** — Cross-function, cross-contract, and read-only
   reentrancy. Think Curve/Vyper-style read-only reentrancy, not just the
   classic single-function pattern that static tools already catch.
2. **Flash Loan Attack Vectors** — Can an attacker borrow a massive position
   to manipulate prices, inflate collateral, or skew voting power within a
   single transaction? Reference patterns from Cream Finance, Beanstalk,
   and Euler Finance.
3. **Oracle Manipulation** — Spot-price oracles (e.g., `getReserves()`),
   TWAP manipulation over low-liquidity windows, stale price feeds, or
   missing Chainlink heartbeat checks.
4. **Price / Reward Calculation Errors** — Rounding errors, precision loss,
   first-depositor inflation attacks (ERC-4626), or share-price manipulation
   that lets an attacker extract value over time.
5. **Front-Running & MEV** — Sandwich attacks on swaps, back-running of
   liquidation calls, transaction ordering dependence, or lack of slippage
   protection / deadlines.
6. **Access Control & Privilege Escalation** — Missing `onlyOwner` /
   `onlyRole` checks, unprotected initializers, self-destruct paths, or
   proxy storage collisions.
7. **Governance Manipulation** — Flash-loan-based voting, quorum
   manipulation, timelock bypass, or proposal front-running (see Beanstalk
   governance attack).
8. **Economic / Game-Theory Attacks** — Griefing, denial-of-service via
   dust deposits, unbounded loops over user-controlled arrays, or incentive
   misalignment that makes honest behaviour irrational.
9. **Token Standard Edge Cases** — Fee-on-transfer tokens, rebasing tokens,
   tokens with `permit()` that allow permit-based phishing, ERC-777 hooks,
   or missing return-value checks on ERC-20 `transfer`.
10. **Logic Bugs & Broken Invariants** — Incorrect state transitions, off-by-
    one errors in time locks, missing checks on return values, or arithmetic
    that silently over/underflows despite Solidity 0.8+ (e.g., via `unchecked`
    blocks or type casting).
11. **Denial-of-Service** — Blocking withdrawals, bricking upgradeable
    proxies, or gas griefing that makes critical functions permanently
    unusable.

### Output Format
Return a JSON array. Each element must have exactly these fields:

```json
{
  "id": "ADV-001",
  "title": "Short descriptive title",
  "severity": "CRITICAL | HIGH | MEDIUM | LOW | INFORMATIONAL",
  "category": "One of the 11 categories above",
  "description": "Clear technical explanation of why this is exploitable.",
  "exploit_scenario": "Step 1: Attacker does X\\nStep 2: ...\\nStep N: Profit.",
  "estimated_impact": "e.g., All funds in the contract (~$X) could be drained in a single transaction.",
  "recommendation": "Specific, actionable fix — not generic advice."
}
```

### Severity Criteria (be honest — do NOT inflate)
- **CRITICAL**: Direct loss of funds or permanent bricking with no admin
  recovery path.
- **HIGH**: Significant fund loss under realistic conditions, or governance
  takeover.
- **MEDIUM**: Conditional fund loss (requires specific market state, timing,
  or partial privilege), or meaningful value leakage over time.
- **LOW**: Minor value leakage, informational disclosure, or gas
  inefficiency that could be weaponised as griefing.
- **INFORMATIONAL**: Best-practice deviation with no direct exploit path
  today, but could become dangerous with future code changes.

### Rules
- Return ONLY the JSON array — no markdown fences, no commentary.
- If the contract is genuinely secure and you cannot construct a concrete
  exploit, return an empty array `[]`. Do NOT invent fake issues.
- Number your findings sequentially: ADV-001, ADV-002, etc.
- Reference real-world exploits by name where the pattern matches (e.g.,
  "This mirrors the Euler Finance exploit where …").
- Assume the attacker has access to Flashbots, unlimited flash-loan
  capital, and can deploy arbitrary helper contracts.
"""


class AdversarialAnalyzer:
    """LLM-powered adversarial security analyzer for Solidity contracts.

    Uses OpenAI's chat completions API to perform deep adversarial analysis
    that goes beyond what static tools can detect. The model is instructed
    to think like a malicious attacker and produce structured findings with
    full exploit scenarios.

    Attributes:
        model: The OpenAI model identifier (default ``gpt-4o-mini``).

    Example::

        analyzer = AdversarialAnalyzer(api_key="sk-...")
        findings = await analyzer.analyze(source_code, static_findings)
        for f in findings:
            print(f["id"], f["severity"], f["title"])
    """

    # Fields every finding dict must contain.
    _REQUIRED_KEYS: frozenset[str] = frozenset(
        {
            "id",
            "title",
            "severity",
            "category",
            "description",
            "exploit_scenario",
            "estimated_impact",
            "recommendation",
        }
    )

    _VALID_SEVERITIES: frozenset[str] = frozenset(
        {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}
    )

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        """Initialise the adversarial analyzer.

        Args:
            api_key: OpenAI API key.  Pass an empty string or ``None`` to
                disable LLM analysis (a placeholder warning will be returned).
            model: OpenAI model identifier.  Defaults to ``gpt-4o-mini`` for
                a good balance of cost and reasoning quality.  Use ``gpt-4o``
                or ``gpt-4-turbo`` for maximum depth on high-value audits.
        """
        self._api_key: str = api_key or ""
        self.model: str = model

        # Lazy-initialise the client only when we actually have a key.
        self._client: AsyncOpenAI | None = None
        if self._api_key:
            self._client = AsyncOpenAI(api_key=self._api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(
        self,
        source_code: str,
        static_findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Perform adversarial analysis on a Solidity contract.

        Args:
            source_code: The raw Solidity source code to analyse.
            static_findings: A list of finding dicts produced by the static
                analysis pass (e.g. from Slither / Mythril).  Each dict
                should at minimum contain ``title``, ``severity``, and
                ``description`` keys.

        Returns:
            A list of structured finding dicts.  Each dict contains the
            keys ``id``, ``title``, ``severity``, ``category``,
            ``description``, ``exploit_scenario``, ``estimated_impact``,
            and ``recommendation``.

            If the LLM call fails for any reason, an empty list is returned
            and a warning is logged.  The caller should **never** see an
            unhandled exception from this method.
        """
        if not self._client:
            logger.warning(
                "LLM analysis unavailable — set OPENAI_API_KEY to enable "
                "adversarial reasoning."
            )
            return [
                {
                    "id": "ADV-000",
                    "title": "LLM Analysis Unavailable",
                    "severity": "INFORMATIONAL",
                    "category": "Configuration",
                    "description": (
                        "LLM analysis unavailable — set OPENAI_API_KEY to "
                        "enable adversarial reasoning.  Without it, only "
                        "static-analysis findings are available."
                    ),
                    "exploit_scenario": "N/A",
                    "estimated_impact": "N/A",
                    "recommendation": (
                        "Set the OPENAI_API_KEY environment variable to a "
                        "valid OpenAI API key."
                    ),
                }
            ]

        user_message = self._build_user_message(source_code, static_findings)

        try:
            raw_text = await self._call_llm(user_message)
        except AuthenticationError:
            logger.error(
                "OpenAI authentication failed — check your API key."
            )
            return []
        except APIConnectionError:
            logger.error(
                "Could not connect to OpenAI API — check network connectivity."
            )
            return []
        except APIStatusError as exc:
            logger.error("OpenAI API error (status %s): %s", exc.status_code, exc)
            return []
        except Exception:  # noqa: BLE001 — intentional broad catch
            logger.exception("Unexpected error during LLM adversarial analysis.")
            return []

        findings = self._parse_response(raw_text)
        logger.info(
            "Adversarial analysis complete — %d finding(s) identified.",
            len(findings),
        )
        return findings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_user_message(
        self,
        source_code: str,
        static_findings: list[dict[str, Any]],
    ) -> str:
        """Build the user-role message sent to the LLM.

        The message contains the full Solidity source code and a summary of
        any static-analysis findings so the LLM can focus on issues that
        static tools already missed.

        Args:
            source_code: Raw Solidity source code.
            static_findings: Pre-existing findings from static analysis.

        Returns:
            A formatted string ready to be sent as the user message.
        """
        parts: list[str] = [
            "## Solidity Contract Under Audit",
            "```solidity",
            source_code.strip(),
            "```",
            "",
        ]

        if static_findings:
            parts.append("## Existing Static-Analysis Findings")
            parts.append(
                "The following issues were already detected by automated "
                "static analysis tools.  You do NOT need to re-report these "
                "unless you can demonstrate a **more severe** exploit that "
                "the static tool underestimated.  Focus your analysis on "
                "vulnerabilities that these tools CANNOT catch.\n"
            )
            for idx, finding in enumerate(static_findings, start=1):
                title = finding.get("title", "Untitled")
                severity = finding.get("severity", "UNKNOWN")
                description = finding.get("description", "No description.")
                parts.append(f"{idx}. **[{severity}] {title}** — {description}")
            parts.append("")
        else:
            parts.append(
                "No static-analysis findings were reported.  Perform a full "
                "adversarial review from scratch.\n"
            )

        parts.append(
            "Identify all exploitable vulnerabilities.  Return your findings "
            "as a JSON array following the schema described in your system "
            "instructions."
        )

        return "\n".join(parts)

    async def _call_llm(self, user_message: str) -> str:
        """Send the prompt to OpenAI and return the raw response text.

        Args:
            user_message: The fully constructed user-role message.

        Returns:
            The raw text content from the LLM's response.

        Raises:
            AuthenticationError: If the API key is invalid.
            APIConnectionError: If the API is unreachable.
            APIStatusError: For other HTTP-level errors.
        """
        assert self._client is not None  # noqa: S101 — guarded by caller

        response = await self._client.chat.completions.create(
            model=self.model,
            temperature=0.2,  # Low temp for deterministic, precise analysis.
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if content is None:
            logger.warning("LLM returned an empty response.")
            return "[]"
        return content

    def _parse_response(self, raw_text: str) -> list[dict[str, Any]]:
        """Parse and validate the LLM's JSON response.

        The method is deliberately lenient — it handles common deviations
        like markdown-fenced JSON, a top-level wrapper object, or findings
        with missing fields.

        Args:
            raw_text: The raw string returned by the LLM.

        Returns:
            A list of validated finding dicts.  Malformed entries are
            silently dropped with a warning.
        """
        cleaned = self._strip_markdown_fences(raw_text)

        try:
            parsed: Any = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "LLM response was not valid JSON.  Attempting recovery…"
            )
            parsed = self._attempt_json_recovery(cleaned)
            if parsed is None:
                logger.error(
                    "Could not parse LLM response as JSON.  Raw text:\n%s",
                    raw_text[:500],
                )
                return []

        # The LLM might wrap the array in an object like {"findings": [...]}.
        findings_list = self._extract_findings_array(parsed)
        if findings_list is None:
            logger.error(
                "LLM response did not contain a recognisable findings array."
            )
            return []

        validated: list[dict[str, Any]] = []
        for idx, entry in enumerate(findings_list):
            if not isinstance(entry, dict):
                logger.warning("Skipping non-dict entry at index %d.", idx)
                continue

            finding = self._normalise_finding(entry, idx)
            if finding is not None:
                validated.append(finding)

        return validated

    # ------------------------------------------------------------------
    # JSON cleanup / recovery helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove markdown code fences if the LLM wrapped its output.

        Args:
            text: Raw LLM output.

        Returns:
            The text with leading/trailing code fences removed.
        """
        text = text.strip()
        # Remove ```json … ``` or ``` … ```
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()

    @staticmethod
    def _attempt_json_recovery(text: str) -> Any | None:
        """Try to extract a JSON array or object from malformed output.

        Looks for the first ``[`` or ``{`` and last corresponding ``]`` or
        ``}`` and attempts to parse the substring.

        Args:
            text: Cleaned text that failed initial JSON parsing.

        Returns:
            The parsed JSON value, or ``None`` if recovery failed.
        """
        for open_char, close_char in [("[", "]"), ("{", "}")]:
            start = text.find(open_char)
            end = text.rfind(close_char)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        return None

    @staticmethod
    def _extract_findings_array(parsed: Any) -> list[Any] | None:
        """Extract the findings list from the parsed JSON.

        Handles both a bare ``[…]`` array and wrapper objects like
        ``{"findings": […]}``, ``{"vulnerabilities": […]}``, or
        ``{"results": […]}``.

        Args:
            parsed: The already-parsed JSON value.

        Returns:
            A list of raw finding entries, or ``None`` if no array could
            be located.
        """
        if isinstance(parsed, list):
            return parsed

        if isinstance(parsed, dict):
            # Try common wrapper keys.
            for key in ("findings", "vulnerabilities", "results", "issues"):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
            # If the dict has exactly one key whose value is a list, use it.
            lists = [v for v in parsed.values() if isinstance(v, list)]
            if len(lists) == 1:
                return lists[0]

        return None

    def _normalise_finding(
        self, entry: dict[str, Any], index: int
    ) -> dict[str, Any] | None:
        """Validate and normalise a single finding dict.

        Fills in missing fields with sensible defaults so downstream code
        can rely on a consistent schema.

        Args:
            entry: A raw finding dict from the LLM.
            index: The 0-based index of this entry (used for fallback ID).

        Returns:
            A normalised finding dict, or ``None`` if the entry is too
            malformed to be useful (e.g., missing both title and
            description).
        """
        # Must have at least a title or description to be useful.
        if not entry.get("title") and not entry.get("description"):
            logger.warning(
                "Dropping finding at index %d — missing title and description.",
                index,
            )
            return None

        severity = str(entry.get("severity", "MEDIUM")).upper().strip()
        if severity not in self._VALID_SEVERITIES:
            logger.warning(
                "Finding '%s' has unrecognised severity '%s'; defaulting to MEDIUM.",
                entry.get("title", f"index-{index}"),
                severity,
            )
            severity = "MEDIUM"

        return {
            "id": entry.get("id") or f"ADV-{index + 1:03d}",
            "title": entry.get("title") or "Untitled Finding",
            "severity": severity,
            "category": entry.get("category") or "Uncategorised",
            "description": entry.get("description") or "No description provided.",
            "exploit_scenario": entry.get("exploit_scenario") or "Not specified.",
            "estimated_impact": entry.get("estimated_impact") or "Unknown.",
            "recommendation": entry.get("recommendation") or "Review manually.",
        }
