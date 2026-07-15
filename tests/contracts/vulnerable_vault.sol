// SPDX-License-Identifier: MIT
// ⚠️ DELIBERATELY VULNERABLE - FOR TESTING ONLY
// This contract contains multiple security vulnerabilities for demonstration purposes.

pragma solidity ^0.7.0;

contract VulnerableVault {
    mapping(address => uint256) public balances;
    address public owner;
    address[] public depositors;
    
    // SCA-010: Hardcoded address (centralization risk)
    address constant TREASURY = 0xdEAD000000000000000042069420694206942069;
    
    constructor() {
        owner = msg.sender;
    }
    
    // Deposit ETH into the vault
    function deposit() public payable {
        require(msg.value > 0, "Must deposit something");
        balances[msg.sender] += msg.value;
        depositors.push(msg.sender);
    }
    
    // SCA-001: REENTRANCY VULNERABILITY
    // External call happens BEFORE state update
    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        // BAD: External call before state update
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
        
        // State update AFTER external call = reentrancy!
        balances[msg.sender] -= amount;
    }
    
    // SCA-003: tx.origin authentication
    // Should use msg.sender instead
    function transferOwnership(address newOwner) public {
        require(tx.origin == owner, "Not owner");
        owner = newOwner;
    }
    
    // SCA-009: Missing access control on sensitive function
    // Anyone can call this!
    function emergencyWithdraw() public {
        // No access control modifier
        uint256 balance = address(this).balance;
        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, "Transfer failed");
    }
    
    // SCA-004: Unprotected selfdestruct
    function destroy() public {
        selfdestruct(payable(msg.sender));
    }
    
    // SCA-006: Unsafe arithmetic (pre-0.8.0, no SafeMath)
    function addReward(address user, uint256 reward) public {
        // Integer overflow possible in Solidity < 0.8.0
        balances[user] = balances[user] + reward;
    }
    
    // SCA-008: Unbounded loop over dynamic array
    function distributeRewards(uint256 amount) public {
        // Gas limit DoS: if depositors array grows too large,
        // this function becomes uncallable
        for (uint256 i = 0; i < depositors.length; i++) {
            balances[depositors[i]] += amount;
        }
    }
    
    // SCA-002: Unchecked return value
    function unsafeSend(address payable recipient, uint256 amount) public {
        // Return value not checked!
        recipient.call{value: amount}("");
    }
    
    // SCA-007: Delegatecall with user-controllable input
    function execute(address target, bytes memory data) public {
        // Dangerous: delegatecall to user-provided address
        (bool success, ) = target.delegatecall(data);
        require(success, "Execution failed");
    }
    
    receive() external payable {
        balances[msg.sender] += msg.value;
    }
}
