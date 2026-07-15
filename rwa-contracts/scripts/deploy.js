const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with the account:", deployer ? deployer.address : "none");

  const RWAToken = await hre.ethers.getContractFactory("RWAToken");
  const initialSupply = hre.ethers.parseEther("1000000"); // 1 million tokens
  const name = "Miami Beach Villa";
  const symbol = "RWA-MBV";
  const coordinates = "25.790654, -80.130045";

  const rwaToken = await RWAToken.deploy(name, symbol, initialSupply, coordinates);
  await rwaToken.waitForDeployment();

  const address = await rwaToken.getAddress();
  console.log("RWAToken deployed to:", address);

  // Send 0.05 ETH/OKB for liquidity / insurance pool
  const tx = await deployer.sendTransaction({
    to: address,
    value: hre.ethers.parseEther("0.05")
  });
  await tx.wait();
  console.log("Funded contract with 0.05 ETH liquidity");

  // Also manually call fundInsurancePool for 0.05 ETH of that
  const rwaWithSigner = rwaToken.connect(deployer);
  const fundTx = await rwaWithSigner.fundInsurancePool({ value: hre.ethers.parseEther("0.05") });
  await fundTx.wait();
  console.log("Funded insurance pool with 0.05 ETH");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
