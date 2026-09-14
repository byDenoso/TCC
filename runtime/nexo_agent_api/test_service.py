from __future__ import annotations

import json, tempfile, unittest
from pathlib import Path
from .service import AgentService, TowerAgentIssue
from .views import materialize_role_views

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
        self.write_work("W2",self.eligible()); self.write_work("cold",{"id":"W-COLD","entity_version":1,"status":"READY","owner_role":"ADVISOR"})
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

if __name__=="__main__": unittest.main()
