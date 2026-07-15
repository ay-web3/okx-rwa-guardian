"""
Async block explorer client for fetching verified smart contract source code.

Supports multiple EVM-compatible chains by mapping chain identifiers to
their respective block explorer API endpoints. Uses httpx for non-blocking
HTTP requests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chain registry — maps friendly chain names to explorer API base URLs.
# ---------------------------------------------------------------------------
CHAIN_EXPLORERS: dict[str, str] = {
    "ethereum": "https://api.etherscan.io/api",
    "xlayer": "https://www.okx.com/explorer/xlayer/api",
    "bsc": "https://api.bscscan.com/api",
    "arbitrum": "https://api.arbiscan.io/api",
}


@dataclass
class ContractSource:
    """Structured result from a block explorer source-code query.

    Attributes:
        address: The contract address that was queried.
        chain: The chain identifier (e.g. ``"ethereum"``).
        contract_name: Name of the contract as registered on the explorer.
        source_code: The verified Solidity source code (empty string if
            the contract is not verified).
        compiler_version: The Solidity compiler version used for verification.
        is_verified: Whether the contract source has been verified.
        abi: The contract ABI as a JSON string, if available.
    """

    address: str
    chain: str
    contract_name: str = ""
    source_code: str = ""
    compiler_version: str = ""
    is_verified: bool = False
    abi: str = ""


class ExplorerClientError(Exception):
    """Raised when the block explorer returns an unexpected response."""


class ExplorerClient:
    """Async HTTP client for fetching verified contract source code
    from EVM-compatible block explorers.

    Args:
        api_key: Optional Etherscan-compatible API key.  When not provided
            the key is read from application settings.
        timeout: HTTP request timeout in seconds.

    Example::

        async with ExplorerClient() as client:
            result = await client.fetch_source(
                "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                chain="ethereum",
            )
            if result.is_verified:
                print(result.source_code[:200])
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        self._api_key: str = api_key or settings.etherscan_api_key
        self._xlayer_url: str = settings.xlayer_explorer_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # -- Async context-manager support -------------------------------------

    async def __aenter__(self) -> "ExplorerClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- Private helpers ----------------------------------------------------

    def _get_base_url(self, chain: str) -> str:
        """Resolve the explorer API base URL for the given chain.

        Args:
            chain: A chain identifier (case-insensitive).

        Returns:
            The base URL string.

        Raises:
            ValueError: If the chain is not supported.
        """
        chain_lower = chain.lower().strip()
        if chain_lower == "xlayer":
            return self._xlayer_url
        if chain_lower not in CHAIN_EXPLORERS:
            supported = ", ".join(sorted(CHAIN_EXPLORERS.keys()))
            raise ValueError(
                f"Unsupported chain '{chain}'. Supported chains: {supported}"
            )
        return CHAIN_EXPLORERS[chain_lower]

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Return the active httpx client, creating one if necessary."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    # -- Public API ---------------------------------------------------------

    async def fetch_source(
        self,
        address: str,
        chain: str = "ethereum",
    ) -> ContractSource:
        """Fetch verified source code from a block explorer.

        Sends a ``getsourcecode`` request to the appropriate chain's
        block explorer API and parses the response into a
        :class:`ContractSource` dataclass.

        Args:
            address: The contract address (0x-prefixed, checksummed or not).
            chain: Target chain identifier. One of ``ethereum``, ``xlayer``,
                ``bsc``, or ``arbitrum``.

        Returns:
            A :class:`ContractSource` instance. Check ``is_verified`` to
            determine whether source code was actually returned.

        Raises:
            ExplorerClientError: If the explorer returns an error status.
            httpx.HTTPStatusError: On non-2xx HTTP responses.
        """
        base_url = self._get_base_url(chain)
        client = await self._ensure_client()

        params: dict[str, str] = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        }
        # Attach API key where applicable (most Etherscan-like APIs).
        if self._api_key:
            params["apikey"] = self._api_key

        logger.info(
            "Fetching source for %s on %s from %s", address, chain, base_url
        )

        response = await client.get(base_url, params=params)
        response.raise_for_status()

        data = response.json()

        # Etherscan-compatible APIs use {"status": "1", "result": [...]}.
        if data.get("status") != "1" or not data.get("result"):
            logger.warning(
                "Explorer returned non-success for %s on %s: %s",
                address,
                chain,
                data.get("message", "unknown error"),
            )
            return ContractSource(
                address=address,
                chain=chain,
                is_verified=False,
            )

        result = data["result"][0] if isinstance(data["result"], list) else data["result"]

        source_code = result.get("SourceCode", "")
        contract_name = result.get("ContractName", "")
        compiler_version = result.get("CompilerVersion", "")
        abi = result.get("ABI", "")

        # A contract is considered "not verified" when the source is empty
        # or the ABI field is the sentinel string.
        is_verified = bool(
            source_code
            and abi != "Contract source code not verified"
        )

        return ContractSource(
            address=address,
            chain=chain,
            contract_name=contract_name,
            source_code=source_code,
            compiler_version=compiler_version,
            is_verified=is_verified,
            abi=abi,
        )

    async def close(self) -> None:
        """Explicitly close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
