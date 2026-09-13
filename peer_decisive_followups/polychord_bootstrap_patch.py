from __future__ import annotations

import hashlib
from pathlib import Path

MARKER = "POLYCHORD_BOOTSTRAP_V1"
ENV_NAME = "POLYCHORD_BOOTSTRAP_SEGMENT_VALID"
GENERATE_PATH = Path("src/polychord/generate.F90")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"upstream anchor {label!r} expected once, found {count}")
    return source.replace(old, new, 1)


_HELPERS = r'''
    subroutine get_bootstrap_segment_valid(segment_valid)
        implicit none
        integer, intent(out) :: segment_valid
        character(len=64) :: value
        integer :: length, status, ios
        segment_valid = 0
        value = ''
        call get_environment_variable('POLYCHORD_BOOTSTRAP_SEGMENT_VALID', value, length=length, status=status)
        if(status == 0 .and. length > 0) then
            read(value(:length),*,iostat=ios) segment_valid
            if(ios /= 0 .or. segment_valid < 0) stop 87
        end if
    end subroutine get_bootstrap_segment_valid

    subroutine bootstrap_filename(settings, filename)
        use settings_module, only: program_settings
        implicit none
        type(program_settings), intent(in) :: settings
        character(len=*), intent(out) :: filename
        filename = trim(settings%base_dir)//'/'//trim(settings%file_root)//'.bootstrap'
    end subroutine bootstrap_filename

    subroutine write_bootstrap_checkpoint(settings,RTI,nlike,ndiscarded,ngenerated,total_time)
        use settings_module, only: program_settings
        use run_time_module, only: run_time_info
        implicit none
        type(program_settings), intent(in) :: settings
        type(run_time_info), intent(in) :: RTI
        integer, intent(in) :: nlike,ndiscarded,ngenerated
        real(dp), intent(in) :: total_time
        integer :: unit,j
        character(len=1024) :: filename,tmpname
        call bootstrap_filename(settings,filename)
        tmpname = trim(filename)//'.tmp'
        open(newunit=unit,file=trim(tmpname),status='replace',action='write',form='formatted')
        write(unit,'(A)') 'POLYCHORD_BOOTSTRAP_V1'
        write(unit,*) settings%nDims,settings%nDerived,settings%nlive,settings%nprior
        write(unit,*) RTI%nlive(1),ndiscarded,ngenerated,nlike,total_time
        do j=1,RTI%nlive(1)
            write(unit,'(*(ES26.17E3,1X))') RTI%live(:,j,1)
        end do
        flush(unit)
        close(unit)
        call execute_command_line('mv -f "'//trim(tmpname)//'" "'//trim(filename)//'"',wait=.true.)
    end subroutine write_bootstrap_checkpoint

    subroutine read_bootstrap_checkpoint(settings,RTI,nlike,ndiscarded,ngenerated,total_time,loaded)
        use settings_module, only: program_settings
        use run_time_module, only: run_time_info
        use array_module, only: add_point
        implicit none
        type(program_settings), intent(in) :: settings
        type(run_time_info), intent(inout) :: RTI
        integer, intent(inout) :: nlike,ndiscarded,ngenerated
        real(dp), intent(inout) :: total_time
        logical, intent(out) :: loaded
        integer :: unit,j,ios,fdims,fderived,fnlive,fnprior,nvalid
        character(len=1024) :: filename
        character(len=64) :: magic
        logical :: exists
        real(dp), dimension(settings%nTotal) :: point
        call bootstrap_filename(settings,filename)
        inquire(file=trim(filename),exist=exists)
        loaded = .false.
        if(.not.exists) return
        open(newunit=unit,file=trim(filename),status='old',action='read',form='formatted')
        read(unit,'(A)',iostat=ios) magic
        if(ios /= 0 .or. trim(magic) /= 'POLYCHORD_BOOTSTRAP_V1') stop 87
        read(unit,*,iostat=ios) fdims,fderived,fnlive,fnprior
        if(ios /= 0) stop 87
        if(fdims /= settings%nDims .or. fderived /= settings%nDerived .or. &
           fnlive /= settings%nlive .or. fnprior /= settings%nprior) stop 87
        read(unit,*,iostat=ios) nvalid,ndiscarded,ngenerated,nlike,total_time
        if(ios /= 0 .or. nvalid < 0 .or. ndiscarded < nvalid .or. ngenerated /= ndiscarded+1) stop 87
        do j=1,nvalid
            read(unit,*,iostat=ios) point
            if(ios /= 0) stop 87
            call add_point(point,RTI%live,RTI%nlive,1)
        end do
        close(unit)
        if(RTI%nlive(1) /= nvalid .or. nlike /= nvalid) stop 87
        loaded = .true.
    end subroutine read_bootstrap_checkpoint

    subroutine delete_bootstrap_checkpoint(settings)
        use settings_module, only: program_settings
        implicit none
        type(program_settings), intent(in) :: settings
        character(len=1024) :: filename
        integer :: unit
        logical :: exists
        call bootstrap_filename(settings,filename)
        inquire(file=trim(filename),exist=exists)
        if(exists) then
            open(newunit=unit,file=trim(filename),status='old')
            close(unit,status='delete')
        end if
    end subroutine delete_bootstrap_checkpoint

    subroutine fast_forward_bootstrap_rng(settings,ndiscarded)
        use settings_module, only: program_settings
        use random_module, only: random_reals
        implicit none
        type(program_settings), intent(in) :: settings
        integer, intent(in) :: ndiscarded
        integer :: j
        real(dp), dimension(settings%nDims) :: throwaway
        do j=1,ndiscarded
            throwaway = random_reals(settings%nDims)
        end do
    end subroutine fast_forward_bootstrap_rng

'''


def patch_generate_source(source: str) -> str:
    if MARKER in source:
        raise ValueError("PolyChord generate.F90 is already patched")
    if "subroutine GenerateLivePoints" not in source:
        raise ValueError("unsupported PolyChord source: GenerateLivePoints not found")

    insertion = "    !> Generate an initial set of live points distributed uniformly in the unit hypercube in parallel\n"
    source = _replace_once(source, insertion, _HELPERS + insertion, "helper insertion")

    mpi_old = "        use mpi_module, only: mpi_bundle,is_root,linear_mode,throw_point,catch_point,sum_integers,sum_doubles,no_more_points,request_live_point,live_point_needed\n"
    if mpi_old in source:
        mpi_new = "        use mpi_module, only: mpi_bundle,is_root,linear_mode,throw_point,catch_point,sum_integers,sum_doubles,no_more_points,request_live_point,live_point_needed,broadcast_integers,mpi_synchronise\n"
        source = _replace_once(source, mpi_old, mpi_new, "MPI imports")

    decl_old = "        integer :: ngenerated ! use to track order points are generated in\n"
    decl_new = decl_old + "        integer :: bootstrap_segment_valid,bootstrap_target,bootstrap_sync(1)\n        logical :: bootstrap_loaded\n"
    source = _replace_once(source, decl_old, decl_new, "bootstrap declarations")

    init_old = "        ndiscarded=0\n\n        total_time=0\n"
    init_new = """        ndiscarded=0
        total_time=0
        bootstrap_loaded=.false.
        bootstrap_segment_valid=0
        bootstrap_target=nprior
        call get_bootstrap_segment_valid(bootstrap_segment_valid)
        if(is_root(mpi_information)) then
            call read_bootstrap_checkpoint(settings,RTI,nlike,ndiscarded,ngenerated,total_time,bootstrap_loaded)
            if(bootstrap_loaded) call fast_forward_bootstrap_rng(settings,ndiscarded)
            if(bootstrap_segment_valid>0) bootstrap_target=min(nprior,RTI%nlive(1)+bootstrap_segment_valid)
        end if
#ifdef MPI
        bootstrap_sync=0
        if(is_root(mpi_information)) bootstrap_sync(1)=bootstrap_target
        call broadcast_integers(bootstrap_sync,mpi_information)
        bootstrap_target=bootstrap_sync(1)
#endif
"""
    source = _replace_once(source, init_old, init_new, "bootstrap initialization")

    source = _replace_once(
        source,
        "            do while(RTI%nlive(1)<nprior)\n",
        "            do while(RTI%nlive(1)<bootstrap_target)\n",
        "linear generation target",
    )
    source = _replace_once(
        source,
        "                    if(RTI%nlive(1)<nprior) then\n",
        "                    if(RTI%nlive(1)<bootstrap_target) then\n",
        "MPI generation target",
    )

    sort_old = """                ! sort live points by order the prior samples were generated in
                RTI%live(:,:RTI%nlive(1),:) = RTI%live(:,sort_doubles(RTI%live(settings%b0,:RTI%nlive(1),1)),:)
                ! restore birth contour to logzero
                RTI%live(settings%b0,:RTI%nlive(1),:) = settings%logzero
"""
    if sort_old in source:
        sort_new = """                if(bootstrap_target>=nprior) then
                    ! sort live points by order the prior samples were generated in
                    RTI%live(:,:RTI%nlive(1),:) = RTI%live(:,sort_doubles(RTI%live(settings%b0,:RTI%nlive(1),1)),:)
                    ! restore birth contour to logzero
                    RTI%live(settings%b0,:RTI%nlive(1),:) = settings%logzero
                end if
"""
        source = _replace_once(source, sort_old, sort_new, "partial-sort guard")

    reduction_anchor = """#ifdef MPI
        nlike = sum_integers(nlike,mpi_information) ! Gather the likelihood calls onto one node
        ndiscarded = sum_integers(ndiscarded,mpi_information) ! Gather the likelihood calls onto one node
        total_time = sum_doubles(total_time,mpi_information) ! Sum up the total time taken
#endif
"""
    if reduction_anchor in source:
        partial = reduction_anchor + """
        if(bootstrap_target<nprior) then
            if(is_root(mpi_information)) then
                if(settings%write_live) close(write_phys_unit)
                call write_bootstrap_checkpoint(settings,RTI,nlike,ndiscarded,ngenerated,total_time)
            end if
#ifdef MPI
            call mpi_synchronise(mpi_information)
#endif
            stop 86
        end if
        if(is_root(mpi_information)) call delete_bootstrap_checkpoint(settings)
"""
        source = _replace_once(source, reduction_anchor, partial, "partial checkpoint exit")
    else:
        # Minimal fixtures do not carry the exact upstream comments; inject before normal finish.
        anchor = "        if(is_root(mpi_information)) then\n            call write_finished_generating(settings%feedback)"
        if anchor in source:
            partial = """        if(bootstrap_target<nprior) then
            if(is_root(mpi_information)) call write_bootstrap_checkpoint(settings,RTI,nlike,ndiscarded,ngenerated,total_time)
            stop 86
        end if
        if(is_root(mpi_information)) call delete_bootstrap_checkpoint(settings)

""" + anchor
            source = _replace_once(source, anchor, partial, "fixture partial checkpoint exit")

    return source


def apply_bootstrap_patch(source_root: Path) -> dict[str, str]:
    source_root = Path(source_root)
    path = source_root / GENERATE_PATH
    if not path.is_file():
        raise FileNotFoundError(path)
    original = path.read_bytes()
    patched_text = patch_generate_source(original.decode("utf-8"))
    patched = patched_text.encode("utf-8")
    path.write_bytes(patched)
    return {
        "path": GENERATE_PATH.as_posix(),
        "upstream_sha256": _sha256_bytes(original),
        "patched_sha256": _sha256_bytes(patched),
    }
