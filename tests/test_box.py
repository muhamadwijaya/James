"""BOX workflow regression checks using temporary persisted data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from agregasi.store import Store
from agregasi.template_model import TemplateRepository,default_document
from agregasi.template_database import product_choices
from agregasi.aggregation_runtime import AggregationRuntime
from agregasi.box_model import BoxRepository


class BoxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.store=Store(self.path/'db');self.templates=TemplateRepository(self.store);self.runtime=AggregationRuntime(self.store,self.templates);self.repo=BoxRepository(self.store,self.runtime)
        self.product=product_choices(self.store)[0];doc=default_document('BOX');doc.update(child_product=self.product,aggregation_min=2,aggregation_max=3);self.template=self.templates.save(doc)
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def start(self,list_id=None):return self.repo.start(self.template,'QA-BATCH','10/09/2026',list_id)
    def test_import_is_atomic_and_enforces_product_batch_and_duplicates(self):
        p=self.path/'bad.csv';p.write_text('serial,batch\nU1,QA-BATCH\nU1,QA-BATCH\n')
        with self.assertRaisesRegex(ValueError,'duplikat'):self.repo.import_targets(p,self.product,'QA-BATCH')
        self.assertEqual(self.repo.lists(self.product,'QA-BATCH'),[])
        p.write_text('serial,batch\nU1,OTHER\n')
        with self.assertRaisesRegex(ValueError,'batch'):self.repo.import_targets(p,self.product,'QA-BATCH')
    def test_rejected_and_duplicate_scans_do_not_change_quantity(self):
        p=self.path/'target.csv';p.write_text('serial\nU1\nU2\nU3\n');list_id=self.repo.import_targets(p,self.product,'QA-BATCH');r=self.start(list_id)
        with self.assertRaisesRegex(ValueError,'tidak terdaftar'):self.repo.scan(r['id'],'OUTSIDE')
        self.repo.scan(r['id'],'U1')
        with self.assertRaisesRegex(ValueError,'duplikat'):self.repo.scan(r['id'],'U1')
        self.assertEqual(self.runtime.get(r['id'])['quantity'],1);m=self.repo.metrics();self.assertEqual((m['valid'],m['reject'],m['duplicate']),(1,1,1))
    def test_reserved_box_code_is_retained_at_completion_and_unique(self):
        r=self.start();code=r['parent_code'];self.assertTrue(code)
        for c in ('U1','U2','U3'):r=self.repo.scan(r['id'],c)
        self.assertEqual(r['parent_code'],code);self.assertEqual(r['state'],'COMPLETE');self.assertEqual(self.repo.metrics()['boxes'],1)
        self.runtime.print_result(r['id']);next_run=self.start();self.assertNotEqual(next_run['parent_code'],code)
    def test_partial_lock_print_and_verification(self):
        r=self.start();self.repo.scan(r['id'],'U1')
        with self.assertRaisesRegex(ValueError,'minimum'):self.runtime.finish_partial(r['id'])
        self.repo.scan(r['id'],'U2');r=self.runtime.finish_partial(r['id'])
        with self.assertRaisesRegex(ValueError,'Cetak'):self.repo.verify(r['id'],r['parent_code'],2)
        self.assertTrue(self.runtime.claim_print(r['id']));self.runtime.print_result(r['id'])
        with self.assertRaisesRegex(ValueError,'Kode'):self.repo.verify(r['id'],'WRONG',2)
        with self.assertRaisesRegex(ValueError,'Jumlah'):self.repo.verify(r['id'],r['parent_code'],1)
        self.repo.verify(r['id'],r['parent_code'],2);self.assertEqual(self.repo.meta(r['id'])['verified'],1)
    def test_resume_keeps_children_mfd_and_target_snapshot(self):
        r=self.start();self.repo.scan(r['id'],'U1');other=Store(self.path/'db')
        try:
            runtime=AggregationRuntime(other,TemplateRepository(other));repo=BoxRepository(other,runtime);resumed=repo.start(self.template,'QA-BATCH','10/09/2026')
            self.assertEqual(resumed['id'],r['id']);self.assertEqual(resumed['quantity'],1);self.assertEqual(runtime.get(r['id'])['document']['data']['mfg_date'],'10/09/2026')
            with self.assertRaisesRegex(ValueError,'MFD'):repo.start(self.template,'QA-BATCH','11/09/2026')
        finally:other.close()
    def test_reset_never_erases_filled_box_and_line_pause_rejects_scan(self):
        r=self.start();self.repo.scan(r['id'],'U1')
        with self.assertRaisesRegex(ValueError,'berisi child'):self.runtime.reset_empty(r['id'])
        self.store.configure({'configuration':{'line_active':False}})
        with self.assertRaisesRegex(ValueError,'nonaktif'):self.repo.scan(r['id'],'U2')
        self.assertEqual(self.runtime.get(r['id'])['quantity'],1)

if __name__=='__main__':unittest.main()
