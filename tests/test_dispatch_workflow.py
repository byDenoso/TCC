from pathlib import Path
import unittest


class DispatchWorkflowTests(unittest.TestCase):
    def test_dispatch_runs_are_not_serialized_by_branch(self):
        workflow = Path('.github/workflows/nexo-dispatch.yml').read_text(encoding='utf-8')
        self.assertNotIn('group: nexo-dispatch-${{ github.ref }}', workflow)


if __name__ == '__main__':
    unittest.main()
