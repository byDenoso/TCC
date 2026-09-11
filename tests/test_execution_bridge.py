from nexo_control_plane.execution_bridge import ExecutionDescriptor, build_execution_contract, provider_for
from nexo_control_plane.models import WorkDomain, WorkRecord, WorkStatus


def _work(runtime: str, domain: WorkDomain = WorkDomain.SCIENCE) -> WorkRecord:
    return WorkRecord(
        work_id="WORK-001",
        thread_id="thread",
        domain=domain,
        status=WorkStatus.READY,
        runtime_requirement=runtime,
        work_type="T-DE001",
        attempt=1,
    )


def _descriptor() -> ExecutionDescriptor:
    return ExecutionDescriptor(
        task_id="cosmology_benchmark",
        repository="byDenoso/TCC",
        commit_sha="c4158fec93625d638ef05ecc92799bee4700513f",
        required_outputs=("benchmark_result.json",),
        parameters={},
        seed=20260911,
        timeout_minutes=15,
    )


def test_heavy_science_routes_to_actions():
    work = _work("MCMC")
    assert provider_for(work) == "github_actions"
    contract = build_execution_contract(work, _descriptor())
    assert contract.provider == "github_actions"
    assert contract.execution_id == "EXEC-WORK-001-A2"
    assert contract.test_id == "T-DE001"
    assert contract.commit_sha == "c4158fec93625d638ef05ecc92799bee4700513f"


def test_light_science_stays_local():
    work = _work("LIGHT")
    assert provider_for(work) == "local"
    contract = build_execution_contract(work, _descriptor())
    assert contract.provider == "local"


def test_olympus_stays_local_even_if_heavy():
    work = _work("HEAVY", WorkDomain.OLYMPUS)
    assert provider_for(work) == "local"
