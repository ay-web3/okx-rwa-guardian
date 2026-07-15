// SPDX-License-Identifier: MIT
// ✅ SECURE CONTRACT - Demonstrates best practices
// This contract follows Solidity security best practices.

pragma solidity 0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract SafeVault is Ownable, ReentrancyGuard {
    mapping(address => uint256) public balances;
    
    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event EmergencyWithdrawn(address indexed owner, uint256 amount);
    
    constructor() Ownable(msg.sender) {}
    
    /// @notice Deposit ETH into the vault
    function deposit() external payable {
        require(msg.value > 0, "Must deposit something");
        balances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value);
    }
    
    /// @notice Withdraw ETH from the vault
    /// @dev Uses checks-effects-interactions pattern + ReentrancyGuard
    function withdraw(uint256 amount) external nonReentrant {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        // GOOD: State update BEFORE external call (checks-effects-interactions)
        balances[msg.sender] -= amount;
        
        // External call after state update
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
        
        emit Withdrawn(msg.sender, amount);
    }
    
    /// @notice Transfer ownership - uses msg.sender (not tx.origin)
    /// @dev Inherited from Ownable - uses onlyOwner modifier
    function transferOwnership(address newOwner) public override onlyOwner {
        super.transferOwnership(newOwner);
    }
    
    /// @notice Emergency withdrawal - owner only
    function emergencyWithdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, "Transfer failed");
        emit EmergencyWithdrawn(msg.sender, balance);
    }
    
    /// @notice Get contract balance
    function getContractBalance() external view returns (uint256) {
        return address(this).balance;
    }
    
    receive() external payable {
        balances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value);
    }
}
