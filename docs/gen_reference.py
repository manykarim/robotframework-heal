"""Build-time reference generation (mkdocs-gen-files hook).

Thin wrapper: the pure generation logic lives in `_refgen` (so it is
unit-testable without a mkdocs runtime); this script writes the result.
A completeness guard in `_refgen` fails the build if a setting lacks a
description or a CLI command is missed, so the docs cannot drift from code.
"""

import pathlib
import sys

import mkdocs_gen_files

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _refgen  # noqa: E402

with mkdocs_gen_files.open("reference/configuration.md", "w") as fd:
    fd.write(_refgen.generate_config_reference())

with mkdocs_gen_files.open("reference/cli.md", "w") as fd:
    fd.write(_refgen.generate_cli_reference())
