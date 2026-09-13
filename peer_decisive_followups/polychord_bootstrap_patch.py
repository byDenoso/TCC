from __future__ import annotations

import hashlib
from pathlib import Path

MARKER = "POLYCHORD_BOOTSTRAP_V1"
RNG_MARKER = "POLYCHORD_BOOTSTRAP_RNG_V1"
ENV_NAME = "POLYCHORD_BOOTSTRAP_SEGMENT_VALID"
GENERATE_PATH = Path("src/polychord/generate.F90")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"upstream anchor {label!r} expected once, found {count}")
    return source.replace(old, new, 1)


def _replace_first(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count < 1:
        raise ValueError(f"upstream anchor {label!r} not found")
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

    subroutine bootstrap_rng_filename(settings, rank, filename)
        use settings_module, only: program_settings
        implicit none
        type(program_settings), intent(in) :: settings
        integer, intent(in) :: rank
        character(len=*), intent(out) :: filename
        character(len=32) :: rank_string
        write(rank_string,'(I0)') rank
        filename = trim(settings%base_dir)//'/'//trim(settings%file_root)//'.bootstrap.rng.'//trim(rank_string)
    end subroutine bootstrap_rng_filename

    subroutine write_bootstrap_rng(settings, rank)
        use settings_module, only: program_settings
        implicit none
        type(program_settings), intent(in) :: settings
        integer, intent(in) :: rank
        integer :: unit,nseed
        integer, allocatable :: seed(:)
        character(len=1024) :: filename,tmpname
        call random_seed(size=nseed)
        allocate(seed(nseed))
        call random_seed(get=seed)
        call bootstrap_rng_filename(settings,rank,filename)
        tmpname = trim(filename)//'.tmp'
        open(newunit=unit,file=trim(tmpname),status='replace',action='write',form='formatted')
        write(unit,'(A)') 'POLYCHORD_BOOTSTRAP_RNG_V1'
        write(unit,*) rank,nseed
        write(unit,*) seed
        flush(unit)
        close(unit)
        deallocate(seed)
        call execute_command_line('mv -f "'//trim(tmpname)//'" "'//trim(filename)//'"',wait=.true.)
    end subroutine write_bootstrap_rng

    subroutine read_bootstrap_rng(settings, rank, loaded)
        use settings_module, only: program_settings
        implicit none
        type(program_settings), intent(in) :: settings
        integer, intent(in) :: rank
        logical, intent(out) :: loaded
        integer :: unit,ios,nseed,stored_rank,expected_nseed
        integer, allocatable :: seed(:)
        character(len=1024) :: filename
        character(len=64) :: magic
        logical :: exists
        call bootstrap_rng_filename(settings,rank,filename)
        inquire(file=trim(filename),exist=exists)
        loaded = .false.
        if(.not.exists) return
        open(newunit=unit,file=trim(filename),status='old',action='read',form='formatted')
        read(unit,'(A)',iostat=ios) magic
        if(ios /= 0 .or. trim(magic) /= 'POLYCHORD_BOOTSTRAP_RNG_V1') stop 87
        read(unit,*,iostat=ios) stored_rank,nseed
        call random_seed(size=expected_nseed)
        if(ios /= 0 .or. stored_rank /= rank .or. nseed /= expected_nseed) stop 87
        allocate(seed(nseed))
        read(unit,*,iostat=ios) seed
        if(ios /= 0) stop 87
        close(unit)
        call random_seed(put=seed)
        deallocate(seed)
        loaded = .true.
    end subroutine read_bootstrap_rng

    subroutine delete_bootstrap_rng(settings, rank)
        use settings_module, only: program_settings
        implicit none
        type(program_settings), intent(in) :: settings
        integer, intent(in) :: rank
        integer :: unit
        character(len=1024) :: filename
        logical :: exists
        call bootstrap_rng_filename(settings,rank,filename)
        inquire(file=trim(filename),exist=exists)
        if(exists) then
            open(newunit=unit,file=trim(filename),status='old')
            close(unit,status='delete')
        end if
    end subroutine delete_bootstrap_rng

    subroutine write_bootstrap_checkpoint(settings,RTI,nlike,ndiscarded,total_time)
        use settings_module, only: program_settings
        use run_time_module, only: run_time_info
        implicit none
        type(program_settings), intent(in) :: settings
        type(run_time_info), intent(in) :: RTI
        integer, intent(in) :: nlike,ndiscarded
        real(dp), intent(in) :: total_time
        integer :: unit,j
        character(len=1024) :: filename,tmpname
        call bootstrap_filename(settings,filename)
        tmpname = trim(filename)//'.tmp'
        open(newunit=unit,file=trim(tmpname),status='replace',action='write',form='formatted')
        write(unit,'(A)') 'POLYCHORD_BOOTSTRAP_V1'
        write(unit,*) settings%nDims,settings%nDerived,settings%nlive,settings%nprior
        write(unit,*) RTI%nlive(1),ndiscarded,nlike,total_time
        do j=1,RTI%nlive(1)
            write(unit,'(*(ES26.17E3,1X))') RTI%live(:,j,1)
        end do
        flush(unit)
        close(unit)
        call execute_command_line('mv -f "'//trim(tmpname)//'" "'//trim(filename)//'"',wait=.true.)
    end subroutine write_bootstrap_checkpoint

    subroutine read_bootstrap_checkpoint(settings,RTI,prev_nlike,prev_ndiscarded,prev_total_time,loaded)
        use settings_module, only: program_settings
        use run_time_module, only: run_time_info
        use array_module, only: add_point
        implicit none
        type(program_settings), intent(in) :: settings
        type(run_time_info), intent(inout) :: RTI
        integer, intent(out) :: prev_nlike,prev_ndiscarded
        real(dp), intent(out) :: prev_total_time
        logical, intent(out) :: loaded
        integer :: unit,j,ios,fdims,fderived,fnlive,fnprior,nvalid
        character(len=1024) :: filename
        character(len=64) :: magic
        logical :: exists
        real(dp), dimension(settings%nTotal) :: point
        prev_nlike=0
        prev_ndiscarded=0
        prev_total_time=0
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
        read(unit,*,iostat=ios) nvalid,prev_ndiscarded,prev_nlike,prev_total_time
        if(ios /= 0 .or. nvalid < 0 .or. prev_ndiscarded < nvalid .or. prev_nlike < nvalid) stop 87
        do j=1,nvalid
            read(unit,*,iostat=ios) point
            if(ios /= 0) stop 87
            call add_point(point,RTI%live,RTI%nlive,1)
        end do
        close(unit)
        if(RTI%nlive(1) /= nvalid) stop 87
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

'''


def patch_generate_source(source: str) -> str:
    if MARKER in source:
        raise ValueError("PolyChord generate.F90 is already patched")
    if "subroutine GenerateLivePoints" not in source:
        raise ValueError("unsupported PolyChord source: GenerateLivePoints not found")

    insertion = "    !> Generate an initial set of live points distributed uniformly in the unit hypercube in parallel\n"
    source = _replace_once(source, insertion, _HELPERS + insertion, "helper insertion")

    mpi_old = (
        "        use mpi_module, only: mpi_bundle,is_root,linear_mode,throw_point,catch_point,"
        "more_points_needed,sum_integers,sum_doubles,request_point,no_more_points\n"
    )
    mpi_new = (
        "        use mpi_module, only: mpi_bundle,is_root,linear_mode,throw_point,catch_point,"
        "more_points_needed,sum_integers,sum_doubles,request_point,no_more_points,"
        "broadcast_integers,broadcast_doubles,mpi_synchronise\n"
    )
    source = _replace_first(source, mpi_old, mpi_new, "GenerateLivePoints MPI imports")

    decl_old = "        integer :: nprior, ndiscarded\n"
    decl_new = decl_old + (
        "        integer :: bootstrap_segment_valid,bootstrap_target\n"
        "        integer :: bootstrap_state_flag(1),bootstrap_target_sync(1),bootstrap_prev_int(2)\n"
        "        integer :: bootstrap_rng_flag,bootstrap_rng_count,j\n"
        "        real(dp) :: bootstrap_prev_time(1)\n"
        "        logical :: bootstrap_loaded,bootstrap_rng_loaded\n"
    )
    source = _replace_once(source, decl_old, decl_new, "bootstrap declarations")

    init_old = "        ndiscarded=0\n\n        total_time=0\n"
    init_new = """        ndiscarded=0

        total_time=0
        bootstrap_loaded=.false.
        bootstrap_rng_loaded=.false.
        bootstrap_segment_valid=0
        bootstrap_target=nprior
        bootstrap_state_flag=0
        bootstrap_target_sync=nprior
        bootstrap_prev_int=0
        bootstrap_prev_time=0
        call get_bootstrap_segment_valid(bootstrap_segment_valid)
        if(is_root(mpi_information)) then
            call read_bootstrap_checkpoint(settings,RTI,bootstrap_prev_int(1),bootstrap_prev_int(2), &
                                           bootstrap_prev_time(1),bootstrap_loaded)
            if(bootstrap_loaded) then
                bootstrap_state_flag(1)=1
                if(settings%write_live) then
                    do j=1,RTI%nlive(1)
                        write(write_phys_unit,fmt_dbl) RTI%live(settings%p0:settings%d1,j,1),RTI%live(settings%l0,j,1)
                    end do
                    flush(write_phys_unit)
                end if
            end if
            if(bootstrap_segment_valid>0) bootstrap_target=min(nprior,RTI%nlive(1)+bootstrap_segment_valid)
            bootstrap_target_sync(1)=bootstrap_target
        end if
#ifdef MPI
        call broadcast_integers(bootstrap_state_flag,mpi_information)
        call broadcast_integers(bootstrap_target_sync,mpi_information)
        call broadcast_integers(bootstrap_prev_int,mpi_information)
        call broadcast_doubles(bootstrap_prev_time,mpi_information)
        bootstrap_target=bootstrap_target_sync(1)
        call read_bootstrap_rng(settings,mpi_information%rank,bootstrap_rng_loaded)
        bootstrap_rng_flag=0
        if(bootstrap_rng_loaded) bootstrap_rng_flag=1
        bootstrap_rng_count=sum_integers(bootstrap_rng_flag,mpi_information)
        if(bootstrap_state_flag(1)==1 .and. bootstrap_rng_count/=mpi_information%nprocs) stop 87
        if(bootstrap_state_flag(1)==0 .and. bootstrap_rng_count/=0) stop 87
#else
        call read_bootstrap_rng(settings,0,bootstrap_rng_loaded)
        if(bootstrap_loaded .neqv. bootstrap_rng_loaded) stop 87
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

    reduction_anchor = """#ifdef MPI
        nlike = sum_integers(nlike,mpi_information) ! Gather the likelihood calls onto one node
        ndiscarded = sum_integers(ndiscarded,mpi_information) ! Gather the likelihood calls onto one node
        total_time = sum_doubles(total_time,mpi_information) ! Sum up the total time taken
#endif
"""
    reduction_new = reduction_anchor + """
        nlike=nlike+bootstrap_prev_int(1)
        ndiscarded=ndiscarded+bootstrap_prev_int(2)
        total_time=total_time+bootstrap_prev_time(1)

        if(bootstrap_target<nprior) then
#ifdef MPI
            call write_bootstrap_rng(settings,mpi_information%rank)
            call mpi_synchronise(mpi_information)
#else
            call write_bootstrap_rng(settings,0)
#endif
            if(is_root(mpi_information)) then
                if(settings%write_live) close(write_phys_unit)
                call write_bootstrap_checkpoint(settings,RTI,nlike,ndiscarded,total_time)
            end if
#ifdef MPI
            call mpi_synchronise(mpi_information)
#endif
            stop 86
        end if
        if(is_root(mpi_information)) call delete_bootstrap_checkpoint(settings)
#ifdef MPI
        call delete_bootstrap_rng(settings,mpi_information%rank)
        call mpi_synchronise(mpi_information)
#else
        call delete_bootstrap_rng(settings,0)
#endif
"""
    source = _replace_once(source, reduction_anchor, reduction_new, "partial checkpoint exit")
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
