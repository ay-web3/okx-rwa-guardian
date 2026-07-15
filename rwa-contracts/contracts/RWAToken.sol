// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

contract RWAToken is ERC20, Ownable, Pausable {
    uint8 public healthScore = 100;
    uint256 public valuation;
    string public propertyCoordinates;
    uint256 public tokenPrice = 0.01 ether;
    
    uint256 public yieldRate = 100; // basis points (1%)
    uint256 public insurancePool;

    event HealthScoreUpdated(uint8 oldScore, uint8 newScore);
    event ValuationUpdated(uint256 oldValuation, uint256 newValuation);
    event TradingPaused(address account);
    event TradingUnpaused(address account);
    event YieldRateUpdated(uint256 oldRate, uint256 newRate);
    event InsurancePayoutTriggered(uint256 totalAmount);
    event TokensSold(address seller, uint256 amount, uint256 payout);

    constructor(
        string memory name,
        string memory symbol,
        uint256 initialSupply,
        string memory _propertyCoordinates
    ) ERC20(name, symbol) Ownable(msg.sender) {
        propertyCoordinates = _propertyCoordinates;
        _mint(msg.sender, initialSupply);
    }

    function pauseTrading() public onlyOwner {
        _pause();
        emit TradingPaused(msg.sender);
    }

    function unpauseTrading() public onlyOwner {
        _unpause();
        emit TradingUnpaused(msg.sender);
    }

    function updateHealthScore(uint8 newScore) public onlyOwner {
        uint8 oldScore = healthScore;
        healthScore = newScore;
        emit HealthScoreUpdated(oldScore, newScore);
    }

    function updateValuation(uint256 newValuation) public onlyOwner {
        uint256 oldValuation = valuation;
        valuation = newValuation;
        emit ValuationUpdated(oldValuation, newValuation);
    }

    function buyTokens(uint256 amount) public payable whenNotPaused {
        require(msg.value >= amount * tokenPrice, "Insufficient payment");
        _mint(msg.sender, amount);
    }

    function setYieldRate(uint256 _newRate) external onlyOwner {
        uint256 oldRate = yieldRate;
        yieldRate = _newRate;
        emit YieldRateUpdated(oldRate, _newRate);
    }

    function triggerInsurancePayout() external onlyOwner {
        uint256 payout = insurancePool;
        insurancePool = 0;
        emit InsurancePayoutTriggered(payout);
        // In a real implementation, this would distribute funds to holders.
        // For the hackathon demo, we just emit the event to log the action.
    }

    function sellTokens(uint256 amount) public whenNotPaused {
        require(balanceOf(msg.sender) >= amount, "Insufficient token balance");
        uint256 payout = amount * tokenPrice;
        require(address(this).balance >= payout, "Contract lacks liquidity");
        
        _burn(msg.sender, amount);
        (bool success, ) = msg.sender.call{value: payout}("");
        require(success, "Transfer failed");
        emit TokensSold(msg.sender, amount, payout);
    }

    function fundInsurancePool() external payable {
        insurancePool += msg.value;
    }

    receive() external payable {}
    fallback() external payable {}

    // Overwrite _update to enforce whenNotPaused
    function _update(address from, address to, uint256 value) internal override whenNotPaused {
        super._update(from, to, value);
    }
}
