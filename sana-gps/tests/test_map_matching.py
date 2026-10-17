import json
import unittest
from io import BytesIO
from unittest.mock import patch

from app.processing.map_matching import _request_matched_points, _valid_coordinate


class MapMatchingTests(unittest.TestCase):
    def test_rejects_invalid_coordinates(self):
        self.assertIsNone(_valid_coordinate(None, 51.4))
        self.assertIsNone(_valid_coordinate(91, 51.4))
        self.assertIsNone(_valid_coordinate(35.7, 181))
        self.assertEqual(_valid_coordinate("35.7", "51.4"), (35.7, 51.4))

    @patch("app.processing.map_matching.urlopen")
    def test_sends_ordered_latitude_longitude_path_and_maps_original_indices(self, urlopen):
        response = BytesIO(json.dumps({
            "snappedPoints": [
                {"originalIndex": 1, "location": [35.701, 51.402]},
                {"originalIndex": 0, "location": [35.700, 51.400]},
                {"originalIndex": 2, "location": [999, 51.400]},
            ]
        }).encode())
        response.__enter__ = lambda self=response: self
        response.__exit__ = lambda *_args: False
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

    def test_does_not_call_api_for_fewer_than_two_points(self):
        with patch("app.processing.map_matching.urlopen") as urlopen:
            self.assertEqual(_request_matched_points("test-key", [(1, 35.7, 51.4)]), {})
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
