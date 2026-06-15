from pathlib import Path

from typer.testing import CliRunner

from heal.cli.main import app
from heal.mcp import server as mcp_server
from heal.report.store import RunStore

from ..report.test_store_and_reports import make_event

runner = CliRunner()


def make_store(tmp_path) -> Path:
    store = RunStore(tmp_path / "heal")
    store.append(make_event("e1"))
    from heal.core.schemas import OutcomeStatus

    store.append(make_event("e2", status=OutcomeStatus.UNHEALED, lineno=20))
    return store.directory


def test_triage_command(tmp_path):
    directory = make_store(tmp_path)
    result = runner.invoke(app, ["triage", str(directory)])
    assert result.exit_code == 0
    assert "2 transactions: 1 healed, 1 unhealed" in result.output
    assert "fix[local]" in result.output


def test_triage_finds_store_under_outputdir(tmp_path):
    make_store(tmp_path)
    result = runner.invoke(app, ["triage", str(tmp_path)])
    assert result.exit_code == 0


def test_report_command(tmp_path):
    directory = make_store(tmp_path)
    result = runner.invoke(app, ["report", str(directory)])
    assert result.exit_code == 0
    assert (directory / "heal_report.html").is_file()
    assert (directory / "summary.json").is_file()


def test_apply_handles_unresolvable_sources(tmp_path):
    # fixture events point at /s/login.robot which does not exist -> no crash
    directory = make_store(tmp_path)
    result = runner.invoke(app, ["apply", str(directory)])
    assert result.exit_code == 0


def test_mcp_tools_over_store(tmp_path):
    directory = make_store(tmp_path)
    mcp_server._events_path = directory / "events.jsonl"
    try:
        import json

        rows = json.loads(mcp_server.list_failures.__wrapped__() if hasattr(mcp_server.list_failures, "__wrapped__") else mcp_server.list_failures())
        assert {r["event_id"] for r in rows} == {"e1", "e2"}
        bundle = json.loads(mcp_server.get_failure_bundle("e1"))
        assert bundle["outcome"]["status"] == "healed"
        proposals = json.loads(mcp_server.get_fix_proposals())
        assert len(proposals) == 1 and proposals[0]["event_id"] == "e1"
        missing = json.loads(mcp_server.get_failure_bundle("nope"))
        assert "error" in missing
    finally:
        mcp_server._events_path = None
