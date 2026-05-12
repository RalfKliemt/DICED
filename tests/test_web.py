"""Regression tests for the Flask web interface."""

import unittest

from diced.web import create_app, format_percent, format_token_for_display


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


class TokenFormattingTests(unittest.TestCase):
    """Verify block dice tokens display correctly."""

    def test_formats_block_dice_plus_modifier(self) -> None:
        """Block dice with + should display as (Block)."""
        self.assertEqual(format_token_for_display("2d+"), "2d (Block)")
        self.assertEqual(format_token_for_display("3d+"), "3d (Block)")
        self.assertEqual(format_token_for_display("1d+"), "1d (Block)")

    def test_formats_block_dice_push_modifier(self) -> None:
        """Block dice with - should display as (Push)."""
        self.assertEqual(format_token_for_display("2d-"), "2d (Push)")
        self.assertEqual(format_token_for_display("3d-"), "3d (Push)")

    def test_formats_block_dice_pow_only_modifier(self) -> None:
        """Block dice with * should display as (Pow)."""
        self.assertEqual(format_token_for_display("2d*"), "2d (Pow)")

    def test_formats_block_dice_push_only_modifier(self) -> None:
        """Block dice with / should display as (Push Only)."""
        self.assertEqual(format_token_for_display("2d/"), "2d (Push Only)")

    def test_leaves_normal_dice_unchanged(self) -> None:
        """Normal dice tokens should not be modified."""
        self.assertEqual(format_token_for_display("2+"), "2+")
        self.assertEqual(format_token_for_display("3++"), "3++")
        self.assertEqual(format_token_for_display("4+"), "4+")

    def test_leaves_non_block_tokens_unchanged(self) -> None:
        """Non-dice tokens should remain unchanged."""
        self.assertEqual(format_token_for_display("av9"), "av9")
        self.assertEqual(format_token_for_display("av9im"), "av9im")



if __name__ == "__main__":
    unittest.main()