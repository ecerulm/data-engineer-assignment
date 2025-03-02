from datetime import datetime
from unittest.mock import Mock

import requests

from smhi.smhi import SmhiParser, StationTemp


def test_check_connection():
    parser = SmhiParser()
    assert 200 == parser.check_connection()


def test_parameters(capsys):
    # endoscopic test
    spy = Mock(spec=SmhiParser)
    spy._make_request(path="/version/1.0").json.return_value = {
        "resource": [
            {"key": "20", "title": "param20", "summary": "summary20"},
            {"key": "10", "title": "param10", "summary": "summary10"},
        ]
    }
    SmhiParser.parameters(spy)

    captured = capsys.readouterr()
    assert "10, param10 (summary10)" in captured.out
    assert "20, param20 (summary20)" in captured.out


def test_temperatures_only_one_station(capsys):
    # endoscopic test we test only temperatures_parameter_2 in isolation
    # all the collaborator methods in the class are mocked
    spy = Mock(spec=SmhiParser)

    spy._make_request(path="/version/1.0/parameter/2").json.return_value = {
        "station": [
            {
                "updated": datetime.now().timestamp() * 1000,
                "key": "1",
                "name": "stationA",
            },
        ],
    }
    spy.get_station_data.return_value = StationTemp(
        key="1", temp=-99, name="stationA", station=None
    )
    SmhiParser.temperatures_parameter_2(spy)

    captured = capsys.readouterr()
    assert "Highest temperature: stationA, -99.0 degrees" in captured.out
    assert "Lowest temperature: stationA, -99.0 degrees" in captured.out


def test_temperatures_only_two_stations(capsys):
    # endoscopic test we test only temperatures_parameter_2 in isolation
    # all the collaborator methods in the class are mocked
    spy = Mock(spec=SmhiParser)

    spy._make_request(path="/version/1.0/parameter/2").json.return_value = {
        "station": [
            {
                "updated": datetime.now().timestamp() * 1000,
                "key": "1",
            },
            {
                "updated": datetime.now().timestamp() * 1000,
                "key": "2",
            },
        ],
    }
    spy.get_station_data.side_effect = [
        StationTemp(key="1", temp=-99, name="stationA", station=None),
        StationTemp(key="2", temp=99, name="stationB", station=None),
    ]
    SmhiParser.temperatures_parameter_2(spy)

    captured = capsys.readouterr()
    assert "Highest temperature: stationB, 99.0 degrees" in captured.out
    assert "Lowest temperature: stationA, -99.0 degrees" in captured.out


def test_temperatures_integration(capsys):
    parser = SmhiParser()

    def _make_request(path=""):
        # mock
        mock = Mock(spec=requests.Response)
        mock.status_code = 200
        match path:
            case "/version/1.0/parameter/2":
                mock.json.return_value = {
                    "station": [
                        {
                            "updated": datetime.now().timestamp() * 1000,
                            "key": "3",
                        },
                        {
                            "updated": datetime.now().timestamp() * 1000,
                            "key": "1",
                        },
                        {
                            "updated": datetime.now().timestamp() * 1000,
                            "key": "2",
                        },
                    ],
                }
            case "/version/1.0/parameter/2/station/3/period/latest-day/data":
                mock.json.return_value = {
                    "station": {
                        "key": "3",
                        "name": "station3",
                    },
                    "value": [
                        {
                            "value": "10.0",
                        }
                    ],
                }
            case "/version/1.0/parameter/2/station/2/period/latest-day/data":
                mock.json.return_value = {
                    "station": {
                        "key": "2",
                        "name": "station2",
                    },
                    "value": [
                        {
                            "value": "11.0",
                        }
                    ],
                }
            case "/version/1.0/parameter/2/station/1/period/latest-day/data":
                mock.json.return_value = {
                    "station": {
                        "key": "1",
                        "name": "station1",
                    },
                    "value": [
                        {
                            "value": "12.0",
                        }
                    ],
                }
            case _:
                raise Exception(f"this should not happen. path = {path}")

        return mock

    parser._make_request = _make_request
    parser.temperatures_parameter_2()

    captured = capsys.readouterr()
    assert "Highest temperature: station1, 12.0 degrees" in captured.out
    assert "Lowest temperature: station3, 10.0 degrees" in captured.out


# TODO: test stations with same temperature
# TODO: test invalid data is skipped, 404, missing value, value = [], value.value = unparseable string
