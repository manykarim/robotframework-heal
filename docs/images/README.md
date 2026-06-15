# Capturing report screenshots

The images on the *What you get* page are real heal report artifacts. To refresh
them after a UI change:

1. Run a suite that heals at least one locator, e.g. the bundled atest:

   ```bash
   uv run robot -d results tests/atest/heal/heal_locator_drift.robot
   ```

2. Screenshot the report HTML with the bundled Browser library (expands all
   transaction details first so the fix-proposal diff is visible):

   ```python
   from pathlib import Path
   import Browser
   from Browser.utils.data_types import ScreenshotFileTypes

   imgdir = Path("docs/images").resolve()
   b = Browser.Browser(); b.new_browser(headless=True)
   b.new_context(viewport={"width": 1200, "height": 900})

   b.new_page(Path("results/heal/heal_report.html").resolve().as_uri())
   b.evaluate_javascript(None, "() => document.querySelectorAll('details').forEach(d => d.open = true)")
   b.take_screenshot(filename=str(imgdir / "dashboard"), fullPage=True, fileType=ScreenshotFileTypes.png)

   b.new_page(next(Path("results/heal/diffs").glob("*.diff.html")).resolve().as_uri())
   b.take_screenshot(filename=str(imgdir / "diff"), fullPage=True, fileType=ScreenshotFileTypes.png)
   b.close_browser("ALL")
   ```

3. Refresh the `heal doctor` block from real output:

   ```bash
   heal doctor --role locator   # heal redacts API keys in its own output
   ```
