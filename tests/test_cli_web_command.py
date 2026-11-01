import unittest
from unittest.mock import patch

from cli import TradingJournalCLI


class CliWebCommandTests(unittest.TestCase):
    def test_web_command_opens_browser_and_launches_web_app(self):
        cli = TradingJournalCLI(service=None)

        with patch("builtins.input", side_effect=["web", "exit"]), patch(
            "webbrowser.open"
        ) as browser_open, patch("cli.os.system", return_value=0) as system_call:
            cli.run()

        browser_open.assert_called_once_with("http://127.0.0.1:5000")
        system_call.assert_called_once_with(f'"{__import__("sys").executable}" web_app.py')


if __name__ == "__main__":
    unittest.main()
