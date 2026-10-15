import unittest
from automations.lean_roles import prepare_migration, ROLE_TEXT, TRANSFERS


def inventory():
    return {"jawbones": [{"id": 'fixture-'+r, "title": 'NEXO '+r.title()+' | Direct', "prompt": 'Existing '+r,
                          "schedule": 'BEGIN:VEVENT\nRRULE:FREQ=HOURLY\nEND:VEVENT', "is_enabled": True}
                         for r in list(ROLE_TEXT)+list(TRANSFERS)]}


class RolesTests(unittest.TestCase):
    def test_preserves_ids_and_never_emits_scheduler_mutations(self):
        x=inventory();result=prepare_migration(x)
        self.assertEqual(result['state'],'PREPARED_NOT_APPLIED');self.assertEqual(len(result['updates']),4)
        self.assertEqual(len(result['responsibility_transfers']),3)
        for row in result['updates']:
            self.assertTrue(row['jawbone_id'].startswith('fixture-'))
            for field in ['schedule','is_enabled','delete','dtstart_offset_json']:
                self.assertNotIn(field,row)
        self.assertFalse(result['schedules_changed']);self.assertFalse(result['automations_disabled'])
    def test_incomplete_inventory_not_treated_as_no_work(self):
        with self.assertRaisesRegex(ValueError,'INCOMPLETE'):prepare_migration({'jawbones':[]})
    def test_duplicate_enabled_role_is_rejected(self):
        x=inventory();x['jawbones'].append(dict(x['jawbones'][0]))
        with self.assertRaisesRegex(ValueError,'AMBIGUOUS'):prepare_migration(x)
    def test_disabled_role_does_not_supply_a_live_identity(self):
        x=inventory();x['jawbones'][0]['is_enabled']=False
        with self.assertRaisesRegex(ValueError,'INCOMPLETE'):prepare_migration(x)
    def test_no_inplace_inventory_changes(self):
        import copy
        x=inventory();before=copy.deepcopy(x);prepare_migration(x);self.assertEqual(x,before)
    def test_accents_are_recognized(self):
        x=inventory()
        for row in x['jawbones']:
            if 'Critico' in row['title']:row['title']='NEXO Cr\u00edtico | Parecer direto'
        self.assertEqual(len(prepare_migration(x)['updates']),4)
    def test_editor_keeps_paper_skill_and_publication_boundary(self):
        p=ROLE_TEXT['EDITOR'];self.assertIn('PREPARING SCIENTIFIC PAPERS',p);self.assertIn('autorizacao do proprietario',p)
    def test_reviewer_independence_not_just_role_name(self):
        self.assertIn('sozinha, nao prova independencia',ROLE_TEXT['CRITICO'])

if __name__=='__main__':unittest.main()
