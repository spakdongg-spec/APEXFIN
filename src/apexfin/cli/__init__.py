"""CLI (L6): the only module allowed to see both `reporting` and the pipeline.

`__main__.py` and the `apexfin` console script both land here. The CLI is the
composition root: it opens one connection, migrates, builds the `RunContext`,
registers the `render` step, and wires the ten commands from CLI_CONTRACT.
"""

from apexfin.cli.state import CliState

__all__ = ["CliState"]
