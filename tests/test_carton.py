"""End-to-end parent/child integrity checks for the Carton workstation."""
from pathlib import Path
import tempfile
import unittest
from agregasi.store import Store
from agregasi.template_model import TemplateRepository,default_document
from agregasi.template_database import product_choices
from agregasi.aggregation_runtime import AggregationRuntime
from agregasi.box_model import BoxRepository
from agregasi.carton_model import CartonRepository
from agregasi.revision_model import RevisionRepository


class CartonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.store=Store(self.path/'db');self.templates=TemplateRepository(self.store);self.runtime=AggregationRuntime(self.store,self.templates);self.box=BoxRepository(self.store,self.runtime);self.repo=CartonRepository(self.store,self.runtime);self.product=product_choices(self.store)[0]
        doc=default_document('BOX');doc.update(child_product=self.product,aggregation_min=1,aggregation_max=1);self.box_id=self.templates.save(doc)
        doc=default_document('CARTON');doc.update(child_template_id=self.box_id,aggregation_min=2,aggregation_max=3);self.carton_id=self.templates.save(doc);self.serial=0
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def make_box(self,batch='QA-BATCH',printed=True,template=None):
        self.serial+=1;r=self.box.start(template or self.box_id,batch,'10/09/2026');r=self.box.scan(r['id'],'UNIT-QA-'+str(self.serial))
        if printed:self.runtime.print_result(r['id'])
        return r
    def start(self,list_id=None):return self.repo.start(self.carton_id,'QA-BATCH','10/09/2026',list_id)
    def test_only_finished_printed_unassigned_boxes_are_targets(self):
        ready=self.make_box();unprinted=self.make_box(printed=False);other=self.make_box('OTHER')
        self.assertEqual([r['code'] for r in self.repo.candidates(self.product,'QA-BATCH')],[ready['parent_code']])
        r=self.start()
        with self.assertRaisesRegex(ValueError,'belum dicetak'):self.repo.scan(r['id'],unprinted['parent_code'])
        with self.assertRaisesRegex(ValueError,'Batch'):self.repo.scan(r['id'],other['parent_code'])
        with self.assertRaisesRegex(ValueError,'bukan hasil Box'):self.repo.scan(r['id'],'UNKNOWN')
        self.assertEqual(self.runtime.get(r['id'])['quantity'],0)
    def test_rejects_wrong_child_template_and_existing_parent(self):
        doc=default_document('BOX');doc.update(child_product=self.product,aggregation_max=1);other_id=self.templates.save(doc);wrong=self.make_box(template=other_id);owned=self.make_box();r=self.start()
        with self.assertRaisesRegex(ValueError,'Template box'):self.repo.scan(r['id'],wrong['parent_code'])
        with self.store.db:self.store.db.execute("UPDATE packages SET parent='CTN-OTHER' WHERE code=?",(owned['parent_code'],))
        with self.assertRaisesRegex(ValueError,'parent'):self.repo.scan(r['id'],owned['parent_code'])
    def test_target_list_import_validation_and_membership(self):
        one=self.make_box();two=self.make_box();p=self.path/'list.csv';p.write_text('code,batch\n'+one['parent_code']+',QA-BATCH\n')
        lid=self.repo.import_targets(p,self.product,'QA-BATCH');r=self.start(lid)
        with self.assertRaisesRegex(ValueError,'tidak terdaftar'):self.repo.scan(r['id'],two['parent_code'])
        self.repo.scan(r['id'],one['parent_code']);self.assertEqual(self.runtime.get(r['id'])['quantity'],1)
        with self.assertRaisesRegex(ValueError,'duplikat'):self.repo.create_targets('bad',[two['parent_code']]*2,self.product,'QA-BATCH')
        self.assertEqual(len(self.repo.lists(self.product,'QA-BATCH')),1)
    def test_full_carton_keeps_reserved_code_and_links_all_boxes(self):
        boxes=[self.make_box() for _ in range(3)];r=self.start();code=r['parent_code']
        for b in boxes:r=self.repo.scan(r['id'],b['parent_code'])
        self.assertEqual(r['state'],'COMPLETE');self.assertEqual(r['parent_code'],code);self.assertEqual(r['quantity'],3)
        parents=[v[0] for v in self.store.db.execute("SELECT parent FROM packages WHERE stage='BOX' AND batch='QA-BATCH'")];self.assertEqual(parents,[code]*3)
        self.assertEqual(self.runtime.print_document(r['id'])['data']['quantity'],'3 BOX');self.assertEqual(self.repo.metrics()['cartons'],1)
        family=self.repo.revisions.family(('CARTON',code));self.assertEqual(len([n for n in family if n['level']=='UNIT']),3)
    def test_duplicate_does_not_invalidate_child_or_increment_quantity(self):
        b=self.make_box();r=self.start();self.repo.scan(r['id'],b['parent_code'])
        with self.assertRaisesRegex(ValueError,'duplikat'):self.repo.scan(r['id'],b['parent_code'])
        self.assertEqual(self.runtime.get(r['id'])['quantity'],1);self.assertEqual(self.repo.revisions.get(('BOX',b['parent_code']))['status'],'VALID');self.assertEqual(self.repo.metrics()['duplicate'],1)
    def test_box_failed_rescan_does_not_poison_valid_child(self):
        doc=self.templates.get(self.box_id)['document'];doc['aggregation_max']=2;self.templates.save(doc,self.box_id)
        b=self.box.start(self.box_id,'QA-BATCH','10/09/2026');self.box.scan(b['id'],'UNIT-1')
        with self.assertRaises(ValueError):self.box.scan(b['id'],'UNIT-1')
        b=self.box.scan(b['id'],'UNIT-2');self.runtime.print_result(b['id']);r=self.start();r=self.repo.scan(r['id'],b['parent_code']);self.assertEqual(r['quantity'],1)
    def test_rejected_descendant_blocks_scan_and_lock_after_revision(self):
        first=self.make_box();second=self.make_box();r=self.start();self.repo.scan(r['id'],first['parent_code']);self.repo.scan(r['id'],second['parent_code'])
        with self.store.db:self.store.db.execute("INSERT INTO revision_state(level,code,status) VALUES('UNIT','UNIT-QA-1','REJECT')")
        with self.assertRaisesRegex(ValueError,'VALID'):self.repo.finish(r['id'])
        self.assertEqual(self.runtime.get(r['id'])['state'],'OPEN')
    def test_partial_minimum_reset_print_and_verification(self):
        first=self.make_box();second=self.make_box();r=self.start();self.repo.scan(r['id'],first['parent_code'])
        with self.assertRaisesRegex(ValueError,'minimum'):self.repo.finish(r['id'])
        with self.assertRaisesRegex(ValueError,'berisi child'):self.runtime.reset_empty(r['id'])
        self.repo.scan(r['id'],second['parent_code']);r=self.repo.finish(r['id'])
        with self.assertRaisesRegex(ValueError,'Cetak'):self.repo.verify(r['id'],r['parent_code'],2)
        self.runtime.print_result(r['id'])
        with self.assertRaisesRegex(ValueError,'Kode'):self.repo.verify(r['id'],'WRONG',2)
        with self.assertRaisesRegex(ValueError,'Jumlah'):self.repo.verify(r['id'],r['parent_code'],1)
        self.repo.verify(r['id'],r['parent_code'],2);self.assertEqual(self.repo.meta(r['id'])['verified'],1)
    def test_resume_preserves_mfd_list_quantity_and_print_mode(self):
        b=self.make_box();lid=self.repo.create_targets('List',[b['parent_code']],self.product,'QA-BATCH');r=self.start(lid);self.repo.scan(r['id'],b['parent_code'])
        other=Store(self.path/'db')
        try:
            rt=AggregationRuntime(other,TemplateRepository(other));repo=CartonRepository(other,rt);resumed=repo.start(self.carton_id,'QA-BATCH','10/09/2026',lid)
            self.assertEqual(resumed['id'],r['id']);self.assertEqual(resumed['quantity'],1);self.assertEqual(resumed['document']['data']['mfg_date'],'10/09/2026')
            with self.assertRaisesRegex(ValueError,'MFD'):repo.start(self.carton_id,'QA-BATCH','11/09/2026',lid)
        finally:other.close()
    def test_direct_unit_mode_and_automatic_print_claim_are_preserved(self):
        doc=default_document('CARTON');doc.update(child_level='UNIT',child_product=self.product,aggregation_min=1,aggregation_max=1,print_mode='AUTO');identifier=self.templates.save(doc);r=self.repo.start(identifier,'QA-BATCH','10/09/2026');r=self.repo.scan(r['id'],'DIRECT-UNIT')
        self.assertEqual(r['print_state'],'PENDING');self.assertTrue(self.runtime.claim_print(r['id'],True));self.assertFalse(self.runtime.claim_print(r['id'],True));self.assertEqual(self.repo.metrics('UNIT')['valid'],1)

if __name__=='__main__':unittest.main()
