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
    """Acceptance tests for the heal engine.

    The timing suite is deterministic (no LLM). The locator-drift suite
    (tag live-llm) needs HEAL_MODEL/HEAL_BASE_URL/HEAL_API_KEY and runs
    only with --live-llm.
    """
    cmd = [
        "robot",
        "--outputdir results/heal-atest",
        f"{ROOT}/tests/atest/heal/heal_timing.robot",
    ]
    timing = subprocess.run(" ".join(cmd), shell=True, check=False)
    drift_rc = 0
    if live_llm:
        cmd = [
            "robot",
            "--outputdir results/heal-atest-llm",
            f"{ROOT}/tests/atest/heal/heal_locator_drift.robot",
        ]
        drift_rc = subprocess.run(" ".join(cmd), shell=True, check=False).returncode
    if timing.returncode != 0 or drift_rc != 0:
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