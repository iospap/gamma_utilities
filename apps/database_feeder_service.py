#
#  periodic data action
#
import os
import sys
from pathlib import Path
import logging

# import signal
import multiprocessing as mp
from datetime import datetime, timedelta, timezone
import time

from bins.configuration import CONFIGURATION

from apps.database_feeder import (
    feed_operations,
    feed_prices,
    create_tokenBlocks_allTokens,
    create_tokenBlocks_allTokensButWeth,
    create_tokenBlocks_topTokens,
    feed_prices_force_sqrtPriceX96,
    feed_timestamp_blocks,
    feed_blocks_timestamp,
    create_tokenBlocks_rewards,
)
from apps.feeds.static import feed_hypervisor_static, feed_rewards_static
from apps.feeds.users import feed_user_status, feed_user_operations
from apps.feeds.status import (
    feed_rewards_status,
    feed_hypervisor_status,
)

from apps.database_checker import repair_all


def network_sequence_loop(
    protocol: str,
    network: str,
    do_prices: bool = False,
    do_userStatus: bool = False,
    do_repairs: bool = False,
):
    """local database feeding loop.
        it will also feed the 'blocks' global collection

    Args:
        protocol (str):
        network (str):
    """

    # feed database with all operations from static hypervisor addresses
    feed_operations(protocol=protocol, network=network)

    # feed database with status
    feed_hypervisor_status(protocol=protocol, network=network, threaded=True)

    # feed global blocks data with status
    feed_timestamp_blocks(network=network, protocol=protocol)

    # feed global blocks data with daily
    feed_blocks_timestamp(network=network)

    if do_prices:
        # feed network prices ( before user status to avoid price related errors)
        price_sequence_loop(protocol=protocol, network=network)

    if do_userStatus:
        # feed user_status data
        feed_user_operations(protocol=protocol, network=network)

    if do_repairs:
        # try to repair all errors found in logs
        repair_all()

    # feed rewards status ( needs prices and blocks)
    feed_rewards_status(protocol=protocol, network=network)


def price_sequence_loop(protocol: str, network: str):
    # feed most used token proces
    logging.getLogger(__name__).info(f">   top token prices")
    feed_prices(
        protocol=protocol,
        network=network,
        price_ids=create_tokenBlocks_topTokens(protocol=protocol, network=network),
        coingecko=True,
    )

    # force feed prices from already known using conversion
    logging.getLogger(__name__).info(f">   all token prices from already known/top")
    feed_prices_force_sqrtPriceX96(protocol=protocol, network=network)

    # feed all token prices left but weth
    logging.getLogger(__name__).info(f">   all token prices left but weth")
    feed_prices(
        protocol=protocol,
        network=network,
        price_ids=create_tokenBlocks_allTokensButWeth(
            protocol=protocol, network=network
        ),
        coingecko=False,
    )
    # feed all token prices left
    logging.getLogger(__name__).info(f">   all token prices left")
    feed_prices(
        protocol=protocol,
        network=network,
        price_ids=create_tokenBlocks_allTokens(protocol=protocol, network=network),
        coingecko=True,
    )

    # feed rewards token prices
    logging.getLogger(__name__).info(f">   rewards token prices")
    feed_prices(
        protocol=protocol,
        network=network,
        price_ids=create_tokenBlocks_rewards(protocol=protocol, network=network),
        coingecko=True,
    )


# services
def local_db_service():
    """feed all local database collections in an infinite loop"""
    # send eveyone service ON
    logging.getLogger("telegram").info(" Local database feeding loop started")
    try:
        while True:
            for protocol in CONFIGURATION["script"]["protocols"]:
                # override networks if specified in cml
                networks = (
                    CONFIGURATION["_custom_"]["cml_parameters"].networks
                    or CONFIGURATION["script"]["protocols"][protocol]["networks"]
                )
                for network in networks:
                    network_sequence_loop(
                        protocol=protocol,
                        network=network,
                        do_prices=CONFIGURATION["_custom_"]["cml_parameters"].do_prices
                        or False,
                        do_repairs=CONFIGURATION["_custom_"][
                            "cml_parameters"
                        ].do_repairs
                        or False,
                    )

    except KeyboardInterrupt:
        logging.getLogger(__name__).debug(" Local database feeding loop stoped by user")
    except Exception:
        logging.getLogger(__name__).exception(
            f" Unexpected error while loop-feeding local database data. error {sys.exc_info()[0]}"
        )
    # send eveyone not updating anymore
    logging.getLogger("telegram").info(" Local database feeding loop stoped")


def global_db_service():
    """feed global database collections in an infinite loop"""

    # send eveyone service ON
    logging.getLogger("telegram").info(" Global database feeding loop started")
    try:
        while True:
            for protocol in CONFIGURATION["script"]["protocols"]:
                # override networks if specified in cml
                networks = (
                    CONFIGURATION["_custom_"]["cml_parameters"].networks
                    or CONFIGURATION["script"]["protocols"][protocol]["networks"]
                )
                for network in networks:
                    price_sequence_loop(protocol=protocol, network=network)

    except KeyboardInterrupt:
        logging.getLogger(__name__).debug(
            " Global database feeding loop stoped by user"
        )
    except Exception as e:
        logging.getLogger(__name__).exception(
            f" Unexpected error while loop-feeding global database data. error {e}"
        )
    # send eveyone not updating anymore
    logging.getLogger("telegram").info(" Global database feeding loop stoped")


def network_db_service(
    protocol: str,
    network: str,
    do_prices: bool = False,
    do_userStatus: bool = False,
    do_repairs: bool = False,
):
    """feed one local database collection in an infinite loop"""

    logging.getLogger("telegram").info(
        f" {protocol}'s {network} database feeding loop started"
    )
    # get minimum time between loops ( defaults to 5 minutes)
    min_loop_time = 60 * (
        CONFIGURATION["_custom_"]["cml_parameters"].min_loop_time
        or CONFIGURATION["script"].get("min_loop_time", 5)
    )
    try:
        while True:
            _startime = datetime.now(timezone.utc)
            network_sequence_loop(
                protocol=protocol,
                network=network,
                do_prices=do_prices,
                do_userStatus=do_userStatus,
                do_repairs=do_repairs,
            )
            _endtime = datetime.now(timezone.utc)
            if (_endtime - _startime).total_seconds() < min_loop_time:
                sleep_time = min_loop_time - (_endtime - _startime).total_seconds()
                logging.getLogger(__name__).debug(
                    f" {protocol}'s {network} sleeping for {sleep_time} seconds to loop again"
                )
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logging.getLogger(__name__).debug(
            f" {protocol}'s {network} database feeding loop stoped by user"
        )
    except Exception:
        logging.getLogger(__name__).exception(
            f" Unexpected error while loop-feeding {protocol}'s {network} database data. error {sys.exc_info()[0]}"
        )

    # telegram messaging
    logging.getLogger("telegram").info(
        f" {protocol}'s {network} database feeding loop stoped"
    )


def main(option: str, **kwargs):
    if option == "local":
        local_db_service()
    elif option == "global":
        global_db_service()
    elif option == "network":
        network_db_service(
            protocol=kwargs["protocol"],
            network=kwargs["network"],
            do_prices=CONFIGURATION["_custom_"]["cml_parameters"].do_prices or False,
            do_userStatus=CONFIGURATION["_custom_"]["cml_parameters"].do_userStatus
            or False,
            do_repairs=CONFIGURATION["_custom_"]["cml_parameters"].do_repairs or False,
        )
    else:
        raise NotImplementedError(
            f" Can't find any action to be taken from {option} service option"
        )
