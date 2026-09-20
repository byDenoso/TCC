from pathlib import Path
import unittest


class DispatchWorkflowTests(unittest.TestCase):
    def workflow(self) -> str:
        return Path('.github/workflows/nexo-dispatch.yml').read_text(encoding='utf-8')

    def test_dispatch_runs_are_not_serialized_by_branch(self):
        self.assertNotIn('group: nexo-dispatch-${{ github.ref }}', self.workflow())

    def test_output_identity_is_validated_before_path_construction(self):
        workflow = self.workflow()
        self.assertIn('validated = load_dispatch_request(request)', workflow)
        self.assertIn("output = Path('nexo_dispatch/results') / f'{validated.work_id}-attempt-{validated.attempt}.json'", workflow)
        self.assertNotIn("work_id = data.get('work_id', 'invalid')", workflow)


if __name__ == '__main__':
    unittest.main()
