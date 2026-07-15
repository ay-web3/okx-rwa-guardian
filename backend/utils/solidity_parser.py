"""
Lightweight Solidity source code parser utilities.

Provides regex-based extraction of key structural elements from Solidity
source code. This is NOT a full compiler or AST parser — it performs
fast pattern matching for security analysis pre-processing.
"""

import re


def extract_pragma_version(source: str) -> str | None:
    """Extract the Solidity compiler version from a pragma statement.

    Parses the first ``pragma solidity`` directive found in the source
    and returns the raw version constraint string.

    Args:
        source: Raw Solidity source code.

    Returns:
        The version constraint string (e.g. ``"^0.8.19"``) or ``None``
        if no pragma directive is found.

    Example:
        >>> extract_pragma_version("pragma solidity ^0.8.19;")
        '^0.8.19'
    """
    match = re.search(r"pragma\s+solidity\s+([^;]+);", source)
    return match.group(1).strip() if match else None


def extract_contract_names(source: str) -> list[str]:
    """Extract all contract, interface, and library names from source code.

    Matches declarations of the form ``contract Foo``, ``interface IBar``,
    and ``library Lib``.

    Args:
        source: Raw Solidity source code.

    Returns:
        A list of declared contract/interface/library names.

    Example:
        >>> extract_contract_names("contract MyToken is ERC20 { }")
        ['MyToken']
    """
    pattern = r"\b(?:contract|interface|library)\s+(\w+)"
    return re.findall(pattern, source)


def extract_functions(source: str) -> list[dict]:
    """Extract function signatures and metadata from Solidity source code.

    Parses function declarations to capture the name, visibility modifier,
    other modifiers, and the line number where the function appears.

    Args:
        source: Raw Solidity source code.

    Returns:
        A list of dictionaries, each containing:
            - ``name`` (str): The function name.
            - ``visibility`` (str): The visibility keyword
              (``public``, ``external``, ``internal``, ``private``)
              or ``"public"`` if not explicitly stated.
            - ``modifiers`` (list[str]): Additional modifiers such as
              ``view``, ``pure``, ``payable``, ``onlyOwner``, etc.
            - ``line_number`` (int): The 1-indexed line number.

    Example:
        >>> fns = extract_functions("function transfer(address to, uint256 amount) external returns (bool) {}")
        >>> fns[0]['name']
        'transfer'
    """
    functions: list[dict] = []
    # Match function declarations — captures name and everything up to the
    # opening brace or semicolon (for interface stubs).
    pattern = re.compile(
        r"function\s+(\w+)\s*\([^)]*\)\s*([^{;]*)",
        re.MULTILINE,
    )

    visibility_keywords = {"public", "external", "internal", "private"}
    known_modifiers = {"view", "pure", "payable", "virtual", "override"}

    lines = source.split("\n")
    # Build a quick lookup: character offset → line number.
    line_offsets: list[int] = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line) + 1  # +1 for the newline character

    for match in pattern.finditer(source):
        name = match.group(1)
        qualifiers_raw = match.group(2).strip()

        # Tokenise the qualifier string to find visibility & modifiers.
        tokens = re.findall(r"\w+", qualifiers_raw)

        visibility = "public"  # Solidity default
        modifiers: list[str] = []

        for token in tokens:
            if token in visibility_keywords:
                visibility = token
            elif token in known_modifiers:
                modifiers.append(token)
            elif token == "returns":
                # Stop processing — everything after 'returns' is type info.
                break
            else:
                # Likely a custom modifier (e.g. onlyOwner, nonReentrant).
                modifiers.append(token)

        # Determine line number from character offset.
        char_pos = match.start()
        line_number = 1
        for i, lo in enumerate(line_offsets):
            if lo > char_pos:
                line_number = i  # Previous line (1-indexed due to i starting at 0)
                break
        else:
            line_number = len(lines)

        functions.append(
            {
                "name": name,
                "visibility": visibility,
                "modifiers": modifiers,
                "line_number": line_number,
            }
        )

    return functions


def count_lines(source: str) -> int:
    """Count the total number of lines in the source code.

    Args:
        source: Raw Solidity source code.

    Returns:
        The total line count.
    """
    return len(source.split("\n"))


def has_external_calls(source: str) -> bool:
    """Detect whether the source contains external contract calls.

    Looks for patterns such as ``.call{``, ``.call(``, ``.transfer(``,
    and ``.send(`` which indicate interaction with external addresses.

    Args:
        source: Raw Solidity source code.

    Returns:
        ``True`` if external call patterns are found.
    """
    patterns = [
        r"\.call\s*[\({]",
        r"\.delegatecall\s*[\({]",
        r"\.staticcall\s*[\({]",
        r"\.transfer\s*\(",
        r"\.send\s*\(",
    ]
    combined = "|".join(patterns)
    return bool(re.search(combined, source))


def has_delegatecall(source: str) -> bool:
    """Detect whether the source uses ``delegatecall``.

    ``delegatecall`` executes code in another contract's context while
    preserving the caller's storage, which is a common proxy pattern
    but also a significant attack surface.

    Args:
        source: Raw Solidity source code.

    Returns:
        ``True`` if ``delegatecall`` usage is found.
    """
    return bool(re.search(r"\.delegatecall\s*[\({]", source))


def has_selfdestruct(source: str) -> bool:
    """Detect whether the source uses ``selfdestruct`` or ``suicide``.

    Both opcodes destroy the contract and forcefully send remaining
    Ether to a target address. ``suicide`` is the deprecated alias.

    Args:
        source: Raw Solidity source code.

    Returns:
        ``True`` if ``selfdestruct`` or ``suicide`` usage is found.
    """
    return bool(re.search(r"\b(?:selfdestruct|suicide)\s*\(", source))
