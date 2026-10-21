import json
import unittest
from unittest.mock import MagicMock, patch

from app.processing.map_matching import (
    _request_matched_points,
    _valid_coordinate,
    has_active_map_matching_viewers,
    process_pending_map_matches,
)


class MapMatchingTests(unittest.TestCase):
    def test_rejects_invalid_coordinates(self):
        self.assertIsNone(_valid_coordinate(None, 51.4))
        self.assertIsNone(_valid_coordinate(91, 51.4))
        self.assertIsNone(_valid_coordinate(35.7, 181))
        self.assertEqual(_valid_coordinate("35.7", "51.4"), (35.7, 51.4))

    @patch("app.processing.map_matching.urlopen")
    def test_sends_ordered_latitude_longitude_path_and_maps_original_indices(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({
            "snappedPoints": [
                {"originalIndex": 1, "location": [35.701, 51.402]},
                {"originalIndex": 0, "location": [35.700, 51.400]},
                {"originalIndex": 2, "location": [999, 51.400]},
            ]
        }).encode()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        urlopen.return_value = response

        points = [
            (10, 35.7, 51.4),
            (11, 35.701, 51.401),
        ]
        result = _request_matched_points("test-key", points)

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode())
        self.assertEqual(body["path"], "35.7000000,51.4000000|35.7010000,51.4010000")
        self.assertEqual(request.get_header("Api-key"), "test-key")
        self.assertEqual(result, {0: (35.7, 51.4), 1: (35.701, 51.402)})

    def test_active_map_viewer_enables_matching_worker(self):
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (True,)
        self.assertTrue(has_active_map_matching_viewers(pool))

    def test_expired_or_missing_map_viewer_disables_matching_worker(self):
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (False,)
        self.assertFalse(has_active_map_matching_viewers(pool))

    @patch("app.processing.map_matching.urlopen")
    def test_parses_real_neshan_location_object(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({
            "snappedPoints": [
                {"originalIndex": 0, "location": {"latitude": 34.359806, "longitude": 47.091189}},
                {"originalIndex": 1, "location": {"latitude": 34.360100, "longitude": 47.091500}},
            ]
        }).encode()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        urlopen.return_value = response

        result = _request_matched_points("test-key", [
            (10, 34.3598, 47.0912),
            (11, 34.3601, 47.0915),
        ])

        self.assertEqual(result, {
            0: (34.359806, 47.091189),
            1: (34.360100, 47.091500),
        })

    def test_does_not_call_api_for_fewer_than_two_points(self):
        with patch("app.processing.map_matching.urlopen") as urlopen:
            self.assertEqual(_request_matched_points("test-key", [(1, 35.7, 51.4)]), {})
        urlopen.assert_not_called()


    @patch("app.processing.map_matching._request_matched_points")
    def test_persists_only_neshan_matches_linked_to_traccar_positions(self, request_matches):
        from datetime import datetime, timezone

        imei = "352016703005868"
        pool = MagicMock()
        connection = pool.connection.return_value.__enter__.return_value

        def execute(sql, params=()):
            cursor = MagicMock()
            if "SELECT id, imei FROM public.fleet_device" in sql:
                cursor.fetchall.return_value = [(9, imei)]
            elif "SELECT traccar_position_id FROM gps.map_matched_position" in sql:
                cursor.fetchall.return_value = []
            else:
                cursor.fetchall.return_value = []
            return cursor

        connection.execute.side_effect = execute
        connection.transaction.return_value.__enter__.return_value = None

        client = MagicMock()
        client.list_devices.return_value = [{"id": 42, "uniqueId": imei}]
        client.list_positions.return_value = [
            {
                "id": 100,
                "fixTime": "2026-10-21T07:00:00.000Z",
                "latitude": 35.7000,
                "longitude": 51.4000,
                "valid": True,
            },
            {
                "id": 101,
                "fixTime": "2026-10-21T07:00:10.000Z",
                "latitude": 35.7010,
                "longitude": 51.4010,
                "valid": True,
            },
        ]
        request_matches.return_value = {
            0: (35.7001, 51.4001),
            1: (35.7011, 51.4011),
        }

        saved = process_pending_map_matches(pool, "test-neshan-key", client)

        assert saved == 2
        insert_calls = [
            call for call in connection.execute.call_args_list
            if "INSERT INTO gps.map_matched_position" in call.args[0]
        ]
        assert len(insert_calls) == 2
        assert insert_calls[0].args[1][0:4] == (
            100, 42, 9, datetime(2026, 10, 21, 7, 0, tzinfo=timezone.utc)
        )
        assert insert_calls[0].args[1][4:6] == (35.7001, 51.4001)
        statements = [call.args[0] for call in connection.execute.call_args_list]
        assert not any("gps.raw_packet" in sql for sql in statements)
        assert not any("gps.location_history" in sql for sql in statements)
        assert not any("gps.current_state" in sql for sql in statements)


if __name__ == "__main__":
    unittest.main()
