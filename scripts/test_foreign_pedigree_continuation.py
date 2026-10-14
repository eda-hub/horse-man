import json,shutil,tempfile,unittest
from pathlib import Path
from check_foreign_pedigree_review import BASE,check,parse_jbis

class ForeignContinuationTests(unittest.TestCase):
    def test_incomplete_primary_pedigree_rejected(self):
        with self.assertRaises(AssertionError):parse_jbis(b'<div class="data-3__items"></div>')

    def test_mutated_alias_identity_scope_and_primary_subject_rejected(self):
        if not (BASE/'batch-12.json').exists():self.skipTest('continuation data absent')
        for scenario in ['alias','duplicate','subject','count']:
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);ped=root/'data/pedigree';rec=ped/'reconciliations';rec.mkdir(parents=True)
                (ped/'horses').symlink_to(Path('data/pedigree/horses').resolve(),target_is_directory=True)
                (rec/'2026-10-09-followup').symlink_to(Path('data/pedigree/reconciliations/2026-10-09-followup').resolve(),target_is_directory=True)
                directory=root/BASE;shutil.copytree(BASE,directory)
                if scenario=='count':
                    p=directory/'progress.json';d=json.loads(p.read_text());d['registered_rows']=41
                else:
                    p=directory/('batch-07.json' if scenario=='alias' else 'batch-09.json');d=json.loads(p.read_text())
                    if scenario=='alias':d['rows'][-1]['official_parent_aliases'][0]['provider_id']='wrong-id'
                    elif scenario=='duplicate':d['rows'][1]=d['rows'][0]
                    else:d['rows'][0]['birth_year']+=1
                p.write_text(json.dumps(d))
                with self.assertRaises((AssertionError,StopIteration)):check(root)

if __name__=='__main__':unittest.main()
