"""Pallet integrity across real BOX -> CARTON -> PALLET sessions."""
import json
from pathlib import Path
import tempfile
import unittest
from agregasi.store import Store
from agregasi.template_model import TemplateRepository,default_document
from agregasi.template_database import product_choices
from agregasi.aggregation_runtime import AggregationRuntime
from agregasi.box_model import BoxRepository
from agregasi.carton_model import CartonRepository
from agregasi.pallet_model import PalletRepository


class PalletTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.store=Store(self.path/'db')
        self.templates=TemplateRepository(self.store);self.runtime=AggregationRuntime(self.store,self.templates)
        self.box=BoxRepository(self.store,self.runtime);self.carton=CartonRepository(self.store,self.runtime);self.repo=PalletRepository(self.store,self.runtime);self.product=product_choices(self.store)[0]
        doc=default_document('BOX');doc.update(child_product=self.product,aggregation_max=1);self.box_id=self.templates.save(doc)
        doc=default_document('CARTON');doc.update(child_template_id=self.box_id,aggregation_max=1);self.carton_id=self.templates.save(doc)
        doc=default_document('PALLET');doc.update(child_template_id=self.carton_id,aggregation_min=2,aggregation_max=3);self.pallet_id=self.templates.save(doc);self.serial=0
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def make_carton(self,batch='QA-BATCH',printed=True,template=None,direct=False):
        self.serial+=1
        if direct:code='DIRECT-UNIT-'+str(self.serial)
        else:
            b=self.box.start(self.box_id,batch,'10/09/2026');b=self.box.scan(b['id'],'QA-UNIT-'+str(self.serial));self.runtime.print_result(b['id']);code=b['parent_code']
        r=self.carton.start(template or self.carton_id,batch,'10/09/2026');r=self.carton.scan(r['id'],code)
        if printed:self.runtime.print_result(r['id'])
        return r
    def start(self,list_id=None):return self.repo.start(self.pallet_id,'QA-BATCH','10/09/2026',list_id)
    def test_three_levels_resolve_product_and_carton_targets(self):
        ready=self.make_carton();unprinted=self.make_carton(printed=False);other=self.make_carton('OTHER')
        self.assertEqual(self.repo.product_for(self.templates.get(self.pallet_id)['document']),self.product)
        self.assertEqual([r['code'] for r in self.repo.candidates(self.product,'QA-BATCH')],[ready['parent_code']])
        r=self.start()
        for code,reason in [(unprinted['parent_code'],'belum dicetak'),(other['parent_code'],'Batch'),('UNKNOWN','bukan hasil Carton')]:
            with self.assertRaisesRegex(ValueError,reason):self.repo.scan(r['id'],code)
        self.assertEqual(self.runtime.get(r['id'])['quantity'],0)
    def test_wrong_template_existing_parent_and_rejected_descendant(self):
        doc=self.templates.get(self.carton_id)['document'];wrong_id=self.templates.save(doc);wrong=self.make_carton(template=wrong_id);owned=self.make_carton();rejected=self.make_carton();r=self.start()
        with self.assertRaisesRegex(ValueError,'Template carton'):self.repo.scan(r['id'],wrong['parent_code'])
        with self.store.db:self.store.db.execute("UPDATE packages SET parent='PLT-OTHER' WHERE code=?",(owned['parent_code'],))
        with self.assertRaisesRegex(ValueError,'parent'):self.repo.scan(r['id'],owned['parent_code'])
        with self.store.db:self.store.db.execute("INSERT INTO revision_state(level,code,status) VALUES('UNIT','QA-UNIT-3','REJECT')")
        with self.assertRaisesRegex(ValueError,'VALID'):self.repo.scan(r['id'],rejected['parent_code'])
        self.assertEqual(self.runtime.get(r['id'])['quantity'],0)
    def test_target_import_is_atomic_and_membership_is_enforced(self):
        a=self.make_carton();b=self.make_carton();path=self.path/'targets.csv';path.write_text('code,batch\n'+a['parent_code']+',QA-BATCH\n')
        lid=self.repo.import_targets(path,self.product,'QA-BATCH');r=self.start(lid)
        with self.assertRaisesRegex(ValueError,'tidak terdaftar'):self.repo.scan(r['id'],b['parent_code'])
        self.repo.scan(r['id'],a['parent_code'])
        with self.assertRaisesRegex(ValueError,'duplikat'):self.repo.create_targets('bad',[b['parent_code']]*2,self.product,'QA-BATCH')
        path.write_text('code,batch\n'+b['parent_code']+',QA-BATCH\nBAD,QA-BATCH\n')
        with self.assertRaises(ValueError):self.repo.import_targets(path,self.product,'QA-BATCH')
        self.assertEqual(len(self.repo.lists(self.product,'QA-BATCH')),1)
    def test_full_pallet_links_cartons_and_preserves_traceability(self):
        cartons=[self.make_carton() for _ in range(3)];r=self.start();reserved=r['parent_code']
        for c in cartons:r=self.repo.scan(r['id'],c['parent_code'])
        self.assertEqual((r['state'],r['quantity'],r['parent_code']),('COMPLETE',3,reserved))
        self.assertEqual([p[0] for p in self.store.db.execute("SELECT parent FROM packages WHERE stage='CARTON' AND batch='QA-BATCH'")],[reserved]*3)
        family=self.repo.revisions.family(('PALLET',reserved));self.assertEqual(len([n for n in family if n['level']=='UNIT']),3)
        self.assertEqual(self.runtime.print_document(r['id'])['data']['quantity'],'3 CARTON')
        self.assertEqual(self.repo.metrics()['pallets'],1)
        with self.assertRaises(ValueError):self.repo.scan(r['id'],cartons[0]['parent_code'])
        self.assertEqual(self.runtime.get(r['id'])['quantity'],3)
    def test_duplicate_and_nonempty_reset_do_not_drop_or_poison_children(self):
        c=self.make_carton();r=self.start();self.repo.scan(r['id'],c['parent_code'])
        with self.assertRaisesRegex(ValueError,'duplikat'):self.repo.scan(r['id'],c['parent_code'])
        with self.assertRaisesRegex(ValueError,'berisi child'):self.runtime.reset_empty(r['id'])
        self.assertEqual(self.runtime.get(r['id'])['quantity'],1);self.assertEqual(self.repo.metrics()['duplicate'],1)
        self.assertEqual(self.repo.revisions.get(('CARTON',c['parent_code']))['status'],'VALID')
    def test_partial_print_verification_and_revised_contents(self):
        cartons=[self.make_carton() for _ in range(2)];r=self.start();self.repo.scan(r['id'],cartons[0]['parent_code'])
        with self.assertRaisesRegex(ValueError,'minimum'):self.repo.finish(r['id'])
        self.repo.scan(r['id'],cartons[1]['parent_code']);r=self.repo.finish(r['id'])
        with self.assertRaisesRegex(ValueError,'Cetak'):self.repo.verify(r['id'],r['parent_code'],2)
        self.runtime.print_result(r['id'])
        with self.assertRaisesRegex(ValueError,'Kode'):self.repo.verify(r['id'],'WRONG',2)
        with self.assertRaisesRegex(ValueError,'Jumlah'):self.repo.verify(r['id'],r['parent_code'],1)
        self.repo.verify(r['id'],r['parent_code'],2);self.assertEqual(self.repo.meta(r['id'])['verified'],1)
        with self.store.db:self.store.db.execute("INSERT INTO revision_state(level,code,status) VALUES('UNIT','QA-UNIT-1','REJECT')")
        with self.assertRaisesRegex(ValueError,'VALID'):self.repo.validate_print(r['id'])
    def test_restart_retains_snapshot_target_and_children(self):
        c=self.make_carton();lid=self.repo.create_targets('List',[c['parent_code']],self.product,'QA-BATCH');r=self.start(lid);self.repo.scan(r['id'],c['parent_code'])
        doc=self.templates.get(self.pallet_id)['document'];doc['aggregation_max']=24;self.templates.save(doc,self.pallet_id)
        child=self.templates.get(self.box_id)['document'];child['child_product']=dict(self.product,id='CHANGED',name='Changed product');self.templates.save(child,self.box_id)
        other=Store(self.path/'db')
        try:
            rt=AggregationRuntime(other,TemplateRepository(other));repo=PalletRepository(other,rt);resumed=repo.start(self.pallet_id,'QA-BATCH','10/09/2026',lid)
            self.assertEqual((resumed['id'],resumed['quantity'],resumed['document']['aggregation_max']),(r['id'],1,3))
            with self.assertRaisesRegex(ValueError,'MFD'):repo.start(self.pallet_id,'QA-BATCH','11/09/2026',lid)
        finally:other.close()
    def test_revision_move_invalidates_both_pallet_labels_and_verifications(self):
        doc=self.templates.get(self.pallet_id)['document'];doc['aggregation_min']=1;self.templates.save(doc,self.pallet_id)
        cartons=[self.make_carton() for _ in range(3)];a=self.start()
        for c in cartons[:2]:self.repo.scan(a['id'],c['parent_code'])
        a=self.repo.finish(a['id']);self.runtime.print_result(a['id']);self.repo.verify(a['id'],a['parent_code'],2)
        b=self.start();self.repo.scan(b['id'],cartons[2]['parent_code']);b=self.repo.finish(b['id']);self.runtime.print_result(b['id']);self.repo.verify(b['id'],b['parent_code'],1)
        key=('CARTON',cartons[0]['parent_code']);self.repo.revisions.unlock(key,'Perbaikan susunan carton')
        self.repo.revisions.move(key,('PALLET',b['parent_code']),'Pemindahan carton sesuai hasil pemeriksaan')
        for r,qty in ((a,1),(b,2)):
            updated=self.runtime.get(r['id']);self.assertEqual(updated['quantity'],qty);self.assertEqual(updated['print_state'],'WAITING');self.assertEqual(self.repo.meta(r['id'])['verified'],0)
            with self.assertRaisesRegex(ValueError,'Cetak'):self.repo.verify(r['id'],r['parent_code'],qty)
            self.repo.validate_print(r['id']);self.runtime.print_result(r['id']);self.repo.verify(r['id'],r['parent_code'],qty)
        self.repo.revisions.unlock(key,'Pemeriksaan ulang');self.repo.revisions.change_status(key,'REJECT','Kemasan rusak')
        self.assertEqual(self.repo.meta(b['id'])['verified'],0)
        with self.assertRaisesRegex(ValueError,'VALID'):self.repo.validate_print(b['id'])

    def test_direct_unit_carton_can_feed_pallet_and_auto_print_claims_once(self):
        doc=default_document('CARTON');doc.update(child_level='UNIT',child_product=self.product,aggregation_max=1);direct=self.templates.save(doc)
        c=self.make_carton(template=direct,direct=True)
        doc=default_document('PALLET');doc.update(child_template_id=direct,aggregation_max=1,print_mode='AUTO');pid=self.templates.save(doc)
        r=self.repo.start(pid,'QA-BATCH','10/09/2026');r=self.repo.scan(r['id'],c['parent_code'])
        self.assertEqual(r['print_state'],'PENDING');self.assertTrue(self.runtime.claim_print(r['id'],True));self.assertFalse(self.runtime.claim_print(r['id'],True))
    def test_product_snapshot_prevents_mixed_product_after_template_edit(self):
        c=self.make_carton();r=self.start();other=dict(self.product,id='OTHER',name='OTHER')
        snapshot=json.loads(c['document']) if isinstance(c['document'],str) else dict(c['document']);snapshot['carton_product']=other
        with self.store.db:self.store.db.execute('UPDATE aggregation_runs SET document=? WHERE id=?',(json.dumps(snapshot),c['id']))
        with self.assertRaisesRegex(ValueError,'Produk'):self.repo.scan(r['id'],c['parent_code'])
        self.assertEqual(self.runtime.get(r['id'])['quantity'],0)

if __name__=='__main__':unittest.main()
