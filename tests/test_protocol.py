import unittest

from wallet_privacy_testkit.protocol import RawTransaction, SendResponse


class ProtocolTests(unittest.TestCase):
    def test_minimal_schema_round_trips_the_required_fields(self):
        raw = RawTransaction(data=b"unchanged", height=123)
        decoded = RawTransaction.FromString(raw.SerializeToString())
        self.assertEqual(decoded.data, b"unchanged")
        self.assertEqual(decoded.height, 123)

        response = SendResponse(errorCode=-1, errorMessage="duplicate")
        decoded_response = SendResponse.FromString(response.SerializeToString())
        self.assertEqual(decoded_response.errorCode, -1)
        self.assertEqual(decoded_response.errorMessage, "duplicate")


if __name__ == "__main__":
    unittest.main()
