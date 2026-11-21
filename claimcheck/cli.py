import argparse
import sys

from claimcheck.commands.validate_command import ValidateCommand
from claimcheck.config import Config


class Cli:
    """Parses the command line and hands off to the command."""

    def run(self, argv: list[str] | None = None) -> int:
        """Run `claimcheck`.

        Args:
            argv: The arguments after the program name. Defaults to `sys.argv`.

        Returns:
            The exit code: 0 on success, 1 for an error the user can fix.
        """
        self._parser().parse_args(argv)
        try:
            ValidateCommand(Config.load()).run()
        except (FileNotFoundError, PermissionError, RuntimeError, ValueError) as error:
            print(f"claimcheck: {error}", file=sys.stderr)
            return 1
        return 0

    def _parser(self) -> argparse.ArgumentParser:
        return argparse.ArgumentParser(
            prog="claimcheck",
            description="Review the claim-extraction sets in ~/claimcheck_data in your browser. "
            "Results are saved to manual_validation_results.jsonl in that folder.",
        )


def main() -> None:
    """The `claimcheck` console script."""
    sys.exit(Cli().run())
