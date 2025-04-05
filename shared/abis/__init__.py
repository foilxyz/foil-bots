import json
from pathlib import Path
from typing import Any, Dict, TypedDict

POSITION_MANAGER_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "positions",
        "outputs": [
            {"name": "nonce", "type": "uint96"},
            {"name": "operator", "type": "address"},
            {"name": "token0", "type": "address"},
            {"name": "token1", "type": "address"},
            {"name": "fee", "type": "uint24"},
            {"name": "tickLower", "type": "int24"},
            {"name": "tickUpper", "type": "int24"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"name": "tokensOwed0", "type": "uint128"},
            {"name": "tokensOwed1", "type": "uint128"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    }
]


class ContractJSON(TypedDict):
    address: str
    abi: Dict[str, Any]


class ABILoader:
    def __init__(self):
        self.base_path = Path(__file__).parent
        self._abis: Dict[str, Any] = {}

    def get_abi(self, name: str) -> Dict[str, Any]:
        """Load and cache contract ABI"""
        if name not in self._abis:
            abi_path = self.base_path / f"{name.lower()}.json"
            with open(abi_path) as f:
                contract_data: ContractJSON = json.load(f)
                self._abis[name] = contract_data["abi"]
        return self._abis[name]


abi_loader = ABILoader()
