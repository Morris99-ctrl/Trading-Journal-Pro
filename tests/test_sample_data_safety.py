"""Regression tests for safe sample-data startup behavior."""

import unittest
from unittest.mock import Mock, patch

import cli
import main
from cli import TradingJournalCLI


class SampleDataSafetyTests(unittest.TestCase):
    def test_main_does_not_seed_samples_by_default(self):
        with patch("main.TradeService") as service_factory, patch("main.launch_web") as launch_web, patch("main.sys.argv", ["main.py"]):
            main.main()
        service_factory.return_value.seed_sample_data.assert_not_called()
        launch_web.assert_called_once()

    def test_main_demo_flag_seeds_only_empty_journal(self):
        with patch("main.TradeService") as service_factory, patch("main.launch_web"), patch("main.sys.argv", ["main.py", "--demo"]):
            service_factory.return_value.get_all_trades.return_value = []
            main.main()
        service_factory.return_value.seed_sample_data.assert_called_once_with()

    def test_main_demo_flag_refuses_non_empty_journal(self):
        with patch("main.TradeService") as service_factory, patch("main.launch_web"), patch("main.sys.argv", ["main.py", "--demo"]):
            service_factory.return_value.get_all_trades.return_value = [object()]
            main.main()
        service_factory.return_value.seed_sample_data.assert_not_called()

    def test_cli_demo_flag_seeds_empty_journal_explicitly(self):
        with patch("cli.TradeService") as service_factory, patch("cli.TradingJournalCLI"), patch("cli.sys.argv", ["cli.py", "--demo"]):
            service_factory.return_value.get_all_trades.return_value = []
            cli.main()
        service_factory.return_value.seed_sample_data.assert_called_once_with()

    def test_cli_entrypoint_does_not_seed_samples_by_default(self):
        with patch("cli.TradeService") as service_factory, patch("cli.TradingJournalCLI") as cli_factory, patch("cli.sys.argv", ["cli.py"]):
            cli.main()
        service_factory.return_value.seed_sample_data.assert_not_called()
        cli_factory.return_value.run.assert_called_once()

    def test_cli_sample_command_refuses_non_empty_journal(self):
        service = Mock()
        service.get_all_trades.return_value = [object()]
        journal_cli = TradingJournalCLI(service=service)
        with patch("builtins.input", side_effect=["sample", "exit"]):
            journal_cli.run()
        service.seed_sample_data.assert_not_called()

    def test_cli_sample_command_loads_into_empty_journal(self):
        service = Mock()
        service.get_all_trades.return_value = []
        journal_cli = TradingJournalCLI(service=service)
        with patch("builtins.input", side_effect=["sample", "exit"]):
            journal_cli.run()
        service.seed_sample_data.assert_called_once_with(clear_first=False)


if __name__ == "__main__":
    unittest.main()
