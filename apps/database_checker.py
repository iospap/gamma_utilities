import os
import random
import sys
import logging
import tqdm
import concurrent.futures
import contextlib
import re

import polars as pl

from datetime import datetime
from pathlib import Path
from web3.exceptions import ContractLogicError


from bins.configuration import CONFIGURATION
from bins.database.db_user_status import user_status_hypervisor_builder
from bins.general.general_utilities import (
    convert_string_datetime,
    differences,
    log_time_passed,
)
from bins.w3.onchain_data_helper import onchain_data_helper2
from bins.w3.onchain_utilities.protocols import (
    gamma_hypervisor,
    gamma_hypervisor_quickswap,
    gamma_hypervisor_cached,
    gamma_hypervisor_quickswap_cached,
    gamma_hypervisor_registry,
)
from bins.w3.onchain_utilities.basic import erc20_cached

from bins.database.common.db_collections_common import database_local, database_global
from bins.mixed.price_utilities import price_scraper

from bins.w3.builders import build_db_hypervisor


# repair apps
def repair_all():
    """Repair all errors found in logs"""

    # repair blocks
    repair_blocks()

    # repair hypervisors status
    repair_hypervisor_status()

    # repair prices not found in logs
    repair_prices()


def repair_prices(min_count: int = 1):
    repair_prices_from_logs(min_count=min_count)

    repair_prices_from_status(
        max_repair_per_network=50
        or CONFIGURATION["_custom_"]["cml_parameters"].max_repair
    )


def repair_prices_from_logs(min_count: int = 1):
    """Check price errors from debug and price logs and try to scrape again"""
    try:
        network_token_blocks = {}
        for log_file in get_all_logfiles():
            network_token_blocks.update(get_failed_prices_from_log(log_file=log_file))

        with tqdm.tqdm(total=len(network_token_blocks)) as progress_bar:
            for network, addresses in network_token_blocks.items():
                logging.getLogger(__name__).info(
                    f" > Trying to repair {len(addresses)} tokens price from {network}"
                )
                for address, blocks_data in addresses.items():
                    for block, counter in blocks_data.items():
                        # block is string
                        block = int(block)

                        # check if price isnot already in database
                        if (
                            get_price_of_token(
                                network=network, token_address=address, block=block
                            )
                            != 0
                        ):
                            logging.getLogger(__name__).debug(
                                f" Price for {network}'s {address} at block {block} is already in database..."
                            )
                            continue

                        progress_bar.set_description(
                            f" Check & solve {network}'s price error log entries for {address[-4:]} at block {block}"
                        )
                        progress_bar.update(0)

                        # counter = number of times found in logs
                        if counter >= min_count:
                            if price := get_price(
                                network=network, token_address=address, block=block
                            ):
                                logging.getLogger(__name__).debug(
                                    f" Added {price} as price for {network}'s {address} at block {block}  (found {counter} times in log)"
                                )
                                add_price_to_token(
                                    network=network,
                                    token_address=address,
                                    block=block,
                                    price=price,
                                )
                            else:
                                logging.getLogger(__name__).debug(
                                    f" Could not find price for {network}'s {address} at block {block}  (found {counter} times in log)"
                                )
                        else:
                            logging.getLogger(__name__).debug(
                                f" Not procesing price for {network}'s {address} at block {block} bc it has been found only {counter} times in log."
                            )

                # update progress
                progress_bar.update(1)

    except Exception:
        logging.getLogger(__name__).exception(
            " unexpected error checking prices from log"
        )


def repair_prices_from_status(
    batch_size: int = 100000, max_repair_per_network: int | None = None
):
    """Check prices not present in database but present in hypervisors and rewards status and try to scrape again"""
    mongo_url = CONFIGURATION["sources"]["database"]["mongo_server_url"]

    for protocol in CONFIGURATION["script"]["protocols"]:
        # override networks if specified in cml
        networks = (
            CONFIGURATION["_custom_"]["cml_parameters"].networks
            or CONFIGURATION["script"]["protocols"][protocol]["networks"]
        )

        with tqdm.tqdm(total=len(networks)) as progress_bar:
            for network in networks:
                # database name
                db_name = f"{network}_{protocol}"

                # database helper
                def _db():
                    return database_local(mongo_url=mongo_url, db_name=db_name)

                # prices to get = all token0 and token1 addresses from hypervisor status + rewarder status blocks
                # price id = network_block_address
                price_ids_shouldBe = set()
                blocks_shouldBe = set()
                # progress
                progress_bar.set_description(
                    f" {network} should be prices: {len(price_ids_shouldBe)}"
                )
                progress_bar.update(0)

                # get all token addressess + block from status hypervisors
                logging.getLogger(__name__).info(
                    f" Getting hypervisor status token addresses and blocks for {network}"
                )
                for hype_status in _db().get_items_from_database(
                    collection_name="status", find={}, batch_size=batch_size
                ):
                    # add token addresses
                    price_ids_shouldBe.add(
                        f"{network}_{hype_status['block']}_{hype_status['pool']['token0']['address']}"
                    )
                    price_ids_shouldBe.add(
                        f"{network}_{hype_status['block']}_{hype_status['pool']['token1']['address']}"
                    )
                    # add block
                    blocks_shouldBe.add(hype_status["block"])

                    # progress
                    progress_bar.set_description(
                        f" {network} should be prices: {len(price_ids_shouldBe)}"
                    )
                    progress_bar.update(0)

                logging.getLogger(__name__).info(
                    f" Getting rewarder status token addresses and blocks for {network}"
                )
                for rewarder_status in _db().get_items_from_database(
                    collection_name="rewards_status",
                    find={"blocks": {"$nin": list(blocks_shouldBe)}},
                    batch_size=batch_size,
                ):
                    # add token addresses
                    price_ids_shouldBe.add(
                        f"{network}_{rewarder_status['block']}_{rewarder_status['rewardToken']}"
                    )

                    # add block
                    blocks_shouldBe.add(rewarder_status["block"])

                    # progress
                    progress_bar.set_description(
                        f" {network} should be prices: {len(price_ids_shouldBe)}"
                    )
                    progress_bar.update(0)

                logging.getLogger(__name__).info(
                    f" Checking if there are {len(price_ids_shouldBe)} prices for {network} in the price database"
                )

                if price_ids_diffs := price_ids_shouldBe - set(
                    [
                        id["id"]
                        for id in database_global(
                            mongo_url=mongo_url
                        ).get_items_from_database(
                            collection_name="usd_prices",
                            find={"network": network},
                            batch_size=batch_size,
                        )
                    ]
                ):
                    logging.getLogger(__name__).info(
                        f" Found {len(price_ids_diffs)} missing prices for {network}"
                    )
                    # do not repair more than max_repair_per_network prices at once to avoid being too much time in the same network
                    if (
                        max_repair_per_network
                        and len(price_ids_diffs) > max_repair_per_network
                    ):
                        logging.getLogger(__name__).info(
                            f" Selecting a random sample of {max_repair_per_network} prices due to maximum repair limit set. Next loop will repair the next ones."
                        )
                        # choose to repair the first max_repair_per_network
                        price_ids_diffs = random.sample(
                            price_ids_diffs, max_repair_per_network
                        )

                    progress_bar.total += len(price_ids_diffs)
                    # get prices
                    for price_id in price_ids_diffs:
                        network, block, address = price_id.split("_")
                        logging.getLogger(__name__).debug(
                            f" Getting price for {network}'s {address} at block {block}"
                        )
                        if price := get_price(
                            network=network, token_address=address, block=block
                        ):
                            logging.getLogger(__name__).debug(
                                f" Added {price} as price for {network}'s {address} at block {block}"
                            )
                            add_price_to_token(
                                network=network,
                                token_address=address,
                                block=block,
                                price=price,
                            )
                        else:
                            logging.getLogger(__name__).debug(
                                f" Could not find price for {network}'s {address} at block {block}"
                            )

                        # progress
                        progress_bar.set_description(f" {network} {address} {block}")
                        progress_bar.update(1)

                else:
                    logging.getLogger(__name__).info(
                        f" No missing prices found for {network}"
                    )

                # progress
                progress_bar.update(1)


def repair_hypervisor_status():
    # from user_status debug log
    repair_hype_status_from_user()

    # missing hypes
    repair_missing_hype_status()


def repair_missing_hypervisor_status(
    protocol: str, network: str, cache: bool = True, max_repair: int = None
):
    """Creates hypervisor status at all operations block and block-1 not already present in database,
        using the difference between operations and status blocks

    Args:
        protocol (str):
        network (str):
        rewrite (bool): rewrite all status
        threaded: (bool):
    """

    logging.getLogger(__name__).info(
        f">Feeding {protocol}'s {network} hypervisors status information using the difference between operations and status blocks"
    )
    # get all operation blocks from database
    mongo_url = CONFIGURATION["sources"]["database"]["mongo_server_url"]
    db_name = f"{network}_{protocol}"

    # loop thru all hypervisors in database
    for hype in database_local(
        mongo_url=mongo_url, db_name=db_name
    ).get_items_from_database(collection_name="static", find={}):
        # get all status blocks
        hype_status_blocks = database_local(
            mongo_url=mongo_url, db_name=db_name
        ).get_distinct_items_from_database(
            collection_name="status",
            field="block",
            condition={"address": hype["address"]},
        )

        # get all operations blocks with the topics=["deposit", "withdraw", "zeroBurn", "rebalance"]
        operation_blocks = []
        for block in database_local(
            mongo_url=mongo_url, db_name=db_name
        ).get_distinct_items_from_database(
            collection_name="operations",
            field="blockNumber",
            condition={
                "address": hype["address"],
                "topics": {"$in": ["deposit", "withdraw", "zeroBurn", "rebalance"]},
            },
        ):
            operation_blocks.append(int(block))
            operation_blocks.append(int(block - 1))

        # get differences
        if difference_blocks := differences(operation_blocks, hype_status_blocks):
            logging.getLogger(__name__).info(
                f" Found {len(difference_blocks)} missing status blocks for {network}'s {hype['address']}"
            )
            if max_repair and len(difference_blocks) > max_repair:
                logging.getLogger(__name__).info(
                    f"  Selecting a random sample of {max_repair} hypervisor status missing due to max_repair limit set."
                )
                difference_blocks = random.sample(difference_blocks, max_repair)

            logging.getLogger(__name__).info(
                f"  Feeding hypervisor status collection with {len(difference_blocks)} blocks for {network}'s {hype['address']}"
            )

            # prepare arguments for paralel scraping
            args = (
                (hype["address"], network, block, hype["dex"], False, None, None, cache)
                for block in difference_blocks
            )
            # scrape missing status
            _errors = 0
            with tqdm.tqdm(total=len(difference_blocks)) as progress_bar:
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    for result in ex.map(lambda p: build_db_hypervisor(*p), args):
                        if result is None:
                            # error found
                            _errors += 1

                        else:
                            # add hypervisor status to database
                            database_local(
                                mongo_url=mongo_url, db_name=db_name
                            ).set_status(data=result)
                            # progress
                            progress_bar.set_description(
                                f' {result.get("address", "")}  {result.get("block", " ")} processed'
                            )
                        # update progress
                        progress_bar.update(1)


def repair_hype_status_from_user(min_count: int = 1):
    protocol = "gamma"

    network_token_blocks = {}
    for log_file in get_all_logfiles():
        network_token_blocks.update(get_failed_status_from_log(log_file=log_file))

    # for log_file in get_all_logfiles():
    # hypervisor status not found while scrpaing user data
    # network_token_blocks = get_failed_status_from_log(log_file)

    try:
        with tqdm.tqdm(total=len(network_token_blocks)) as progress_bar:
            for network, addresses in network_token_blocks.items():
                # set local database name and create manager
                db_name = f"{network}_{protocol}"
                local_db = database_local(
                    mongo_url=CONFIGURATION["sources"]["database"]["mongo_server_url"],
                    db_name=db_name,
                )
                logging.getLogger(__name__).info(
                    f" > Trying to repair {len(addresses)} hypervisors status from {network}"
                )

                for address, blocks_data in addresses.items():
                    for block, counter in blocks_data.items():
                        # block is string
                        block = int(block)

                        # make sure hypervisor status is not in db
                        if local_db.get_items(
                            collection_name="status",
                            find={"address": address.lower(), "block": block},
                            projection={"dex": 1},
                        ):
                            logging.getLogger(__name__).debug(
                                f" Status for {network}'s {address} at block {block} is already in database..."
                            )
                            continue

                        progress_bar.set_description(
                            f" Repair {network}'s hype status not found log entries for {address} at block {block}"
                        )
                        progress_bar.update(0)

                        # counter = number of times found in logs
                        if counter >= min_count:
                            # need dex to be able to build hype

                            if dex := local_db.get_items(
                                collection_name="static",
                                find={"address": address.lower()},
                                projection={"dex": 1},
                            ):
                                dex = dex[0]["dex"]
                            else:
                                logging.getLogger(__name__).error(
                                    f"{protocol}'s {network} hyperivisor {address} not fount in static db collection. May not be present in registry. (cant solve err.)"
                                )
                                # loop to next address
                                continue

                            # scrape hypervisor status at block
                            hype_status = build_db_hypervisor(
                                address=address,
                                network=network,
                                block=block,
                                dex=dex,
                                cached=False,
                            )
                            if hype_status:
                                # add hypervisor status to database
                                local_db.set_status(data=hype_status)

                                logging.getLogger(__name__).info(
                                    f" Added status for {network}'s {address} at block {block}  (found {counter} times in log)"
                                )
                            else:
                                logging.getLogger(__name__).debug(
                                    f" Could not find status for {network}'s {address} at block {block}  (found {counter} times in log)"
                                )
                        else:
                            logging.getLogger(__name__).debug(
                                f" Not procesing status for {network}'s {address} at block {block} bc it has been found only {counter} times in log."
                            )

                # update progress
                progress_bar.update(1)
    except Exception as e:
        logging.getLogger(__name__).error(
            f" Error repairing hypervisor status not found {e}"
        )


def repair_missing_hype_status():
    for protocol in CONFIGURATION["script"]["protocols"]:
        # override networks if specified in cml
        networks = (
            CONFIGURATION["_custom_"]["cml_parameters"].networks
            or CONFIGURATION["script"]["protocols"][protocol]["networks"]
        )

        for network in networks:
            repair_missing_hypervisor_status(
                protocol=protocol,
                network=network,
                max_repair=CONFIGURATION["_custom_"]["cml_parameters"].max_repair,
            )


def repair_blocks():
    for protocol in CONFIGURATION["script"]["protocols"]:
        # override networks if specified in cml
        networks = (
            CONFIGURATION["_custom_"]["cml_parameters"].networks
            or CONFIGURATION["script"]["protocols"][protocol]["networks"]
        )
        for network in networks:
            repair_missing_blocks(protocol=protocol, network=network)


def repair_missing_blocks(protocol: str, network: str, batch_size: int = 100000):
    # get a list of blocks from global database
    database_blocks = [
        x["block"]
        for x in database_global(
            mongo_url=CONFIGURATION["sources"]["database"]["mongo_server_url"]
        ).get_items_from_database(
            collection_name="blocks",
            find={"network": network},
            projection={"block": 1},
            batch_size=batch_size,
        )
    ]

    # get a list of status blocks from local database
    todo_blocks = {
        x["block"]: {
            "id": f"{network}_{x['block']}",
            "network": network,
            "block": x["block"],
            "timestamp": x["timestamp"],
        }
        for x in database_local(
            mongo_url=CONFIGURATION["sources"]["database"]["mongo_server_url"],
            db_name=f"{network}_{protocol}",
        ).get_items_from_database(
            collection_name="status",
            find={"block": {"$nin": database_blocks}},
            projection={"block": 1, "timestamp": 1},
            batch_size=batch_size,
        )
    }

    # get a list of status rewards from local database
    todo_blocks.update(
        {
            x["block"]: {
                "id": f"{network}_{x['block']}",
                "network": network,
                "block": x["block"],
                "timestamp": x["timestamp"],
            }
            for x in database_local(
                mongo_url=CONFIGURATION["sources"]["database"]["mongo_server_url"],
                db_name=f"{network}_{protocol}",
            ).get_items_from_database(
                collection_name="rewards_status",
                find={"block": {"$nin": database_blocks}},
                projection={"block": 1, "timestamp": 1},
                batch_size=batch_size,
            )
        }
    )

    if todo_blocks:
        logging.getLogger(__name__).info(
            f" Found {len(todo_blocks)} missing blocks in {network}. Adding to global database..."
        )
        # add missing blocks to global database
        database_global(
            mongo_url=CONFIGURATION["sources"]["database"]["mongo_server_url"]
        ).replace_items_to_database(data=todo_blocks.values(), collection_name="blocks")
    else:
        logging.getLogger(__name__).info(f" No missing blocks found in {network}.")

    # _errors = 0
    # with tqdm.tqdm(total=len(todo_blocks)) as progress_bar:
    #     for block, timestamp in todo_blocks.items():
    #         try:
    #             database_global(
    #                 mongo_url=CONFIGURATION["sources"]["database"]["mongo_server_url"]
    #             ).set_block(network=network, block=block, timestamp=timestamp)
    #         except Exception as e:
    #             logging.getLogger(__name__).error(
    #                 f" Error adding block {block} to global database {e}"
    #             )
    #             _errors += 1

    #         progress_bar.set_description(
    #             f" Check & solve {network}'s block num. {block}"
    #         )
    #         progress_bar.update(1)


# one time utils
def replace_blocks_to_int():
    logging.getLogger(__name__).debug("    Converting non int blocks to int")

    # setup database managers
    mongo_url = CONFIGURATION["sources"]["database"]["mongo_server_url"]
    # db_name = f"{network}_{protocol}"
    # local_db_manager = database_local(mongo_url=mongo_url, db_name=db_name)
    global_db_manager = database_global(mongo_url=mongo_url)

    # get all prices
    all_prices = global_db_manager.get_items_from_database(
        collection_name="usd_prices", find={"block": {"$not": {"$type": "int"}}}
    )
    _errors = 0
    with tqdm.tqdm(total=len(all_prices)) as progress_bar:

        def loopme(price):
            global_db_manager.set_price_usd(
                network=price["network"],
                block=price["block"],
                token_address=price["address"],
                price_usd=price["price"],
            )
            return price

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            for price in ex.map(loopme, all_prices):
                progress_bar.set_description(
                    f"Updating database {price['network']}'s block {price['block']}"
                )
                # update progress
                progress_bar.update(1)


def replace_quickswap_pool_dex_to_algebra(network: str, protocol: str = "gamma"):
    logging.getLogger(__name__).debug("    Convert quickswap pool dex to algebra")

    # setup database managers
    mongo_url = CONFIGURATION["sources"]["database"]["mongo_server_url"]
    db_name = f"{network}_{protocol}"
    local_db_manager = database_local(mongo_url=mongo_url, db_name=db_name)

    # get all status to be modded
    status_to_modify = local_db_manager.get_items_from_database(
        collection_name="status", find={"pool.dex": "quickswap"}
    )
    _errors = 0
    with tqdm.tqdm(total=len(status_to_modify)) as progress_bar:

        def loopme(status):
            status["pool"]["dex"] = "algebrav3"
            local_db_manager.set_status(data=status)
            return status

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            for status in ex.map(loopme, status_to_modify):
                progress_bar.set_description(
                    f" Convert {network}'s status quickswap pool dex to algebra  id: {status['id']}"
                )
                # update progress
                progress_bar.update(1)


def add_timestamps_to_status(network: str, protocol: str = "gamma"):
    # setup database managers
    mongo_url = CONFIGURATION["sources"]["database"]["mongo_server_url"]
    db_name = f"{network}_{protocol}"
    local_db_manager = database_local(mongo_url=mongo_url, db_name=db_name)
    global_db_manager = database_global(mongo_url=mongo_url)

    # get a list of timestamps from database
    all_blocks = {
        x["block"]: x["timestamp"]
        for x in global_db_manager.get_items_from_database(collection_name="blocks")
    }

    all_status = local_db_manager.get_items_from_database(collection_name="status")

    _errors = 0
    with tqdm.tqdm(total=len(all_status)) as progress_bar:

        def loopme(status):
            if "timestamp" in status:
                # item already with data
                return status, True

            # control var
            saveit = False
            with contextlib.suppress(Exception):
                # get timestamp from database
                status["timestamp"] = all_blocks[status["block"]]
                status["pool"]["timestamp"] = status["timestamp"]
                status["pool"]["token0"]["timestamp"] = status["timestamp"]
                status["pool"]["token1"]["timestamp"] = status["timestamp"]

                saveit = True
            if not saveit:
                with contextlib.suppress(Exception):
                    # get timestamp from web3 call
                    status["timestamp"] = (
                        erc20_cached(
                            address="0x0000000000000000000000000000000000000000",
                            network=network,
                        )
                        ._w3.eth.get_block(status["block"])
                        .timestamp
                    )
                    status["pool"]["timestamp"] = status["timestamp"]
                    status["pool"]["token0"]["timestamp"] = status["timestamp"]
                    status["pool"]["token1"]["timestamp"] = status["timestamp"]

                    saveit = True
            if saveit:
                # save modified status to database
                local_db_manager.set_status(data=status)
                return status, True
            else:
                logging.getLogger(__name__).warning(
                    f" Can't get timestamp for hypervisor {status['address']}   id: {status['id']}"
                )
                return status, False

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            for status, result in ex.map(loopme, all_status):
                if not result:
                    _errors += 1

                progress_bar.set_description(
                    f"[{_errors}]  Updating status database {network}'s {status['address']} block {status['block']}"
                )

                # update progress
                progress_bar.update(1)


# helpers
def add_price_to_token(network: str, token_address: str, block: int, price: float):
    """force special price add to database:
     will create a field called "origin" with "manual" as value to be ableto identify at db

    Args:
        network (str):
        token_address (str):
        block (int):
        price (float):
    """

    # setup database managers
    mongo_url = CONFIGURATION["sources"]["database"]["mongo_server_url"]
    global_db_manager = database_global(mongo_url=mongo_url)

    data = {
        "id": f"{network}_{block}_{token_address}",
        "network": network,
        "block": int(block),
        "address": token_address,
        "price": float(price),
        "origin": "manual",
    }

    global_db_manager.save_item_to_database(data=data, collection_name="usd_prices")


def get_price_of_token(network: str, token_address: str, block: int) -> float:
    """get price of token at block

    Args:
        network (str):
        token_address (str):
        block (int):

    Returns:
        float:
    """

    # setup database managers
    mongo_url = CONFIGURATION["sources"]["database"]["mongo_server_url"]
    global_db_manager = database_global(mongo_url=mongo_url)

    # get price from database
    price = global_db_manager.get_price_usd(
        network=network, block=block, address=token_address
    )

    if price:
        return price[0]["price"]
    else:
        return 0.0


def get_price(network: str, token_address: str, block: int) -> float:
    price_helper = price_scraper(cache=False)

    return price_helper.get_price(network=network, token_id=token_address, block=block)


def auto_get_prices():
    # set prices to get
    address_block_list = {
        # "ethereum": {
        #     "0xf4dc48d260c93ad6a96c5ce563e70ca578987c74": [14982409],
        #     "0x0642026e7f0b6ccac5925b4e7fa61384250e1701": [15171687],
        #     "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": [16701232],
        #     "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": [13047429],
        #     "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": [14953317, 12825206],
        #     "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": [12957386],
        #     "0x77fba179c79de5b7653f68b5039af940ada60ce0": [12996888],
        #     "0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0": [12948766],
        # },
        # "polygon": {
        #     "0xc2132d05d31c914a87c6611c10748aeb04b58e8f": [
        #         39745459,
        #         39745460,
        #         39745491,
        #         39745492,
        #         39745534,
        #         39745535,
        #         39745541,
        #         39745542,
        #         39746053,
        #         39746054,
        #         39746062,
        #         39746063,
        #         39068569,
        #         39423640,
        #         39613083,
        #         39616413,
        #     ]
        # }
    }

    address_block_list["ethereum"] = {
        "0xb41f289d699c5e79a51cb29595c203cfae85f32a": [
            13856873,
            13856900,
            13864770,
            13856874,
            13856901,
            13864769,
        ]
    }

    # loop query n save
    for network, data in address_block_list.items():
        for address, blocks in data.items():
            for block in blocks:
                price = get_price(network=network, token_address=address, block=block)
                if price != 0:
                    logging.getLogger(__name__).debug(
                        f" Added price for {network}'s {address} at block {block}"
                    )
                    add_price_to_token(
                        network=network, token_address=address, block=block, price=price
                    )
                else:
                    logging.getLogger(__name__).debug(
                        f" Could not add price for {network}'s {address} at block {block}"
                    )


def get_all_logfiles() -> list:
    """get all logfiles from config or default"""

    logfiles = []

    for logPath in (
        CONFIGURATION["_custom_"]["cml_parameters"].check_logs
        or CONFIGURATION["logs"]["save_path"]
    ):
        if os.path.isfile(logPath):
            logfiles.append(logPath)
        elif os.path.isdir(logPath):
            for root, dirs, files in os.walk(logPath):
                # avoid to load "check" related logs ( current app log)
                if (
                    CONFIGURATION["_custom_"]["cml_parameters"].log_subfolder
                    or "check" not in root.lower()
                ):
                    for file in files:
                        if file.endswith(".log") and (
                            "debug" in file.lower() or "price" in file.lower()
                        ):
                            logfiles.append(os.path.join(root, file))

        # # get loaded price log
        # logfiles.append(logging.getLogger("price").handlers[0].baseFilename)
        # # get loaded debug log
        # logfiles.append(
        #     [
        #         x.baseFilename
        #         for x in logging.getLoggerClass().root.handlers
        #         if "debug" in x.name
        #     ][0]
        # )

    return logfiles


def load_logFile(logfile: str) -> str:
    """load logfile and return list of lines"""

    # load file
    result = ""
    if os.path.isfile(logfile):
        with open(logfile, mode="r", encoding="utf8") as f:
            result = f.read()
    else:
        logging.getLogger(__name__).error(f"Error: File not found {logfile}")

    return result


# checks
def check_database():
    # setup global database manager
    mongo_url = CONFIGURATION["sources"]["database"]["mongo_server_url"]
    global_db_manager = database_global(mongo_url=mongo_url)

    with tqdm.tqdm(total=len(CONFIGURATION["script"]["protocols"])) as progress_bar:
        # checks
        for protocol, networks in CONFIGURATION["script"]["protocols"].items():
            for network, dexes in networks["networks"].items():
                # setup local database manager
                db_name = f"{network}_{protocol}"
                local_db_manager = database_local(mongo_url=mongo_url, db_name=db_name)

                # progress
                progress_bar.set_description(
                    f" Checking {network}'s blocks from operations and status"
                )
                progress_bar.update(0)
                # check blocks
                chek_localdb_blocks(local_db_manager=local_db_manager)

                # progress
                progress_bar.set_description(
                    f" Checking {network}'s token stables usd prices"
                )
                progress_bar.update(0)
                # check stable prices
                check_stable_prices(
                    network=network,
                    local_db_manager=local_db_manager,
                    global_db_manager=global_db_manager,
                )

                # update progress
                progress_bar.update(1)

        # check GLOBAL
        # progress
        progress_bar.set_description(" Checking global blocks collection")
        progress_bar.update(0)
        # check blocks
        chek_globaldb_blocks(global_db_manager=global_db_manager)


def chek_localdb_blocks(local_db_manager: database_local):
    """check if blocks are typed correctly

    Args:
        local_db_manager (database_local):
    """

    if blocks_operatons := local_db_manager.get_items_from_database(
        collection_name="operations",
        find={"blockNumber": {"$not": {"$type": "int"}}},
    ):
        logging.getLogger(__name__).warning(
            f" Found {len(blocks_operatons)} operations with the block field not being int"
        )

    if blocks_status := local_db_manager.get_items_from_database(
        collection_name="status", find={"block": {"$not": {"$type": "int"}}}
    ):
        logging.getLogger(__name__).warning(
            f" Found {len(blocks_status)} hypervisor status with the block field not being int"
        )


def chek_globaldb_blocks(global_db_manager: database_global):
    """check that blocks have the correct type

    Args:
        global_db_manager (database_global):
    """

    if blocks_usd_prices := global_db_manager.get_items_from_database(
        collection_name="usd_prices", find={"block": {"$not": {"$type": "int"}}}
    ):
        logging.getLogger(__name__).warning(
            f" Found {len(blocks_usd_prices)} usd prices with the block field not being int: database '{global_db_manager._db_name}' collection 'usd_prices'   ids-> {[x['_id'] for x in blocks_usd_prices]}"
        )
        # try replacing those found non int block prices to int
        replace_blocks_to_int()


def check_status_prices(
    network: str, local_db_manager: database_local, global_db_manager: database_global
):
    """Check that all status tokens have usd prices

    Args:
        local_db_manager (database_local):
        global_db_manager (database_global):
    """
    # get all prices + address + block
    prices = {
        x["id"]
        for x in global_db_manager.get_unique_prices_addressBlock(network=network)
    }

    # get tokens and blocks present in database
    prices_todo = set()
    for x in local_db_manager.get_items_from_database(collection_name="status"):
        for i in [0, 1]:
            db_id = f'{network}_{x["pool"][f"token{i}"]["block"]}_{x["pool"][f"token{i}"]["address"]}'

            if db_id not in prices:
                prices_todo.add(db_id)

    if prices_todo:
        logging.getLogger(__name__).warning(
            " Found {} token blocks without price, from a total of {} ({:,.1%})".format(
                len(prices_todo), len(prices), len(prices_todo) / len(prices)
            )
        )


def check_stable_prices(
    network: str, local_db_manager: database_local, global_db_manager: database_global
):
    """Search database for predefined stable tokens usd price devisations from 1
        and log it

    Args:
        network (str): _description_
        local_db_manager (database_local):
        global_db_manager (database_global):
    """
    logging.getLogger(__name__).debug(
        f" Seek deviations of {network}'s stable token usd prices from 1 usd"
    )

    stables_symbol_list = ["USDC", "USDT", "LUSD", "DAI"]
    stables = {
        x["pool"]["token0"]["symbol"]: x["pool"]["token0"]["address"]
        for x in local_db_manager.get_items_from_database(
            collection_name="static",
            find={"pool.token0.symbol": {"$in": stables_symbol_list}},
        )
    } | {
        x["pool"]["token1"]["symbol"]: x["pool"]["token1"]["address"]
        for x in local_db_manager.get_items_from_database(
            collection_name="static",
            find={"pool.token1.symbol": {"$in": stables_symbol_list}},
        )
    }

    # database ids var
    db_ids = []

    for x in global_db_manager.get_items_from_database(
        collection_name="usd_prices",
        find={"address": {"$in": list(stables.values())}, "network": network},
    ):
        # check if deviation from 1 is significative
        if abs(x["price"] - 1) > 0.3:
            logging.getLogger(__name__).warning(
                f" Stable {x['network']}'s {x['address']} usd price is {x['price']} at block {x['block']}"
            )
            # add id
            db_ids.append(x["_id"])

    if db_ids:
        logging.getLogger(__name__).warning(
            f" Error found in database '{global_db_manager._db_name}' collection 'usd_prices'  ids: {db_ids}"
        )


def get_failed_prices_from_log(log_file: str) -> dict:
    """Search repeated network + address + block in logs

    Return: {  <network>: {<address>: {<block>:<counter>}}}

    """
    pricelog_regx = "\-\s\s(?P<network>.*)'s\stoken\s(?P<address>.*)\sprice\sat\sblock\s(?P<block>\d*)\snot\sfound"
    debug_regx = "No\sprice\sfor\s(?P<address>.*)\sat\sblock\s(?P<block>\d*).*\[(?P<network>.*)\s(?P<dex>.*)\]"
    debug_regx2 = "No\sprice\sfor\s(?P<network>.*)'s\s(?P<symbol>.*)\s\((?P<address>.*)\).*at\sblock\s(?P<block>\d*)"
    user_status_regx = "Can't\sfind\s(?P<network>.*?)'s\s(?P<hype_address>.*?)\susd\sprice\sfor\s(?P<address>.*?)\sat\sblock\s(?P<block>\d*?)\.\sReturn\sZero"
    # groups->  network, symbol, address, block

    # load file
    log_file_content = load_logFile(logfile=log_file)

    # set a var
    network_token_blocks = {}

    for regx_txt in [debug_regx, pricelog_regx, debug_regx2, user_status_regx]:
        if matches := re.finditer(regx_txt, log_file_content):
            for match in matches:
                network = match.group("network")
                address = match.group("address")
                block = match.group("block")

                # network
                if network not in network_token_blocks:
                    network_token_blocks[network] = {}
                # address
                if address not in network_token_blocks[network]:
                    network_token_blocks[network][address] = {}
                # block
                if block not in network_token_blocks[network][address]:
                    network_token_blocks[network][address][block] = 0

                # counter ( times encountered)
                network_token_blocks[network][address][block] += 1

    return network_token_blocks


def get_failed_status_from_log(log_file: str) -> dict:
    # load file
    log_file_content = load_logFile(logfile=log_file)

    regx_txt = "No\shypervisor\sstatus\sfound\sfor\s(?P<network>.*)'s\s(?P<address>.*)\sat\sblock\s(?P<block>\d*)"
    # set a var
    network_token_blocks = {}

    # find hypervisor status not found
    if matches := re.finditer(regx_txt, log_file_content):
        for match in matches:
            network = match.group("network")
            address = match.group("address")
            block = match.group("block")

            # network
            if network not in network_token_blocks:
                network_token_blocks[network] = {}
            # address
            if address not in network_token_blocks[network]:
                network_token_blocks[network][address] = {}
            # block
            if block not in network_token_blocks[network][address]:
                network_token_blocks[network][address][block] = 0

            # counter ( times encountered)
            network_token_blocks[network][address][block] += 1

    return network_token_blocks


def main(option: str, **kwargs):
    if option == "prices":
        repair_prices()
    if option == "database":
        check_database()
    if option == "hypervisor_status":
        repair_hypervisor_status()
    if option == "repair":
        repair_all()
    if option == "special":
        # used to check for special cases
        pass
    # else:
    #     raise NotImplementedError(
    #         f" Can't find any action to be taken from {option} checks option"
    #     )
