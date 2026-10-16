"""Regression tests against the deployed Writer's local lock; no remote calls."""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime.nexo_agent_api import drive_transport as dt

class LockAudit(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.home=Path(self.temp.name)
        self.patcher=patch.object(dt,'nexo_home',return_value=self.home); self.patcher.start()
    def tearDown(self):
        self.patcher.stop(); self.temp.cleanup()
    def test_nested_lock_rejected(self):
        with dt.writer_lock():
            with self.assertRaises(dt.TowerConflict):
                with dt.writer_lock(): pass
    def test_age_never_steals_active_lock(self):
        with dt.writer_lock() as path:
            old=time.time()-20000; os.utime(path,(old,old))
            with self.assertRaises(dt.TowerConflict):
                with dt.writer_lock(stale_after=1): pass
    def test_exception_releases(self):
        with self.assertRaises(RuntimeError):
            with dt.writer_lock(): raise RuntimeError('injected failure')
        with dt.writer_lock(): pass
    def test_repeated_acquisition(self):
        for _ in range(4):
            with dt.writer_lock(): pass
    def child(self, body):
        setup='from pathlib import Path\nfrom runtime.nexo_agent_api import drive_transport as dt\ndt.nexo_home=lambda:Path('+repr(str(self.home))+')\n'
        return subprocess.run([sys.executable,'-c',setup+body],text=True,capture_output=True,timeout=15)
    def test_process_contention(self):
        with dt.writer_lock():
            result=self.child('try:\n with dt.writer_lock(): pass\nexcept dt.TowerConflict:\n print("BUSY")\n')
            self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(result.stdout.strip(),'BUSY')
    def test_crashed_process_recovers(self):
        result=self.child('import os\nwith dt.writer_lock():\n os._exit(0)\n')
        self.assertEqual(result.returncode,0,result.stderr)
        with dt.writer_lock(): pass
if __name__=='__main__': unittest.main()
