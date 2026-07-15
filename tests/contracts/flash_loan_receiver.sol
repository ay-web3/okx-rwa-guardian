// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0; // Vulnerability: Floating pragma

contract FlashLoanReceiver {
    // Vulnerability: Hardcoded address
    address public constant DEX_ROUTER = 0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D;
    
    address public owner;
    mapping(address => uint256) public balances;
    address[] public users;

    constructor() {
        owner = msg.sender;
    }

    // Vulnerability: Missing Access Control
    function updateOwner(address newOwner) public {
        owner = newOwner;
    }

    // Vulnerability: tx.origin Authentication
    function withdrawAll() public {
        require(tx.origin == owner, "Only owner can withdraw");
        
        // Vulnerability: Unchecked Return Value
        msg.sender.call{value: address(this).balance}("");
    }

    function processFlashLoan(uint256 amount) public {
        // Vulnerability: Unsafe Arithmetic (Pragma <0.8.0, no SafeMath)
        balances[msg.sender] = balances[msg.sender] + amount;
        users.push(msg.sender);
    }

    function distributeYield() public {
        // Vulnerability: Unbounded Loop
        for(uint256 i = 0; i < users.length; i++) {
            balances[users[i]] = balances[users[i]] + 1;
        }
    }
}
