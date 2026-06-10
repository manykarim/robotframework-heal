import asyncio

from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from heal.core.doctor import DoctorReport, ProbeResult, run_doctor
from heal.core.runtime import ToolSupport
from heal.core.settings import OutputMode


def report_with(**outcomes: bool) -> DoctorReport:
    return DoctorReport(
        model_name="m",
        results=[ProbeResult(name=name, ok=ok) for name, ok in outcomes.items()],
    )


def test_capabilities_full_support():
    report = report_with(
        tool_output=True, native_output=True, prompted_output=True, exploration_tool=True, vision=True
    )
    caps = report.capabilities()
    assert caps.structured_output is OutputMode.TOOL
    assert caps.tools is ToolSupport.RELIABLE
    assert caps.vision is True


def test_capabilities_minimax_like():
    # tool transport broken, native works, no reliable exploration (probe-1 profile)
    report = report_with(
        tool_output=False, native_output=True, prompted_output=True, exploration_tool=False, vision=False
    )
    caps = report.capabilities()
    assert caps.structured_output is OutputMode.NATIVE
    assert caps.tools is ToolSupport.NONE
    assert caps.vision is False


def test_capabilities_prompted_floor():
    # qwen3-14b-on-openrouter profile: no tool endpoints at all
    report = report_with(
        tool_output=False, native_output=False, prompted_output=True, exploration_tool=False, vision=False
    )
    caps = report.capabilities()
    assert caps.structured_output is OutputMode.PROMPTED
    assert caps.tools is ToolSupport.NONE


def test_recommendations_unreachable():
    report = report_with(tool_output=False, native_output=False, prompted_output=False, exploration_tool=False)
    report.results[0].error = "ModelHTTPError: status_code: 404"
    recs = report.recommendations()
    assert any("unreachable" in r.lower() for r in recs)
    assert any("404" in r for r in recs)


def test_recommendations_degraded_modes():
    report = report_with(
        tool_output=False, native_output=True, prompted_output=True, exploration_tool=False, vision=False
    )
    text = " ".join(report.recommendations())
    assert "'native'" in text
    assert "curated evidence" in text
    assert "DOM-only" in text


def test_run_doctor_with_test_model():
    report = asyncio.run(run_doctor(TestModel(), model_name="test", include_vision=False))
    assert report.model_name == "test"
    assert report.reachable
    assert report.passed("tool_output")
    assert report.passed("exploration_tool")
    # native is rejected by TestModel's profile -> recorded as failure, not crash
    assert report.result("native_output") is not None
    assert not report.passed("native_output")


def test_run_doctor_with_broken_model():
    def explode(messages, info: AgentInfo):
        raise RuntimeError("connection refused")

    report = asyncio.run(run_doctor(FunctionModel(explode), model_name="broken", include_vision=False))
    assert not report.reachable
    assert all(not r.ok for r in report.results)
    assert all(r.error for r in report.results)
    assert any("unreachable" in r.lower() for r in report.recommendations())
