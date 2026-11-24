import subprocess
import time

import mistune


def test_ac_nfr_001_1():
    """AC-NFR-001-1: Benchmark execution time has < 5% regression on benchmark suite."""
    start = time.perf_counter()
    result = subprocess.run(
        ["uv", "run", "python", "benchmark/bench.py"],
        capture_output=True,
        text=True,
    )
    duration = time.perf_counter() - start
    assert result.returncode == 0, f"Benchmark suite failed: {result.stderr}"
    assert duration < 15.0, f"Benchmark execution took too long: {duration}s"


def test_ac_nfr_002_1():
    """AC-NFR-002-1: Mypy error count is 0 on src/mistune."""
    result = subprocess.run(
        ["uv", "run", "mypy", "src/mistune"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Mypy check failed with errors:\n{result.stdout}\n{result.stderr}"
    assert "Success: no issues found" in result.stdout


def test_url_plugin_www():
    """AC-NFR-001-1 & AC-NFR-002-1: Verification of www. URL parsing via public API."""
    md = mistune.create_markdown(plugins=["url"])
    result = md("Visit www.example.com for details.")
    assert result.strip() == '<p>Visit <a href="https://www.example.com">www.example.com</a> for details.</p>'
