"""Regression tests for the Flask web interface."""

import unittest

from diced.web import create_app, format_percent


class WebInterfaceTests(unittest.TestCase):
    """Verify the browser-facing layer renders expected results."""

    def setUp(self) -> None:
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_homepage_loads(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"DICED", response.data)

    def test_calculation_results_render(self) -> None:
        response = self.client.get("/", query_string={"sequence": "3++ 4+"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"DICED", response.data)
        self.assertIn(b"44.4%", response.data)
        self.assertIn(b"(66.7% / 66.7%)", response.data)
        self.assertIn(b"3++ 4+", response.data)
        self.assertIn(b"........", response.data)

    def test_server_response_does_not_persist_log_lines(self) -> None:
        self.client.get("/", query_string={"sequence": "2+"})
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Type a chain and press Go!", response.data)

    def test_invalid_input_shows_error(self) -> None:
        response = self.client.get("/", query_string={"sequence": "8+"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid roll target", response.data)


class WebFormattingTests(unittest.TestCase):
    """Keep shared formatting helpers predictable."""

    def test_formats_percent_with_one_decimal(self) -> None:
        self.assertEqual(format_percent(2 / 3), "66.7%")


if __name__ == "__main__":
    unittest.main()