from pathlib import Path

from tools import trace_demo


def test_trace_demo_bundled_backend_resolution():
    parser = trace_demo.build_parser()
    args = parser.parse_args(["--demo", "backend"])
    jd, resume = trace_demo.resolve_inputs(args)
    assert jd.name == "backend_jd.txt"
    assert resume.name == "01_strong.txt"
    assert jd.exists()
    assert resume.exists()


def test_trace_demo_bundled_hr_resolution():
    parser = trace_demo.build_parser()
    args = parser.parse_args(["--demo", "hr"])
    jd, resume = trace_demo.resolve_inputs(args)
    assert jd.name == "hr_jd.txt"
    assert resume.name == "01_hr_strong.txt"
    assert jd.exists()
    assert resume.exists()


def test_trace_demo_requires_inputs_when_not_demo():
    parser = trace_demo.build_parser()
    args = parser.parse_args([])
    try:
        trace_demo.resolve_inputs(args)
    except ValueError as exc:
        assert "--demo" in str(exc)
    else:
        raise AssertionError("resolve_inputs should reject missing JD/resume")
