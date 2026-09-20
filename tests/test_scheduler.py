import unittest

from nexo_control_plane.models import Backend, WorkDomain, WorkRecord, WorkStatus
from nexo_control_plane.scheduler import CapacityProfile, SchedulerSnapshot, eligible_dispatches


def work(
    work_id,
    domain=WorkDomain.SCIENCE,
    lane="L1",
    priority="MEDIUM",
    speculative=False,
    status=WorkStatus.READY,
    resources=(),
):
    backend = Backend.GITHUB_ENGINEERING if domain == WorkDomain.ENGINEERING else Backend.GITHUB_SCIENCE
    return WorkRecord(
        work_id=work_id,
        thread_id=f"THR::{domain.value}::ROOT",
        domain=domain,
        status=status,
        execution_backend=backend,
        runtime_requirement="CODE" if domain == WorkDomain.ENGINEERING else "HEAVY",
        lane_id=lane,
        priority=priority,
        speculative=speculative,
        resource_keys=tuple(resources),
    )


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.profile = CapacityProfile()

    def test_global_hard_limit_is_eight_when_burst_is_needed(self):
        ready = [work("CRIT", lane="LC", priority="CRITICAL")] + [work(f"S{i}", lane=f"L{i}") for i in range(20)]
        out = eligible_dispatches(ready, [], SchedulerSnapshot(), self.profile)
        self.assertEqual(len(out), 8)

    def test_burst_slot_stays_free_without_critical_work(self):
        ready = [work(f"S{i}", lane=f"L{i}") for i in range(20)]
        out = eligible_dispatches(ready, [], SchedulerSnapshot(), self.profile)
        self.assertEqual(len(out), 7)

    def test_per_lane_limit_is_three_including_active(self):
        active = [work("A1", lane="L1", status=WorkStatus.RUNNING), work("A2", lane="L1", status=WorkStatus.RUNNING)]
        ready = [work("R1", lane="L1"), work("R2", lane="L1"), work("R3", lane="L1"), work("R4", lane="L2")]
        out = eligible_dispatches(ready, active, SchedulerSnapshot(), self.profile)
        self.assertEqual(sum(x.lane_id == "L1" for x in out), 1)
        self.assertIn("R4", {x.work_id for x in out})

    def test_speculative_limit_is_two(self):
        ready = [work(f"SP{i}", lane=f"L{i}", speculative=True) for i in range(6)]
        out = eligible_dispatches(ready, [], SchedulerSnapshot(), self.profile)
        self.assertEqual(len(out), 2)

    def test_verification_pressure_stops_speculative_dispatch(self):
        ready = [work("SP1", speculative=True), work("M1", speculative=False, lane="L2")]
        out = eligible_dispatches(
            ready,
            [],
            SchedulerSnapshot(verification_backlog=8),
            self.profile,
        )
        self.assertEqual([x.work_id for x in out], ["M1"])

    def test_ready_queue_pressure_stops_speculative_dispatch(self):
        ready = [work(f"M{i}", lane=f"L{i}") for i in range(21)] + [work("SP", lane="LS", speculative=True)]
        out = eligible_dispatches(
            ready,
            [],
            SchedulerSnapshot(ready_queue_count=22),
            self.profile,
        )
        self.assertNotIn("SP", {x.work_id for x in out})

    def test_engineering_blocker_gets_last_available_slot(self):
        active = [work(f"A{i}", lane=f"AS{i}", status=WorkStatus.RUNNING) for i in range(7)]
        ready = [
            work("SCI-CRIT", lane="SCI", priority="CRITICAL"),
            work("ENG-BLOCK", domain=WorkDomain.ENGINEERING, lane="ENG", priority="CRITICAL"),
        ]
        out = eligible_dispatches(ready, active, SchedulerSnapshot(engineering_backlog=1), self.profile)
        self.assertEqual([x.work_id for x in out], ["ENG-BLOCK"])


    def test_domain_targets_are_reserved_when_both_backlogs_exist(self):
        ready = (
            [work(f"AAA-SCI-{i}", lane=f"S{i}", priority="CRITICAL") for i in range(8)]
            + [work(f"ZZZ-ENG-{i}", domain=WorkDomain.ENGINEERING, lane=f"E{i}", priority="MEDIUM") for i in range(2)]
        )
        out = eligible_dispatches(
            ready,
            [],
            SchedulerSnapshot(engineering_backlog=2),
            self.profile,
        )
        self.assertEqual(sum(x.domain == WorkDomain.ENGINEERING for x in out), 2)
        self.assertGreaterEqual(sum(x.domain == WorkDomain.SCIENCE for x in out), 4)

    def test_verification_backlog_reserves_one_global_slot(self):
        active = [work(f"A{i}", lane=f"L{i}", status=WorkStatus.RUNNING) for i in range(7)]
        ready = [work("R", lane="LR")]
        out = eligible_dispatches(ready, active, SchedulerSnapshot(verification_backlog=1), self.profile)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
