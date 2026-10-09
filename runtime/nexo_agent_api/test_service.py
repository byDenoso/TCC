from __future__ import annotations

import json, tempfile, unittest
from pathlib import Path
from .service import AgentService, TowerAgentIssue
from .views import materialize_role_views
from .test_state_materialization import StateMaterializationTests

class AgentServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        for rel in ("entities/work","manifests","snapshot"): (self.root/rel).mkdir(parents=True)
        (self.root/"CONTROL.json").write_text(json.dumps({"mode":"ACTIVE","schema_version":"0.6"}))
        (self.root/"snapshot/latest.json").write_text(json.dumps({"event_cursor":"EVT-10"}))
        (self.root/"manifests/capabilities.json").write_text(json.dumps({"capabilities":{"compile_v1":{"roles":["EXECUTOR"],"backend":"github"}}}))
        (self.root/"manifests/artifacts.json").write_text(json.dumps({"artifacts":{"ART-1":{"storage":"drive","ref":"drive:1"}}}))
    def tearDown(self): self.tmp.cleanup()
    def write_work(self,name,payload): (self.root/f"entities/work/{name}.json").write_text(json.dumps(payload))
    def eligible(self,wid="W2"): return {"id":wid,"entity_version":1,"status":"READY","owner_role":"EXECUTOR","dependencies_resolved":True,"binding_verified":True,"task_id":"compile_v1","repository":"byDenoso/TCC","source_revision":"abc","required_outputs":["o"],"validation_ref":"VAL","runtime_available":True,"resource_lock_available":True}

    def test_executor_requires_mechanical_eligibility(self):
        self.write_work("weak",{"id":"W1","entity_version":1,"status":"READY","owner_role":"EXECUTOR"}); self.write_work("ok",self.eligible())
        self.assertEqual([x["id"] for x in AgentService(self.root).queue_for("EXECUTOR")],["W2"])

    def test_cas_mutation_and_stale_rejection(self):
        self.write_work("w1",{"id":"W1","entity_version":1,"status":"READY"})
        r=AgentService(self.root).mutate("work","w1",expected_version=1,changes={"status":"RUNNING"},writer_role="EXECUTOR",event_type="WORK_STARTED")
        self.assertEqual((r["entity_version"],r["readback"]),(2,"PASS")); self.assertEqual(len(list((self.root/"events").rglob("*.json"))),1)
        with self.assertRaises(TowerAgentIssue): AgentService(self.root).mutate("work","w1",expected_version=1,changes={"status":"DONE"},writer_role="EXECUTOR",event_type="WORK_DONE")

    def test_bootstrap_and_artifact_resolution(self):
        self.write_work("w2",self.eligible()); b=AgentService(self.root).bootstrap("EXECUTOR")
        self.assertEqual(b["queue"][0]["id"],"W2"); self.assertIn("compile_v1",b["capabilities"]); self.assertEqual(AgentService(self.root).resolve_artifact("ART-1")["storage"],"drive")

    def test_entity_overrides_stale_active_index(self):
        (self.root/"indexes").mkdir(); (self.root/"indexes/active-work.json").write_text(json.dumps({"work":[{"id":"W2","entity_version":1,"status":"BLOCKED","owner_role":"ADVISOR"}]}))
        p=self.eligible(); p["entity_version"]=4; self.write_work("W2",p)
        q=AgentService(self.root).queue_for("EXECUTOR"); self.assertEqual((q[0]["id"],q[0]["entity_version"]),("W2",4))

    def test_bootstrap_is_single_hot_role_view_and_queue_is_stub(self):
        (self.root/"indexes").mkdir(); (self.root/"indexes/active-work.json").write_text(json.dumps({"work":[{"id":"W2"}]}))
        self.write_work("W2",self.eligible()); self.write_work("cold",{"id":"W-COLD","entity_version":1,"status":"BLOCKED","owner_role":"ADVISOR"})
        r=materialize_role_views(self.root); self.assertEqual(r["view_model"],"SINGLE_ROLE_VIEW")
        executor=json.loads((self.root/"bootstrap/executor.json").read_text()); advisor=json.loads((self.root/"bootstrap/advisor.json").read_text()); stub=json.loads((self.root/"queues/executor.json").read_text())
        self.assertEqual(executor["queue_count"],1); self.assertEqual(advisor["queue_count"],0); self.assertEqual(executor["view_model"],"SINGLE_ROLE_VIEW"); self.assertEqual(stub["count"],0); self.assertEqual(stub["role_view_ref"],"bootstrap/executor.json")

    def test_role_view_caps_advisor_at_five_prioritized_cards(self):
        (self.root/"indexes").mkdir()
        items=[]
        for i in range(7):
            wid=f"A{i}"; priority="CRITICAL" if i==6 else "HIGH"
            item={"id":wid,"entity_version":1,"status":"READY","owner_role":"ADVISOR","kind":"RESEARCH","priority":priority}
            items.append(item); self.write_work(wid,item)
        (self.root/"indexes/active-work.json").write_text(json.dumps({"work":items}))
        materialize_role_views(self.root)
        advisor=json.loads((self.root/"bootstrap/advisor.json").read_text())
        self.assertEqual(advisor["queue_count"],5); self.assertEqual(advisor["queue_limit"],5); self.assertEqual(advisor["queue"][0]["id"],"A6")

    def test_role_view_parks_wait_dependency_behind_actionable_advisor_work(self):
        (self.root/"indexes").mkdir()
        items=[]
        parked={"id":"WAIT-CRITICAL","entity_version":1,"status":"WAIT_DEPENDENCY","kind":"REVIEW","priority":"CRITICAL"}
        items.append(parked); self.write_work("WAIT-CRITICAL",parked)
        for i in range(5):
            wid=f"READY-{i}"
            item={"id":wid,"entity_version":1,"status":"READY","kind":"RESEARCH","priority":"HIGH"}
            items.append(item); self.write_work(wid,item)
        (self.root/"indexes/active-work.json").write_text(json.dumps({"work":items}))

        materialize_role_views(self.root)
        advisor=json.loads((self.root/"bootstrap/advisor.json").read_text())

        self.assertEqual(advisor["queue_count"],5)
        self.assertNotIn("WAIT-CRITICAL", [item["id"] for item in advisor["queue"]])
        self.assertTrue(all(item["status"] == "READY" for item in advisor["queue"]))


    def test_hidden_capability_work_is_discoverable_but_not_automatically_runnable(self):
        capability = {
            "capabilities": {
                "peer.detection.d04_v1": {
                    "roles": ["EXECUTOR"], "status": "ACTIVE",
                    "backend": "chatgpt_runtime", "task_id": "peer_detection_d04",
                }
            }
        }
        (self.root / "manifests/capabilities.json").write_text(json.dumps(capability))
        self.write_work("D04", {
            "id": "PEER-DETECTION-D04", "status": "READY",
            "owner_role": "EXECUTOR", "priority": "HIGH",
            "capability_id": "peer.detection.d04_v1",
            "blocker": "Exact matched profile grid missing",
        })
        service = AgentService(self.root)
        self.assertEqual(service.queue_for("EXECUTOR"), [])
        discovery = service.bootstrap("EXECUTOR")["discovery"]
        self.assertEqual(discovery["omitted_executor_work_count"], 1)
        self.assertEqual(discovery["omitted_executor_work"][0]["id"], "PEER-DETECTION-D04")
        self.assertEqual(discovery["omitted_executor_work"][0]["visibility_status"],
                         "DISCOVERY_ONLY_NOT_EXECUTABLE")
        self.assertEqual(discovery["omitted_executor_work"][0]["first_gap"],
                         "CAPABILITY_DECLARED_BUT_WORK_BINDING_INCOMPLETE")

    def test_recipe_recovery_discovers_only_existing_active_roadmap_tests(self):
        for name, status in (("RM-H0-ACTIVE", "ACTIVE"), ("RM-DE-CLOSED", "CLOSED")):
            path = self.root / "roadmaps" / (name + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"state": status}))
        for test_id, roadmap in (("H0-BRIDGE", "RM-H0-ACTIVE"),
                                 ("DDE-CLOSED", "RM-DE-CLOSED")):
            path = self.root / "entities/test" / (test_id + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "id": test_id, "state": "BLOCKED_INPUT",
                "roadmap_id": roadmap, "data_binding": {"status": "BOUND"},
                "readiness": {"eligible": False, "reasons": ["RECIPE_BINDING_MISSING"]},
            }))
        service = AgentService(self.root)
        discovery = service.bootstrap("EXECUTOR")["discovery"]
        self.assertEqual(discovery["active_recipe_blocked_test_count"], 1)
        self.assertEqual(discovery["active_recipe_blocked_tests"][0]["test_id"], "H0-BRIDGE")
        self.assertEqual(discovery["active_recipe_blocked_tests"][0]["data_binding_status"], "BOUND")
        self.assertEqual(service.queue_for("EXECUTOR"), [])

    def test_all_forty_blocked_tests_are_visible_without_fabricating_readiness(self):
        roadmap = self.root / "roadmaps" / "RM-ACTIVE.json"
        roadmap.parent.mkdir(parents=True, exist_ok=True)
        roadmap.write_text(json.dumps({"state": "ACTIVE"}))
        for index in range(40):
            test_id = f"SYNTH-BLOCKED-{index:02d}"
            reasons = (["RECIPE_BINDING_MISSING"] if index < 36
                       else ["INPUT_PROVENANCE_INCOMPLETE"])
            binding = {"status": "BOUND" if index < 5 else "PARTIAL"}
            path = self.root / "entities" / "test" / (test_id + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "id": test_id, "state": "BLOCKED_INPUT",
                "roadmap_id": "RM-ACTIVE", "data_binding": binding,
                "readiness": {"eligible": False, "reasons": reasons},
            }))
        service = AgentService(self.root)
        self.assertEqual(service.queue_for("EXECUTOR"), [])
        view = service.bootstrap("EXECUTOR")["discovery"]
        self.assertEqual(view["active_input_blocked_test_count"], 40)
        self.assertEqual(view["active_recipe_blocked_test_count"], 36)
        self.assertEqual(view["active_data_bound_recipe_blocked_count"], 5)
        self.assertEqual(len({t["test_id"] for t in view["active_input_blocked_tests"]}), 40)
        self.assertEqual(sum(not t["recipe_missing"] for t in view["active_input_blocked_tests"]), 4)
        self.assertTrue(all(t["visibility_status"] == "RECOVERY_DISCOVERY_ONLY"
                            for t in view["active_input_blocked_tests"]))

    def test_closed_roadmap_with_stale_active_state_does_not_reopen_tests(self):
        root = self.root / "roadmaps"
        root.mkdir(parents=True, exist_ok=True)
        (root / "RM-CLOSED.json").write_text(json.dumps({
            "status": "CLOSED", "state": "ACTIVE",
        }))
        (root / "RM-ACTIVE.json").write_text(json.dumps({
            "status": "ACTIVE", "state": "ACTIVE",
        }))
        for test_id, roadmap_id in (("CLOSED-TEST", "RM-CLOSED"),
                                    ("OPEN-TEST", "RM-ACTIVE")):
            folder = self.root / "entities" / "test"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (test_id + ".json")).write_text(json.dumps({
                "id": test_id, "status": "BLOCKED_INPUT",
                "roadmap_id": roadmap_id,
                "data_binding": {"status": "BOUND"},
                "readiness": {"eligible": False, "reasons": ["RECIPE_BINDING_MISSING"]},
            }))
        result = AgentService(self.root).bootstrap("EXECUTOR")["discovery"]
        self.assertEqual(result["active_input_blocked_test_count"], 1)
        self.assertEqual(result["active_recipe_blocked_test_count"], 1)
        self.assertEqual(result["active_input_blocked_tests"][0]["test_id"], "OPEN-TEST")
        self.assertEqual(result["roadmap_state_conflict_count"], 1)
        self.assertEqual(result["roadmap_state_conflicts"][0]["roadmap_id"], "RM-CLOSED")
        self.assertEqual(result["roadmap_state_conflicts"][0]["effective_status"], "CLOSED")

    def test_five_card_queue_reveals_full_runnable_count(self):
        for i in range(7):
            self.write_work(f"ID{i}", self.eligible(f"ID{i}"))
        materialize_role_views(self.root)
        view = json.loads((self.root / "bootstrap/executor.json").read_text())
        self.assertEqual(view["queue_count"], 5)
        self.assertEqual(view["queue_total_count"], 7)
        self.assertTrue(view["queue_has_more"])
        self.assertEqual(view["queue_scope"],
                         "TOP_CARDS_ONLY_DISCOVERY_NOT_EXECUTION_AUTHORIZATION")


if __name__=="__main__": unittest.main()
