from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    spec = importlib.util.find_spec("peer_decisive_followups.polychord_bootstrap_patch")
    assert spec is not None, "polychord_bootstrap_patch module is required"
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fixture_source() -> str:
    return """module generate_module
    use utils_module, only: dp
    implicit none
    contains

    subroutine GenerateLivePoints(loglikelihood,prior,settings,RTI,mpi_information)
        use settings_module,  only: program_settings
        use random_module,   only: random_reals
        use run_time_module, only: run_time_info,initialise_run_time_info, find_min_loglikelihoods
        use array_module, only: add_point
        implicit none
        integer :: nlike
        integer :: nprior, ndiscarded
        integer :: ngenerated
        real(dp) :: time0,time1,total_time
        nlike = 0
        ngenerated = 1
        if(is_root(mpi_information)) then
            call initialise_run_time_info(settings,RTI)
        end if
        ndiscarded=0
        total_time=0
        if(linear_mode(mpi_information)) then
            do while(RTI%nlive(1)<nprior)
                live_point(settings%h0:settings%h1) = random_reals(settings%nDims)
            end do
#ifdef MPI
        else
            if(is_root(mpi_information)) then
                active_workers=mpi_information%nprocs-1
                do worker_id=1,active_workers
                    live_point(settings%h0:settings%h1) = random_reals(settings%nDims)
                    live_point(settings%b0) = ngenerated
                    ngenerated = ngenerated+1
                    call request_live_point(live_point,mpi_information,worker_id)
                end do
                do while(active_workers>0)
                    worker_id = catch_point(live_point,mpi_information)
                    if(RTI%nlive(1)<nprior) then
                        live_point(settings%h0:settings%h1) = random_reals(settings%nDims)
                        live_point(settings%b0) = ngenerated
                        ngenerated = ngenerated+1
                        call request_live_point(live_point,mpi_information,worker_id)
                    else
                        call no_more_points(mpi_information,worker_id)
                        active_workers=active_workers-1
                    end if
                end do
            else
                do while(live_point_needed(live_point,mpi_information))
                    call calculate_point(loglikelihood,prior,live_point,settings,nlike)
                    ndiscarded=ndiscarded+1
                    call throw_point(live_point,mpi_information)
                end do
            end if
#endif
        end if
#ifdef MPI
        nlike = sum_integers(nlike,mpi_information)
        ndiscarded = sum_integers(ndiscarded,mpi_information)
        total_time = sum_doubles(total_time,mpi_information)
#endif
        if(is_root(mpi_information)) then
            call write_finished_generating(settings%feedback)
        end if
    end subroutine GenerateLivePoints
end module generate_module
"""


def test_patch_module_and_markers_exist():
    module = _load_module()
    patched = module.patch_generate_source(_fixture_source())
    assert "POLYCHORD_BOOTSTRAP_V1" in patched
    assert "POLYCHORD_BOOTSTRAP_SEGMENT_VALID" in patched
    assert "write_bootstrap_checkpoint" in patched
    assert "read_bootstrap_checkpoint" in patched
    assert "bootstrap_target" in patched
    assert "stop 86" in patched


def test_patch_rejects_already_patched_source():
    module = _load_module()
    patched = module.patch_generate_source(_fixture_source())
    try:
        module.patch_generate_source(patched)
    except ValueError as exc:
        assert "already patched" in str(exc)
    else:
        raise AssertionError("second patch application must fail")


def test_apply_patch_writes_file_and_hashes(tmp_path: Path):
    module = _load_module()
    generate = tmp_path / "src" / "polychord" / "generate.F90"
    generate.parent.mkdir(parents=True)
    generate.write_text(_fixture_source(), encoding="utf-8")
    result = module.apply_bootstrap_patch(tmp_path)
    assert result["upstream_sha256"] != result["patched_sha256"]
    assert result["path"] == "src/polychord/generate.F90"
    assert "POLYCHORD_BOOTSTRAP_V1" in generate.read_text(encoding="utf-8")


def test_patch_contains_no_science_specific_prior_mutation():
    module = _load_module()
    patched = module.patch_generate_source(_fixture_source()).lower()
    for forbidden in ("peer_fede", "alens", "tau", "planck", "shoes", "desi"):
        assert forbidden not in patched
