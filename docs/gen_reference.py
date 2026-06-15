"""Build-time reference generation (mkdocs-gen-files hook).

Generates the user-facing configuration and CLI reference pages so they never
drift from the code. Task 2.2 fills in the real generation; for now it emits
placeholders so the nav resolves and `mkdocs build --strict` passes.
"""

import mkdocs_gen_files

_PLACEHOLDER = "# {title}\n\n!!! note\n    Generated reference — populated at build time.\n"

for path, title in [
    ("reference/configuration.md", "Configuration reference"),
    ("reference/cli.md", "CLI reference"),
]:
    with mkdocs_gen_files.open(path, "w") as fd:
        fd.write(_PLACEHOLDER.format(title=title))
