"""
attack_vectors.py — Canonical attack vector categories for smart contract security analysis.

Defines the standard taxonomy of vulnerability classes used throughout the
Hack My Contract analysis pipeline. Each vector carries metadata that feeds
into report generation, severity scoring, and remediation guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


# ---------------------------------------------------------------------------
# Severity enum (shared with the rest of the analyser)
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """Standard severity levels aligned with OWASP / CVSS conventions."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    def __str__(self) -> str:  # noqa: D105
        return self.value


# ---------------------------------------------------------------------------
# Attack‑vector metadata container
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AttackVectorInfo:
    """Immutable descriptor for a single attack‑vector category.

    Attributes:
        name: Human‑readable label (e.g. ``"Reentrancy"``).
        description: Concise technical explanation of the vulnerability class.
        default_severity: The typical severity when this vector is confirmed.
        reference_url: URL to a well‑known real‑world exploit or write‑up.
    """

    name: str
    description: str
    default_severity: Severity
    reference_url: str


# ---------------------------------------------------------------------------
# Attack‑vector enumeration
# ---------------------------------------------------------------------------

class AttackVector(Enum):
    """The ten canonical attack‑vector categories tracked by Hack My Contract.

    Each member's *value* is an :class:`AttackVectorInfo` instance so that
    callers can access rich metadata directly::

        >>> AttackVector.REENTRANCY.value.name
        'Reentrancy'
        >>> AttackVector.REENTRANCY.value.default_severity
        <Severity.CRITICAL: 'CRITICAL'>
    """

    REENTRANCY = AttackVectorInfo(
        name="Reentrancy",
        description=(
            "An external call transfers control to an untrusted contract "
            "before the calling contract's state is updated, allowing the "
            "callee to re‑enter and repeat withdrawals or other privileged "
            "operations."
        ),
        default_severity=Severity.CRITICAL,
        reference_url="https://hackmd.io/@nomad/the-dao-hack",
    )

    FLASH_LOAN = AttackVectorInfo(
        name="Flash Loan Attack",
        description=(
            "An attacker uses uncollateralised flash‑loan liquidity within a "
            "single transaction to manipulate protocol state—often price "
            "oracles or governance votes—extracting value before the loan is "
            "repaid."
        ),
        default_severity=Severity.CRITICAL,
        reference_url="https://rekt.news/bZx2/",
    )

    ACCESS_CONTROL = AttackVectorInfo(
        name="Access Control",
        description=(
            "Missing or improperly implemented authorisation checks allow "
            "unauthorised actors to call privileged functions such as "
            "minting, pausing, or upgrading the contract."
        ),
        default_severity=Severity.HIGH,
        reference_url="https://rekt.news/parity-wallet-hack/",
    )

    ORACLE_MANIPULATION = AttackVectorInfo(
        name="Oracle Manipulation",
        description=(
            "A contract relies on a price feed or data source that an "
            "attacker can influence—typically a spot‑AMM price—to skew "
            "collateral valuations, liquidation thresholds, or swap rates."
        ),
        default_severity=Severity.CRITICAL,
        reference_url="https://rekt.news/harvest-finance-rekt/",
    )

    INTEGER_OVERFLOW = AttackVectorInfo(
        name="Integer Overflow / Underflow",
        description=(
            "Arithmetic operations exceed the range of their data type, "
            "wrapping around to produce unexpected values. Pre‑Solidity "
            "0.8.0 contracts without SafeMath are especially vulnerable."
        ),
        default_severity=Severity.HIGH,
        reference_url="https://blog.soliditylang.org/2020/10/28/solidity-0.8.x-preview/",
    )

    FRONTRUNNING_MEV = AttackVectorInfo(
        name="Front‑running / MEV",
        description=(
            "An adversary observes a pending transaction in the mempool and "
            "submits a competing transaction with a higher gas price (or via "
            "a private relay) to extract value—sandwich attacks, back‑runs, "
            "and liquidation sniping are common variants."
        ),
        default_severity=Severity.MEDIUM,
        reference_url="https://www.paradigm.xyz/2020/08/ethereum-is-a-dark-forest",
    )

    DELEGATECALL_INJECTION = AttackVectorInfo(
        name="Delegatecall Injection",
        description=(
            "A contract uses ``delegatecall`` to execute code from an "
            "attacker‑controlled address, giving the attacker full write "
            "access to the calling contract's storage and balance."
        ),
        default_severity=Severity.CRITICAL,
        reference_url="https://rekt.news/parity-wallet-hack/",
    )

    DENIAL_OF_SERVICE = AttackVectorInfo(
        name="Denial of Service",
        description=(
            "An attacker forces a contract into a state where legitimate "
            "users can no longer interact with it—common patterns include "
            "unbounded loops over user‑controlled arrays, unexpected reverts "
            "in fallback functions, and block‑gas‑limit abuse."
        ),
        default_severity=Severity.MEDIUM,
        reference_url="https://swcregistry.io/docs/SWC-128",
    )

    LOGIC_BUG = AttackVectorInfo(
        name="Logic Bug",
        description=(
            "A flaw in the business logic of the contract—such as incorrect "
            "fee calculations, flawed token distribution, or broken state "
            "machines—that does not fall into a well‑known vulnerability "
            "class but still leads to loss of funds or broken invariants."
        ),
        default_severity=Severity.HIGH,
        reference_url="https://rekt.news/compound-rekt/",
    )

    CENTRALIZATION_RISK = AttackVectorInfo(
        name="Centralization Risk",
        description=(
            "Excessive power is concentrated in a single externally‑owned "
            "account or multisig—e.g. the ability to mint unlimited tokens, "
            "pause the protocol indefinitely, or upgrade to arbitrary "
            "implementations—creating a single point of failure or rug‑pull "
            "vector."
        ),
        default_severity=Severity.MEDIUM,
        reference_url="https://rekt.news/ronin-rekt/",
    )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def info(self) -> AttackVectorInfo:
        """Return the :class:`AttackVectorInfo` metadata for this vector."""
        return self.value

    @property
    def display_name(self) -> str:
        """Human‑readable name suitable for reports and UI labels."""
        return self.value.name

    @property
    def default_severity(self) -> Severity:
        """The default severity level for this attack vector."""
        return self.value.default_severity


# ---------------------------------------------------------------------------
# Module‑level helpers
# ---------------------------------------------------------------------------

def get_all_vectors() -> list[AttackVector]:
    """Return every :class:`AttackVector` member as an ordered list."""
    return list(AttackVector)


def get_vector_by_name(name: str) -> AttackVector | None:
    """Look up an :class:`AttackVector` by its enum member name (case‑insensitive).

    Args:
        name: The member name, e.g. ``"reentrancy"`` or ``"FLASH_LOAN"``.

    Returns:
        The matching :class:`AttackVector`, or ``None`` if not found.
    """
    key = name.strip().upper()
    try:
        return AttackVector[key]
    except KeyError:
        return None


def build_vector_lookup() -> Dict[str, AttackVectorInfo]:
    """Return a ``{MEMBER_NAME: AttackVectorInfo}`` mapping for quick access.

    Useful when you need O(1) lookup by the uppercase enum key.
    """
    return {member.name: member.value for member in AttackVector}
