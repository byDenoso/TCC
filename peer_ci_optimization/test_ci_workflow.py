from pathlib import Path

import yaml


CI = Path(".github/workflows/peer-ci-optimization-tests.yml")
README = Path(".github/launch/README.md")


def test_ci_workflow_runs_only_pure_verification_on_pull_requests() -> None:
    workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
    assert "pull_request" in (workflow.get(True) or workflow.get("on"))
    jobs = workflow["jobs"]
    assert set(jobs) == {"verify"}
    scripts = "\n".join(step.get("run", "") for step in jobs["verify"]["steps"])
    assert "pytest -q peer_ci_optimization" in scripts
    assert "py_compile" in scripts
    assert "mpirun" not in scripts
    assert "cobaya-run" not in scripts


def test_launch_readme_requires_dedicated_marker_and_preserves_manual_resume() -> None:
    text = README.read_text(encoding="utf-8")
    assert ".github/launch/peer-act20-optimized.txt" in text
    assert "resume_run_id" in text
    assert "não mesclar" in text.lower()
