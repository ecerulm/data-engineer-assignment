import argparse
import logging
import logging.config
import operator
import sys
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from pprint import pp
from traceback import print_exc, print_last, print_stack

import requests

logging.basicConfig(level=logging.WARN, format="%(asctime)s %(levelname)s %(message)s")
try:
    logging.config.fileConfig("logging.conf")  # Load logging.conf if exist
except FileNotFoundError as e:
    # print("logging.conf not found:", e)
    pass
logger = logging.getLogger("smhi")


StationTemp = namedtuple("StationTemp", ["key", "name", "temp", "station"])


class SmhiParser:
    """
    Class to handle communication with and extract data from the SMHI Open API.
    """

    BASE_URL = "https://opendata-download-metobs.smhi.se/api"

    def __init__(self, suffix=".json"):
        self.suffix = suffix

    def _make_request(self, path=""):
        r = requests.get(self.BASE_URL + path + self.suffix)
        return r

    def check_connection(self):
        r = self._make_request()
        return r.status_code

    def print(self, *args, **kwargs):  # makes testing easier
        print(*args, **kwargs)

    def parameters(self):
        # https://opendata-download-metobs.smhi.se/api/version/1.0.json
        r = self._make_request(path="/version/1.0")

        params = sorted(r.json()["resource"], key=lambda x: int(x["key"]))
        # logger.debug("params %s", params)
        for param in params:
            # 1, Lufttemperatur (momentanvärde, 1 gång/tim)
            print(f"{param['key']:>3}, {param['title']} ({param['summary']})")
            # logger.debug(f"{param['key']:>3}, {param['title']} ({param['summary']})")

    def get_station_data(self, station):
        # https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/2/station/188790.json
        # https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/2/station/188790/period/latest-day.json
        # https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/2/station/188790/period/latest-day/data.json
        station_key = station["key"]
        r = self._make_request(
            path=f"/version/1.0/parameter/2/station/{station_key}/period/latest-day/data"
        )
        if r.status_code != 200:  # TODO: How shall we handle 404, etc
            logger.debug("URL %s returned status code %s", r.url, r.status_code)
            return None
        r = r.json()
        station_name = r["station"]["name"]
        try:
            station_temp = float(r["value"][0]["value"])
        except:
            # TODO: better error handling
            # value can be missing, be an empty list, the first eleemnt in the list may be missing 'value', or value can't be parsed as float
            logger.warning("Can't get temperature for station %s", station_name)
            return None
        station_data = StationTemp(
            key=r["station"]["key"],
            name=station_name,
            temp=station_temp,
            station=r["station"],
        )
        logger.info("station %s", station_data)
        return station_data

    def temperatures_parameter_2(self):
        # doc: https://opendata.smhi.se/metobs/resources/parameter
        # https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/2.json
        # https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/2/station/188790.json

        # There is no station set in parameter 2
        # So we need to loop over all the stations and fetch the data for each
        # we should check the updated field of each station

        version = "1.0"
        parameter = "2"

        r = self._make_request(path=f"/version/{version}/parameter/{parameter}")

        stations = r.json()["station"]

        # We sort the stations so that we have an stable order, to break
        # ties when several stations ties on min,max temperatures
        stations = sorted(stations, key=lambda x: x["key"])

        now = datetime.now(timezone.utc)
        min_station = StationTemp(
            key=None, temp=float("+inf"), name="N/A", station=None
        )
        max_station = StationTemp(
            key=None, temp=float("-inf"), name="N/A", station=None
        )
        for station in stations:
            updated = station["updated"]
            updated = datetime.fromtimestamp(updated // 1000, tz=timezone.utc)
            update_td = now - updated
            # TODO check if ignoring data older than 2 days is ok
            # We skip stations that have not been updated lately
            if update_td > timedelta(days=2):
                logger.debug(
                    "station '%s' ignored as it's not being updated for %s days",
                    station["name"],
                    update_td.days,
                )
                continue
            # fetch station data
            station_data = self.get_station_data(station)
            if not station_data:
                # skip if station data is None, due to missing data for the period, etc
                continue
            if station_data.temp > max_station.temp:
                max_station = station_data
            if station_data.temp < min_station.temp:
                min_station = station_data

        print(f"Highest temperature: {max_station.name}, {max_station.temp:.1f} degrees")
        print(f"Lowest temperature: {min_station.name}, {min_station.temp:.1f} degrees")


def main():
    parser = argparse.ArgumentParser(
        description="""Script to extract data from SMHI's Open API"""
    )
    parser.add_argument(
        "--parameters", action="store_true", help="List SMHI API parameters"
    )
    parser.add_argument(
        "--temperatures",
        action="store_true",
        help="List highest and lowest average temperatures",
    )
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    parser = SmhiParser()

    if args.parameters:
        parser.parameters()

    if args.temperatures:
        # parser.temperatures()
        parser.temperatures_parameter_2()


if __name__ == "__main__":
    main()
