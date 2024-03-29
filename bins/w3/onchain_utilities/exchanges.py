import logging
import sys
import math

from decimal import Decimal
from hexbytes import HexBytes
from web3 import Web3

from bins.configuration import CONFIGURATION, WEB3_CHAIN_IDS
from bins.formulas import dex_formulas
from bins.w3.onchain_utilities.basic import web3wrap, erc20, erc20_cached
from bins.cache import cache_utilities


class univ3_pool(web3wrap):
    # SETUP
    def __init__(
        self,
        address: str,
        network: str,
        abi_filename: str = "",
        abi_path: str = "",
        block: int = 0,
        timestamp: int = 0,
        custom_web3: Web3 | None = None,
        custom_web3Url: str | None = None,
    ):
        self._abi_filename = abi_filename or "univ3_pool"
        self._abi_path = abi_path or "data/abi/uniswap/v3"

        self._token0: erc20 = None
        self._token1: erc20 = None

        super().__init__(
            address=address,
            network=network,
            abi_filename=self._abi_filename,
            abi_path=self._abi_path,
            block=block,
            timestamp=timestamp,
            custom_web3=custom_web3,
            custom_web3Url=custom_web3Url,
        )

    # PROPERTIES
    @property
    def factory(self) -> str:
        return self.call_function_autoRpc("factory")

    @property
    def fee(self) -> int:
        """The pool's fee in hundredths of a bip, i.e. 1e-6"""
        return self.call_function_autoRpc("fee")

    @property
    def feeGrowthGlobal0X128(self) -> int:
        """The fee growth as a Q128.128 fees of token0 collected per unit of liquidity for the entire life of the pool
        Returns:
           int: as Q128.128 fees of token0
        """
        return self.call_function_autoRpc("feeGrowthGlobal0X128")

    @property
    def feeGrowthGlobal1X128(self) -> int:
        """The fee growth as a Q128.128 fees of token1 collected per unit of liquidity for the entire life of the pool
        Returns:
           int: as Q128.128 fees of token1
        """
        return self.call_function_autoRpc("feeGrowthGlobal1X128")

    @property
    def liquidity(self) -> int:
        return self.call_function_autoRpc("liquidity")

    @property
    def maxLiquidityPerTick(self) -> int:
        return self.call_function_autoRpc("maxLiquidityPerTick")

    def observations(self, input: int):
        return self.call_function_autoRpc("observations", None, input)

    def observe(self, secondsAgo: int):
        """observe _summary_

        Args:
           secondsAgo (int): _description_

        Returns:
           _type_: tickCumulatives   int56[] :  12731930095582
                   secondsPerLiquidityCumulativeX128s   uint160[] :  242821134689165142944235398318169

        """
        return self.call_function_autoRpc("observe", None, secondsAgo)

    def positions(self, position_key: str) -> dict:
        """

        Args:
           position_key (str): 0x....

        Returns:
           _type_:
                   liquidity   uint128 :  99225286851746
                   feeGrowthInside0LastX128   uint256 :  0
                   feeGrowthInside1LastX128   uint256 :  0
                   tokensOwed0   uint128 :  0
                   tokensOwed1   uint128 :  0
        """
        position_key = (
            HexBytes(position_key) if type(position_key) == str else position_key
        )
        result = self.call_function_autoRpc("positions", None, position_key)
        return {
            "liquidity": result[0],
            "feeGrowthInside0LastX128": result[1],
            "feeGrowthInside1LastX128": result[2],
            "tokensOwed0": result[3],
            "tokensOwed1": result[4],
        }

    @property
    def protocolFees(self) -> list[int]:
        """
        Returns:
           list: [0,0]

        """
        return self.call_function_autoRpc("protocolFees")

    @property
    def slot0(self) -> dict:
        """The 0th storage slot in the pool stores many values, and is exposed as a single method to save gas when accessed externally.

        Returns:
           _type_: sqrtPriceX96   uint160 :  28854610805518743926885543006518067
                   tick   int24 :  256121
                   observationIndex   uint16 :  198
                   observationCardinality   uint16 :  300
                   observationCardinalityNext   uint16 :  300
                   feeProtocol   uint8 :  0
                   unlocked   bool :  true
        """
        tmp = self.call_function_autoRpc("slot0")
        return {
            "sqrtPriceX96": tmp[0],
            "tick": tmp[1],
            "observationIndex": tmp[2],
            "observationCardinality": tmp[3],
            "observationCardinalityNext": tmp[4],
            "feeProtocol": tmp[5],
            "unlocked": tmp[6],
        }

    def snapshotCumulativeInside(self, tickLower: int, tickUpper: int):
        return self.call_function_autoRpc(
            "snapshotCumulativeInside", None, tickLower, tickUpper
        )

    def tickBitmap(self, input: int) -> int:
        return self.call_function_autoRpc("tickBitmap", None, input)

    @property
    def tickSpacing(self) -> int:
        return self.call_function_autoRpc("tickSpacing")

    def ticks(self, tick: int) -> dict:
        """

        Args:
           tick (int):

        Returns:
           _type_:     liquidityGross   uint128 :  0
                       liquidityNet   int128 :  0
                       feeGrowthOutside0X128   uint256 :  0
                       feeGrowthOutside1X128   uint256 :  0
                       tickCumulativeOutside   int56 :  0
                       spoolecondsPerLiquidityOutsideX128   uint160 :  0
                       secondsOutside   uint32 :  0
                       initialized   bool :  false
        """
        result = self.call_function_autoRpc("ticks", None, tick)
        return {
            "liquidityGross": result[0],
            "liquidityNet": result[1],
            "feeGrowthOutside0X128": result[2],
            "feeGrowthOutside1X128": result[3],
            "tickCumulativeOutside": result[4],
            "secondsPerLiquidityOutsideX128": result[5],
            "secondsOutside": result[6],
            "initialized": result[7],
        }

    @property
    def token0(self) -> erc20:
        """The first of the two tokens of the pool, sorted by address

        Returns:
        """
        if self._token0 is None:
            self._token0 = erc20(
                address=self.call_function_autoRpc("token0"),
                network=self._network,
                block=self.block,
            )
        return self._token0

    @property
    def token1(self) -> erc20:
        """The second of the two tokens of the pool, sorted by address_

        Returns:
           erc20:
        """
        if self._token1 is None:
            self._token1 = erc20(
                address=self.call_function_autoRpc("token1"),
                network=self._network,
                block=self.block,
            )
        return self._token1

    # CUSTOM PROPERTIES
    @property
    def block(self) -> int:
        return self._block

    @block.setter
    def block(self, value: int):
        # set block
        self._block = value
        self.token0.block = value
        self.token1.block = value

    # CUSTOM FUNCTIONS
    def position(self, ownerAddress: str, tickLower: int, tickUpper: int) -> dict:
        """

        Returns:
           dict:
                   liquidity   uint128 :  99225286851746
                   feeGrowthInside0LastX128   uint256 :  0
                   feeGrowthInside1LastX128   uint256 :  0
                   tokensOwed0   uint128 :  0
                   tokensOwed1   uint128 :  0
        """
        return self.positions(
            dex_formulas.get_positionKey(
                ownerAddress=ownerAddress,
                tickLower=tickLower,
                tickUpper=tickUpper,
            )
        )

    def get_qtty_depoloyed(
        self, ownerAddress: str, tickUpper: int, tickLower: int, inDecimal: bool = True
    ) -> dict:
        """Retrieve the quantity of tokens currently deployed

        Args:
           ownerAddress (str):
           tickUpper (int):
           tickLower (int):
           inDecimal (bool): return result in a decimal format?

        Returns:
           dict: {
                   "qtty_token0":0,        (int or Decimal) # quantity of token 0 deployed in dex
                   "qtty_token1":0,        (int or Decimal) # quantity of token 1 deployed in dex
                   "fees_owed_token0":0,   (int or Decimal) # quantity of token 0 fees owed to the position ( not included in qtty_token0 and this is not uncollected fees)
                   "fees_owed_token1":0,   (int or Decimal) # quantity of token 1 fees owed to the position ( not included in qtty_token1 and this is not uncollected fees)
                 }
        """

        result = {
            "qtty_token0": 0,  # quantity of token 0 deployed in dex
            "qtty_token1": 0,  # quantity of token 1 deployed in dex
            "fees_owed_token0": 0,  # quantity of token 0 fees owed to the position ( not included in qtty_token0 and this is not uncollected fees)
            "fees_owed_token1": 0,  # quantity of token 1 fees owed to the position ( not included in qtty_token1 and this is not uncollected fees)
        }

        # get position data
        pos = self.position(
            ownerAddress=Web3.toChecksumAddress(ownerAddress.lower()),
            tickLower=tickLower,
            tickUpper=tickUpper,
        )
        # get slot data
        slot0 = self.slot0

        # get current tick from slot
        tickCurrent = slot0["tick"]
        sqrtRatioX96 = slot0["sqrtPriceX96"]
        sqrtRatioAX96 = dex_formulas.TickMath.getSqrtRatioAtTick(tickLower)
        sqrtRatioBX96 = dex_formulas.TickMath.getSqrtRatioAtTick(tickUpper)
        # calc quantity from liquidity
        (
            result["qtty_token0"],
            result["qtty_token1"],
        ) = dex_formulas.LiquidityAmounts.getAmountsForLiquidity(
            sqrtRatioX96, sqrtRatioAX96, sqrtRatioBX96, pos["liquidity"]
        )

        # add owed tokens
        result["fees_owed_token0"] = pos["tokensOwed0"]
        result["fees_owed_token1"] = pos["tokensOwed1"]

        # convert to decimal as needed
        if inDecimal:
            self._get_qtty_depoloyed_todecimal(result)
        # return result
        return result.copy()

    def _get_qtty_depoloyed_todecimal(self, result):
        # get token decimals
        decimals_token0 = self.token0.decimals
        decimals_token1 = self.token1.decimals

        result["qtty_token0"] = Decimal(result["qtty_token0"]) / Decimal(
            10**decimals_token0
        )
        result["qtty_token1"] = Decimal(result["qtty_token1"]) / Decimal(
            10**decimals_token1
        )
        result["fees_owed_token0"] = Decimal(result["fees_owed_token0"]) / Decimal(
            10**decimals_token0
        )
        result["fees_owed_token1"] = Decimal(result["fees_owed_token1"]) / Decimal(
            10**decimals_token1
        )

    def get_fees_uncollected(
        self, ownerAddress: str, tickUpper: int, tickLower: int, inDecimal: bool = True
    ) -> dict:
        """Retrieve the quantity of fees not collected nor yet owed ( but certain) to the deployed position

        Args:
            ownerAddress (str):
            tickUpper (int):
            tickLower (int):
            inDecimal (bool): return result in a decimal format?

        Returns:
            dict: {
                    "qtty_token0":0,   (int or Decimal)     # quantity of uncollected token 0
                    "qtty_token1":0,   (int or Decimal)     # quantity of uncollected token 1
                }
        """

        result = {
            "qtty_token0": 0,
            "qtty_token1": 0,
        }

        # get position data
        pos = self.position(
            ownerAddress=Web3.toChecksumAddress(ownerAddress.lower()),
            tickLower=tickLower,
            tickUpper=tickUpper,
        )

        # get ticks
        tickCurrent = self.slot0["tick"]
        ticks_lower = self.ticks(tickLower)
        ticks_upper = self.ticks(tickUpper)

        (
            result["qtty_token0"],
            result["qtty_token1"],
        ) = dex_formulas.get_uncollected_fees_vGammawire(
            fee_growth_global_0=self.feeGrowthGlobal0X128,
            fee_growth_global_1=self.feeGrowthGlobal1X128,
            tick_current=tickCurrent,
            tick_lower=tickLower,
            tick_upper=tickUpper,
            fee_growth_outside_0_lower=ticks_lower["feeGrowthOutside0X128"],
            fee_growth_outside_1_lower=ticks_lower["feeGrowthOutside1X128"],
            fee_growth_outside_0_upper=ticks_upper["feeGrowthOutside0X128"],
            fee_growth_outside_1_upper=ticks_upper["feeGrowthOutside1X128"],
            liquidity=pos["liquidity"],
            fee_growth_inside_last_0=pos["feeGrowthInside0LastX128"],
            fee_growth_inside_last_1=pos["feeGrowthInside1LastX128"],
        )

        # convert to decimal as needed
        if inDecimal:
            result["qtty_token0"] = Decimal(result["qtty_token0"]) / Decimal(
                10**self.token0.decimals
            )
            result["qtty_token1"] = Decimal(result["qtty_token1"]) / Decimal(
                10**self.token1.decimals
            )

        # return result
        return result.copy()

    def as_dict(self, convert_bint=False, static_mode: bool = False) -> dict:
        """as_dict _summary_

        Args:
            convert_bint (bool, optional): convert big integers to string . Defaults to False.
            static_mode (bool, optional): return only static pool parameters. Defaults to False.

        Returns:
            dict:
        """
        result = super().as_dict(convert_bint=convert_bint)

        # result["factory"] = self.factory
        result["fee"] = self.fee

        # t spacing
        result["tickSpacing"] = (
            str(self.tickSpacing) if convert_bint else self.tickSpacing
        )

        # identify pool dex
        result["dex"] = self.identify_dex_name()

        # tokens
        result["token0"] = self.token0.as_dict(convert_bint=convert_bint)
        result["token1"] = self.token1.as_dict(convert_bint=convert_bint)

        # protocolFees
        result["protocolFees"] = self.protocolFees
        if convert_bint:
            result["protocolFees"] = [str(i) for i in result["protocolFees"]]

        if not static_mode:
            self._as_dict_not_static_items(convert_bint, result)
        return result

    def _as_dict_not_static_items(self, convert_bint, result):
        result["feeGrowthGlobal0X128"] = (
            str(self.feeGrowthGlobal0X128)
            if convert_bint
            else self.feeGrowthGlobal0X128
        )

        result["feeGrowthGlobal1X128"] = (
            str(self.feeGrowthGlobal1X128)
            if convert_bint
            else self.feeGrowthGlobal1X128
        )

        result["liquidity"] = str(self.liquidity) if convert_bint else self.liquidity
        result["maxLiquidityPerTick"] = (
            str(self.maxLiquidityPerTick) if convert_bint else self.maxLiquidityPerTick
        )

        # slot0
        result["slot0"] = self.slot0
        if convert_bint:
            result["slot0"]["sqrtPriceX96"] = str(result["slot0"]["sqrtPriceX96"])
            result["slot0"]["tick"] = str(result["slot0"]["tick"])
            result["slot0"]["observationIndex"] = str(
                result["slot0"]["observationIndex"]
            )
            result["slot0"]["observationCardinality"] = str(
                result["slot0"]["observationCardinality"]
            )
            result["slot0"]["observationCardinalityNext"] = str(
                result["slot0"]["observationCardinalityNext"]
            )


class univ3_pool_cached(univ3_pool):
    SAVE2FILE = True

    # SETUP
    def setup_cache(self):
        # define network
        if self._network in WEB3_CHAIN_IDS:
            self._chain_id = WEB3_CHAIN_IDS[self._network]
        else:
            self._chain_id = self.w3.eth.chain_id

        # made up a descriptive cahce file name
        cache_filename = f"{self._chain_id}_{self.address.lower()}"

        fixed_fields = {
            "decimals": False,
            "symbol": False,
            "factory": False,
            "fee": False,
        }

        # create cache helper
        self._cache = cache_utilities.mutable_property_cache(
            filename=cache_filename,
            folder_name="data/cache/onchain",
            reset=False,
            fixed_fields=fixed_fields,
        )

    # PROPERTIES
    @property
    def factory(self) -> str:
        prop_name = "factory"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def fee(self) -> int:
        """The pool's fee in hundredths of a bip, i.e. 1e-6"""
        prop_name = "fee"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def feeGrowthGlobal0X128(self) -> int:
        """The fee growth as a Q128.128 fees of token0 collected per unit of liquidity for the entire life of the pool
        Returns:
           int: as Q128.128 fees of token0
        """
        prop_name = "feeGrowthGlobal0X128"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def feeGrowthGlobal1X128(self) -> int:
        """The fee growth as a Q128.128 fees of token1 collected per unit of liquidity for the entire life of the pool
        Returns:
           int: as Q128.128 fees of token1
        """
        prop_name = "feeGrowthGlobal1X128"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def liquidity(self) -> int:
        prop_name = "liquidity"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def maxLiquidityPerTick(self) -> int:
        prop_name = "maxLiquidityPerTick"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def protocolFees(self) -> list:
        """The amounts of token0 and token1 that are owed to the protocol

        Returns:
           list: token0   uint128 :  0, token1   uint128 :  0
        """
        prop_name = "protocolFees"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result.copy()

    @property
    def slot0(self) -> dict:
        """The 0th storage slot in the pool stores many values, and is exposed as a single method to save gas when accessed externally.

        Returns:
           _type_: sqrtPriceX96   uint160 :  28854610805518743926885543006518067
                   tick   int24 :  256121
                   observationIndex   uint16 :  198
                   observationCardinality   uint16 :  300
                   observationCardinalityNext   uint16 :  300
                   feeProtocol   uint8 :  0
                   unlocked   bool :  true
        """
        prop_name = "slot0"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result.copy()

    @property
    def tickSpacing(self) -> int:
        prop_name = "tickSpacing"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def token0(self) -> erc20:
        """The first of the two tokens of the pool, sorted by address

        Returns:
           erc20:
        """
        if self._token0 is None:
            self._token0 = erc20_cached(
                address=self._contract.functions.token0().call(
                    block_identifier=self.block
                ),
                network=self._network,
                block=self.block,
            )
        return self._token0

    @property
    def token1(self) -> erc20:
        """The second of the two tokens of the pool, sorted by address_

        Returns:
           erc20:
        """
        if self._token1 is None:
            self._token1 = erc20_cached(
                address=self._contract.functions.token1().call(
                    block_identifier=self.block
                ),
                network=self._network,
                block=self.block,
            )
        return self._token1


class algebrav3_dataStorageOperator(web3wrap):
    # SETUP
    def __init__(
        self,
        address: str,
        network: str,
        abi_filename: str = "",
        abi_path: str = "",
        block: int = 0,
        timestamp: int = 0,
        custom_web3: Web3 | None = None,
        custom_web3Url: str | None = None,
    ):
        self._abi_filename = abi_filename or "dataStorageOperator"
        self._abi_path = abi_path or "data/abi/algebra/v3"

        super().__init__(
            address=address,
            network=network,
            abi_filename=self._abi_filename,
            abi_path=self._abi_path,
            block=block,
            timestamp=timestamp,
            custom_web3=custom_web3,
            custom_web3Url=custom_web3Url,
        )

    # TODO: Implement contract functs calculateVolumePerLiquidity, getAverages, getFee, getSingleTimepoint, getTimepoints and timepoints

    @property
    def feeConfig(self) -> dict:
        """feeConfig _summary_

        Returns:
            dict:   { alpha1   uint16 :  100
                        alpha2   uint16 :  3600
                        beta1   uint32 :  500
                        beta2   uint32 :  80000
                        gamma1   uint16 :  80
                        gamma2   uint16 :  11750
                        volumeBeta   uint32 :  0
                        volumeGamma   uint16 :  10
                        baseFee   uint16 :  400 }

        """
        return self.call_function_autoRpc("feeConfig")

    @property
    def window(self) -> int:
        """window _summary_

        Returns:
            int: 86400 uint32
        """
        return self.call_function_autoRpc("window")


class algebrav3_dataStorageOperator_cached(algebrav3_dataStorageOperator):
    @property
    def feeConfig(self) -> dict:
        prop_name = "feeConfig"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result


class algebrav3_pool(web3wrap):
    # SETUP
    def __init__(
        self,
        address: str,
        network: str,
        abi_filename: str = "",
        abi_path: str = "",
        block: int = 0,
        timestamp: int = 0,
        custom_web3: Web3 | None = None,
        custom_web3Url: str | None = None,
    ):
        self._abi_filename = abi_filename or "algebrav3pool"
        self._abi_path = abi_path or "data/abi/algebra/v3"

        self._token0: erc20 = None
        self._token1: erc20 = None

        self._dataStorage: algebrav3_dataStorageOperator = None

        super().__init__(
            address=address,
            network=network,
            abi_filename=self._abi_filename,
            abi_path=self._abi_path,
            block=block,
            timestamp=timestamp,
            custom_web3=custom_web3,
            custom_web3Url=custom_web3Url,
        )

    # SETUP
    def setup_cache(self):
        # define network
        if self._network in WEB3_CHAIN_IDS:
            self._chain_id = WEB3_CHAIN_IDS[self._network]
        else:
            self._chain_id = self.w3.eth.chain_id

        # made up a descriptive cahce file name
        cache_filename = f"{self._chain_id}_{self.address.lower()}"

        fixed_fields = {
            "decimals": False,
            "symbol": False,
            "factory": False,
            "tickSpacing": False,
        }

        # create cache helper
        self._cache = cache_utilities.mutable_property_cache(
            filename=cache_filename,
            folder_name="data/cache/onchain",
            reset=False,
            fixed_fields=fixed_fields,
        )

    # PROPERTIES

    @property
    def activeIncentive(self) -> str:
        """activeIncentive

        Returns:
            str: address
        """
        return self.call_function_autoRpc("activeIncentive")

    @property
    def dataStorageOperator(self) -> algebrav3_dataStorageOperator:
        """ """
        if self._dataStorage is None:
            self._dataStorage = algebrav3_dataStorageOperator(
                address=self.call_function_autoRpc("dataStorageOperator"),
                network=self._network,
                block=self.block,
            )
        return self._dataStorage

    @property
    def factory(self) -> str:
        return self.call_function_autoRpc("factory")

    def getInnerCumulatives(self, bottomTick: int, topTick: int):
        """

        Args:
            bottomTick (int): _description_
            topTick (int): _description_

        Returns:
            innerSecondsSpentPerLiquidity uint160, innerSecondsSpent uint32
        """
        return self.call_function_autoRpc(
            "getInnerCumulatives", None, bottomTick, topTick
        )

    def getTimepoints(self, secondsAgo: int) -> dict:
        return self.call_function_autoRpc("getTimepoints", None, secondsAgo)

    @property
    def globalState(self) -> dict:
        """

        Returns:
           dict:   sqrtPriceX96  uint160 :  28854610805518743926885543006518067  ( <price> at contract level)
                   tick   int24 :  256121
                   fee   uint16 :  198
                   timepointIndex   uint16 :  300
                   communityFeeToken0   uint8 :  300
                   communityFeeToken1   uint8 :  0
                   unlocked   bool :  true
        """
        tmp = self.call_function_autoRpc("globalState")
        return {
            "sqrtPriceX96": tmp[0],
            "tick": tmp[1],
            "fee": tmp[2],
            "timepointIndex": tmp[3],
            "communityFeeToken0": tmp[4],
            "communityFeeToken1": tmp[5],
            "unlocked": tmp[6],
        }

    @property
    def liquidity(self) -> int:
        """liquidity _summary_

        Returns:
            int: 14468296980040792163 uint128
        """
        return self.call_function_autoRpc("liquidity")

    @property
    def liquidityCooldown(self) -> int:
        """liquidityCooldown _summary_

        Returns:
            int: 0 uint32
        """
        return self.call_function_autoRpc("liquidityCooldown")

    @property
    def maxLiquidityPerTick(self) -> int:
        """maxLiquidityPerTick _summary_

        Returns:
            int: 11505743598341114571880798222544994 uint128
        """
        return self.call_function_autoRpc("maxLiquidityPerTick")

    def positions(self, position_key: str) -> dict:
        """

        Args:
           position_key (str): 0x....

        Returns:
           _type_:
                   liquidity   uint128 :  99225286851746
                   lastLiquidityAddTimestamp
                   innerFeeGrowth0Token   uint256 :  (feeGrowthInside0LastX128)
                   innerFeeGrowth1Token   uint256 :  (feeGrowthInside1LastX128)
                   fees0   uint128 :  0  (tokensOwed0)
                   fees1   uint128 :  0  ( tokensOwed1)
        """
        position_key = (
            HexBytes(position_key) if type(position_key) == str else position_key
        )
        result = self.call_function_autoRpc("positions", None, position_key)
        return {
            "liquidity": result[0],
            "lastLiquidityAddTimestamp": result[1],
            "feeGrowthInside0LastX128": result[2],
            "feeGrowthInside1LastX128": result[3],
            "tokensOwed0": result[4],
            "tokensOwed1": result[5],
        }

    @property
    def tickSpacing(self) -> int:
        """tickSpacing _summary_

        Returns:
            int: 60 int24
        """
        return self.call_function_autoRpc("tickSpacing")

    def tickTable(self, value: int) -> int:
        return self.call_function_autoRpc("tickTable", None, value)

    def ticks(self, tick: int) -> dict:
        """

        Args:
           tick (int):

        Returns:
           _type_:     liquidityGross   uint128 :  0        liquidityTotal
                       liquidityNet   int128 :  0           liquidityDelta
                       feeGrowthOutside0X128   uint256 :  0 outerFeeGrowth0Token
                       feeGrowthOutside1X128   uint256 :  0 outerFeeGrowth1Token
                       tickCumulativeOutside   int56 :  0   outerTickCumulative
                       spoolecondsPerLiquidityOutsideX128   uint160 :  0    outerSecondsPerLiquidity
                       secondsOutside   uint32 :  0         outerSecondsSpent
                       initialized   bool :  false          initialized
        """
        result = self.call_function_autoRpc("ticks", None, tick)
        return {
            "liquidityGross": result[0],
            "liquidityNet": result[1],
            "feeGrowthOutside0X128": result[2],
            "feeGrowthOutside1X128": result[3],
            "tickCumulativeOutside": result[4],
            "secondsPerLiquidityOutsideX128": result[5],
            "secondsOutside": result[6],
            "initialized": result[7],
        }

    def timepoints(self, index: int) -> dict:
        #   initialized bool, blockTimestamp uint32, tickCumulative int56, secondsPerLiquidityCumulative uint160, volatilityCumulative uint88, averageTick int24, volumePerLiquidityCumulative uint144
        return self.call_function_autoRpc("timepoints", None, index)

    @property
    def token0(self) -> erc20:
        """The first of the two tokens of the pool, sorted by address

        Returns:
           erc20:
        """
        if self._token0 is None:
            self._token0 = erc20(
                address=self.call_function_autoRpc("token0"),
                network=self._network,
                block=self.block,
            )
        return self._token0

    @property
    def token1(self) -> erc20:
        if self._token1 is None:
            self._token1 = erc20(
                address=self.call_function_autoRpc("token1"),
                network=self._network,
                block=self.block,
            )
        return self._token1

    @property
    def feeGrowthGlobal0X128(self) -> int:
        """The fee growth as a Q128.128 fees of token0 collected per unit of liquidity for the entire life of the pool
        Returns:
           int: as Q128.128 fees of token0
        """
        return self.call_function_autoRpc("totalFeeGrowth0Token")

    @property
    def feeGrowthGlobal1X128(self) -> int:
        """The fee growth as a Q128.128 fees of token1 collected per unit of liquidity for the entire life of the pool
        Returns:
           int: as Q128.128 fees of token1
        """
        return self.call_function_autoRpc("totalFeeGrowth1Token")

    # CUSTOM PROPERTIES
    @property
    def block(self) -> int:
        return self._block

    @block.setter
    def block(self, value: int):
        # set block
        self._block = value
        self.token0.block = value
        self.token1.block = value

    # CUSTOM FUNCTIONS
    def position(self, ownerAddress: str, tickLower: int, tickUpper: int) -> dict:
        """

        Returns:
           dict:
                   liquidity   uint128 :  99225286851746
                   feeGrowthInside0LastX128   uint256 :  0
                   feeGrowthInside1LastX128   uint256 :  0
                   tokensOwed0   uint128 :  0
                   tokensOwed1   uint128 :  0
        """
        return self.positions(
            dex_formulas.get_positionKey_algebra(
                ownerAddress=ownerAddress,
                tickLower=tickLower,
                tickUpper=tickUpper,
            )
        )

    def get_qtty_depoloyed(
        self, ownerAddress: str, tickUpper: int, tickLower: int, inDecimal: bool = True
    ) -> dict:
        """Retrieve the quantity of tokens currently deployed

        Args:
           ownerAddress (str):
           tickUpper (int):
           tickLower (int):
           inDecimal (bool): return result in a decimal format?

        Returns:
           dict: {
                   "qtty_token0":0,        (int or Decimal) # quantity of token 0 deployed in dex
                   "qtty_token1":0,        (int or Decimal) # quantity of token 1 deployed in dex
                   "fees_owed_token0":0,   (int or Decimal) # quantity of token 0 fees owed to the position ( not included in qtty_token0 and this is not uncollected fees)
                   "fees_owed_token1":0,   (int or Decimal) # quantity of token 1 fees owed to the position ( not included in qtty_token1 and this is not uncollected fees)
                 }
        """

        result = {
            "qtty_token0": 0,  # quantity of token 0 deployed in dex
            "qtty_token1": 0,  # quantity of token 1 deployed in dex
            "fees_owed_token0": 0,  # quantity of token 0 fees owed to the position ( not included in qtty_token0 and this is not uncollected fees)
            "fees_owed_token1": 0,  # quantity of token 1 fees owed to the position ( not included in qtty_token1 and this is not uncollected fees)
        }

        # get position data
        pos = self.position(
            ownerAddress=Web3.toChecksumAddress(ownerAddress.lower()),
            tickLower=tickLower,
            tickUpper=tickUpper,
        )
        # get slot data
        slot0 = self.globalState

        # get current tick from slot
        tickCurrent = slot0["tick"]
        sqrtRatioX96 = slot0["sqrtPriceX96"]
        sqrtRatioAX96 = dex_formulas.TickMath.getSqrtRatioAtTick(tickLower)
        sqrtRatioBX96 = dex_formulas.TickMath.getSqrtRatioAtTick(tickUpper)
        # calc quantity from liquidity
        (
            result["qtty_token0"],
            result["qtty_token1"],
        ) = dex_formulas.LiquidityAmounts.getAmountsForLiquidity(
            sqrtRatioX96, sqrtRatioAX96, sqrtRatioBX96, pos["liquidity"]
        )

        # add owed tokens
        result["fees_owed_token0"] = pos["tokensOwed0"]
        result["fees_owed_token1"] = pos["tokensOwed1"]

        # convert to decimal as needed
        if inDecimal:
            self._get_qtty_depoloyed_todecimal(result)
        # return result
        return result.copy()

    def _get_qtty_depoloyed_todecimal(self, result):
        # get token decimals
        decimals_token0 = self.token0.decimals
        decimals_token1 = self.token1.decimals

        result["qtty_token0"] = Decimal(result["qtty_token0"]) / Decimal(
            10**decimals_token0
        )
        result["qtty_token1"] = Decimal(result["qtty_token1"]) / Decimal(
            10**decimals_token1
        )
        result["fees_owed_token0"] = Decimal(result["fees_owed_token0"]) / Decimal(
            10**decimals_token0
        )
        result["fees_owed_token1"] = Decimal(result["fees_owed_token1"]) / Decimal(
            10**decimals_token1
        )

    def get_fees_uncollected(
        self, ownerAddress: str, tickUpper: int, tickLower: int, inDecimal: bool = True
    ) -> dict:
        """Retrieve the quantity of fees not collected nor yet owed ( but certain) to the deployed position

        Args:
            ownerAddress (str):
            tickUpper (int):
            tickLower (int):
            inDecimal (bool): return result in a decimal format?

        Returns:
            dict: {
                    "qtty_token0":0,   (int or Decimal)     # quantity of uncollected token 0
                    "qtty_token1":0,   (int or Decimal)     # quantity of uncollected token 1
                }
        """

        result = {
            "qtty_token0": 0,
            "qtty_token1": 0,
        }

        # get position data
        pos = self.position(
            ownerAddress=Web3.toChecksumAddress(ownerAddress.lower()),
            tickLower=tickLower,
            tickUpper=tickUpper,
        )

        # get ticks
        tickCurrent = self.globalState["tick"]
        ticks_lower = self.ticks(tickLower)
        ticks_upper = self.ticks(tickUpper)

        (
            result["qtty_token0"],
            result["qtty_token1"],
        ) = dex_formulas.get_uncollected_fees_vGammawire(
            fee_growth_global_0=self.feeGrowthGlobal0X128,
            fee_growth_global_1=self.feeGrowthGlobal1X128,
            tick_current=tickCurrent,
            tick_lower=tickLower,
            tick_upper=tickUpper,
            fee_growth_outside_0_lower=ticks_lower["feeGrowthOutside0X128"],
            fee_growth_outside_1_lower=ticks_lower["feeGrowthOutside1X128"],
            fee_growth_outside_0_upper=ticks_upper["feeGrowthOutside0X128"],
            fee_growth_outside_1_upper=ticks_upper["feeGrowthOutside1X128"],
            liquidity=pos["liquidity"],
            fee_growth_inside_last_0=pos["feeGrowthInside0LastX128"],
            fee_growth_inside_last_1=pos["feeGrowthInside1LastX128"],
        )

        # convert to decimal as needed
        if inDecimal:
            # get token decimals
            decimals_token0 = self.token0.decimals
            decimals_token1 = self.token1.decimals

            result["qtty_token0"] = Decimal(result["qtty_token0"]) / Decimal(
                10**decimals_token0
            )
            result["qtty_token1"] = Decimal(result["qtty_token1"]) / Decimal(
                10**decimals_token1
            )

        # return result
        return result.copy()

    def as_dict(self, convert_bint=False, static_mode: bool = False) -> dict:
        """as_dict _summary_

        Args:
            convert_bint (bool, optional): convert big integers to string. Defaults to False.
            static_mode (bool, optional): return  static fields only. Defaults to False.

        Returns:
            dict:
        """

        result = super().as_dict(convert_bint=convert_bint)

        result["activeIncentive"] = self.activeIncentive

        result["liquidityCooldown"] = (
            str(self.liquidityCooldown) if convert_bint else self.liquidityCooldown
        )

        result["maxLiquidityPerTick"] = (
            str(self.maxLiquidityPerTick) if convert_bint else self.maxLiquidityPerTick
        )

        # t spacing
        # result["tickSpacing"] = (
        #     self.tickSpacing if not convert_bint else str(self.tickSpacing)
        # )

        # add fee so that it has same field as univ3 pool to dict
        result["fee"] = self.globalState["fee"]

        # identify pool dex
        result["dex"] = self.identify_dex_name()

        result["token0"] = self.token0.as_dict(convert_bint=convert_bint)
        result["token1"] = self.token1.as_dict(convert_bint=convert_bint)

        if not static_mode:
            result["feeGrowthGlobal0X128"] = (
                str(self.feeGrowthGlobal0X128)
                if convert_bint
                else self.feeGrowthGlobal0X128
            )

            result["feeGrowthGlobal1X128"] = (
                str(self.feeGrowthGlobal1X128)
                if convert_bint
                else self.feeGrowthGlobal1X128
            )

            result["liquidity"] = (
                str(self.liquidity) if convert_bint else self.liquidity
            )

            result["globalState"] = self.globalState
            if convert_bint:
                try:
                    result["globalState"]["sqrtPriceX96"] = (
                        str(result["globalState"]["sqrtPriceX96"])
                        if "sqrtPriceX96" in result["globalState"]
                        else ""
                    )
                    # result["globalState"]["price"] = (
                    #     str(result["globalState"]["price"])
                    #     if "price" in result["globalState"]
                    #     else ""
                    # )
                    result["globalState"]["tick"] = (
                        str(result["globalState"]["tick"])
                        if "tick" in result["globalState"]
                        else ""
                    )
                    result["globalState"]["fee"] = (
                        str(result["globalState"]["fee"])
                        if "fee" in result["globalState"]
                        else ""
                    )
                    result["globalState"]["timepointIndex"] = (
                        str(result["globalState"]["timepointIndex"])
                        if "timepointIndex" in result["globalState"]
                        else ""
                    )
                except Exception:
                    logging.getLogger(__name__).warning(
                        f' Unexpected error converting globalState of {result["address"]} at block {result["block"]}     error-> {sys.exc_info()[0]}   globalState: {result["globalState"]}'
                    )

        return result


class algebrav3_pool_cached(algebrav3_pool):
    SAVE2FILE = True

    # PROPERTIES

    @property
    def activeIncentive(self) -> str:
        prop_name = "activeIncentive"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def dataStorageOperator(self) -> algebrav3_dataStorageOperator:
        """ """
        if self._dataStorage is None:
            self._dataStorage = algebrav3_dataStorageOperator_cached(
                address=self._contract.functions.dataStorageOperator().call(
                    block_identifier=self.block
                ),
                network=self._network,
                block=self.block,
            )
        return self._dataStorage

    @property
    def factory(self) -> str:
        prop_name = "factory"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def globalState(self) -> dict:
        prop_name = "globalState"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result.copy()

    @property
    def liquidity(self) -> int:
        prop_name = "liquidity"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def liquidityCooldown(self) -> int:
        prop_name = "liquidityCooldown"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def maxLiquidityPerTick(self) -> int:
        prop_name = "maxLiquidityPerTick"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def tickSpacing(self) -> int:
        prop_name = "tickSpacing"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def token0(self) -> erc20_cached:
        """The first of the two tokens of the pool, sorted by address

        Returns:
           erc20:
        """
        if self._token0 is None:
            self._token0 = erc20_cached(
                address=self._contract.functions.token0().call(
                    block_identifier=self.block
                ),
                network=self._network,
                block=self.block,
            )
        return self._token0

    @property
    def token1(self) -> erc20_cached:
        if self._token1 is None:
            self._token1 = erc20_cached(
                address=self._contract.functions.token1().call(
                    block_identifier=self.block
                ),
                network=self._network,
                block=self.block,
            )
        return self._token1

    @property
    def feeGrowthGlobal0X128(self) -> int:
        prop_name = "feeGrowthGlobal0X128"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result

    @property
    def feeGrowthGlobal1X128(self) -> int:
        prop_name = "feeGrowthGlobal1X128"
        result = self._cache.get_data(
            chain_id=self._chain_id,
            address=self.address,
            block=self.block,
            key=prop_name,
        )
        if result is None:
            result = getattr(super(), prop_name)
            self._cache.add_data(
                chain_id=self._chain_id,
                address=self.address,
                block=self.block,
                key=prop_name,
                data=result,
                save2file=self.SAVE2FILE,
            )
        return result


# algebra pool for camelot
# TODO: work ongoing
class algebraCamelot_pool(algebrav3_pool):
    @property
    def comunityFeeLastTimestamp(self) -> int:
        return self.call_function_autoRpc("comunityFeeLastTimestamp")

    @property
    def comunityVault(self) -> str:
        # TODO: comunityVault object
        return self.call_function_autoRpc("comunityVault")

    @property
    def getComunityFeePending(self) -> tuple[int, int]:
        """The amounts of token0 and token1 that will be sent to the vault

        Returns:
            tuple[int,int]: token0,token1
        """
        return self.call_function_autoRpc("getComunityFeePending")

    def getTimepoints(self, secondsAgo: int):
        raise NotImplementedError(" No get Timepoints in camelot")

    @property
    def getReserves(self) -> tuple[int, int]:
        """The amounts of token0 and token1 currently held in reserves

        Returns:
            tuple[int,int]: token0,token1
        """
        return self.call_function_autoRpc("getReserves")

    @property
    def globalState(self) -> dict:
        """

        Returns:
           dict:    uint160 price; // The square root of the current price in Q64.96 format
                    int24 tick; // The current tick
                    uint16 feeZtO; // The current fee for ZtO swap in hundredths of a bip, i.e. 1e-6
                    uint16 feeOtZ; // The current fee for OtZ swap in hundredths of a bip, i.e. 1e-6
                    uint16 timepointIndex; // The index of the last written timepoint
                    uint8 communityFee; // The community fee represented as a percent of all collected fee in thousandths (1e-3)
                    bool unlocked; // True if the contract is unlocked, otherwise - false
        """
        tmp = self.call_function_autoRpc("globalState")
        return {
            "sqrtPriceX96": tmp[0],
            "tick": tmp[1],
            "fee": tmp[2],
            "timepointIndex": tmp[4],
            "communityFeeToken0": tmp[5],
            "communityFeeToken1": tmp[5],
            "unlocked": tmp[6],
            # special
            "feeZtO": tmp[2],
            "feeOtZ": tmp[3],
        }
