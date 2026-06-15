import pathlib
import subprocess
from invoke import task
import inspect

if not hasattr(inspect, 'getargspec'):
    inspect.getargspec = inspect.getfullargspec

ROOT = pathlib.Path(__file__).parent.resolve().as_posix()
utests_completed_process = None
atests_completed_process = None

@task
def utests(context):
    cmd = [
        "coverage",
        "run",
        "--source=src/heal,src/SelfHealing",
        "-p",
        "-m",
        "pytest",
        "--junitxml=results/pytest.xml",
        f"{ROOT}/tests/unit",
    ]
    global utests_completed_process
    utests_completed_process = subprocess.run(" ".join(cmd), shell=True, check=False)

@task
def atests(context):
    cmd = [
        "coverage",
        "run",
        "--source=src/SelfHealing",
        "-p",
        "-m",
        "robot",
        "--loglevel=TRACE:DEBUG",
        "--listener RobotStackTracer",
        "--exclude appiumORnot_readyORnot_ci",
        "-d results",
        "--prerebotmodifier utilities.xom.XUnitOut:results/xunit.xml",
        f"{ROOT}/tests/atest"
    ]
    global atests_completed_process
    atests_completed_process = subprocess.run(" ".join(cmd), shell=True, check=False)

@task
def heal_atests(context, live_llm=False):
    """Acceptance tests for the heal engine (bundled demo pages only).

    Deterministic suites (tag ``heal-atest``: timing recoveries) need no LLM
    and run always. Live suites (tag ``live-llm``: locator drift, keyword-arg
    fixing, Selenium, shadow DOM / iframes) need HEAL_MODEL/HEAL_BASE_URL/
    HEAL_API_KEY and run only with ``--live-llm`` (used by the e2e workflow).

    The external-site demo suites under ``tests/atest/`` are exploratory and
    are not run here.
    """
    pathlib.Path(f"{ROOT}/results").mkdir(parents=True, exist_ok=True)
    deterministic = subprocess.run(
        f"robot --outputdir {ROOT}/results/heal-atest --include heal-atest "
        f"{ROOT}/tests/atest/heal",
        shell=True, check=False,
    )
    live_rc = 0
    if live_llm:
        live = subprocess.run(
            f"robot --outputdir {ROOT}/results/heal-atest-llm --include live-llm "
            f"{ROOT}/tests/atest/heal",
            shell=True, check=False,
        )
        live_rc = live.returncode
    if deterministic.returncode != 0 or live_rc != 0:
        raise Exception("heal atests failed")

@task
def heal_utests(context):
    pathlib.Path(f"{ROOT}/results").mkdir(parents=True, exist_ok=True)
    rc = subprocess.run(
        f"pytest -q --junitxml={ROOT}/results/pytest.xml {ROOT}/tests/unit",
        shell=True, check=False,
    ).returncode
    if rc != 0:
        raise Exception("heal unit tests failed")

@task(utests, atests)
def tests(context):
    subprocess.run("coverage combine", shell=True, check=False)
    subprocess.run("coverage report", shell=True, check=False)
    subprocess.run("coverage html -d results/htmlcov", shell=True, check=False)
    if utests_completed_process.returncode != 0 or atests_completed_process.returncode != 0:
        raise Exception("Tests failed")

@task
def coverage_report(context):
    subprocess.run("coverage combine", shell=True, check=False)
    subprocess.run("coverage report", shell=True, check=False)
    subprocess.run("coverage html -d results/htmlcov", shell=True, check=False)