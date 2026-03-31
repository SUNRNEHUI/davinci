"""Shared CLI test helpers."""

from __future__ import annotations

import io
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


def run_cli(argv: list[str], *, cli_home: Path) -> tuple[int, str, str]:
    import leica_cli

    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch.dict(
        os.environ,
        {
            "LEICA_CLI_HOME": str(cli_home),
            "DAVINCI_OUTPUT_ROOT": str(cli_home.parent / "davinci_output"),
        },
    ):
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = leica_cli.main(argv)
    return rc, stdout.getvalue(), stderr.getvalue()
