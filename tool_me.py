import os
import sys
import logging
from datetime import datetime

# set working directory the script's
os.chdir(os.path.dirname(os.path.realpath(__file__)))


from bins.configuration import CONFIGURATION
from bins.general.general_utilities import log_time_passed, convert_string_datetime
from apps import (
    database_feeder,
    database_feeder_service,
    database_checker,
    database_analysis,
)


# START ####################################################################################################################
if __name__ == "__main__":

    print(f" Python version: {sys.version}")

    __module_name = " Gamma tools"

    ##### main ######
    logging.getLogger(__name__).info(
        " Start {}   ----------------------> ".format(__module_name)
    )
    # start time log
    _startime = datetime.utcnow()

    # convert datetimes if exist
    if CONFIGURATION["_custom_"]["cml_parameters"].ini_datetime:
        # convert to datetime
        try:
            CONFIGURATION["_custom_"][
                "cml_parameters"
            ].ini_datetime = convert_string_datetime(
                string=CONFIGURATION["_custom_"]["cml_parameters"].ini_datetime
            )
        except Exception:
            logging.getLogger(__name__).error(
                f" Can't convert command line passed ini datetime-> {CONFIGURATION['_custom_']['cml_parameters'].ini_datetime}"
            )
    if CONFIGURATION["_custom_"]["cml_parameters"].end_datetime:
        # convert to datetime
        try:
            CONFIGURATION["_custom_"][
                "cml_parameters"
            ].end_datetime = convert_string_datetime(
                string=CONFIGURATION["_custom_"]["cml_parameters"].end_datetime
            )
        except Exception:
            logging.getLogger(__name__).error(
                f" Can't convert command line passed end datetime-> {CONFIGURATION['_custom_']['cml_parameters'].end_datetime}"
            )

    # choose the first of the  parsed options
    if CONFIGURATION["_custom_"]["cml_parameters"].db_feed:
        # database feeder:  -db_feed operations
        database_feeder.main(option=CONFIGURATION["_custom_"]["cml_parameters"].db_feed)
    elif CONFIGURATION["_custom_"]["cml_parameters"].service:
        # service loop
        database_feeder_service.main(
            option=CONFIGURATION["_custom_"]["cml_parameters"].service
        )
    elif CONFIGURATION["_custom_"]["cml_parameters"].service_network:
        # service loop specific
        database_feeder_service.main(
            option="network",
            network=CONFIGURATION["_custom_"]["cml_parameters"].service_network,
            protocol="gamma",
        )
    elif CONFIGURATION["_custom_"]["cml_parameters"].check:
        # checks
        database_checker.main(option=CONFIGURATION["_custom_"]["cml_parameters"].check)

    elif CONFIGURATION["_custom_"]["cml_parameters"].analysis:
        # analysis
        database_analysis.main(
            option=CONFIGURATION["_custom_"]["cml_parameters"].analysis
        )

    else:
        # nothin todo
        logging.getLogger(__name__).info(" Nothing to do. How u doin? ")

    logging.getLogger(__name__).info(
        " took {} to complete".format(
            log_time_passed.get_timepassed_string(start_time=_startime)
        )
    )
    logging.getLogger(__name__).info(
        " Exit {}    <----------------------".format(__module_name)
    )
