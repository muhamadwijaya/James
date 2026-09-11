"""Relational settings, migration, child validation and quantity/print boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from agregasi.store import Store
from agregasi.template_model import TemplateRepository,default_document,validate_document
from agregasi.template_database import product_choices
from agregasi.aggregation_runtime import AggregationRuntime


class AggregationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.store=Store(self.path/'app.db');self.repo=TemplateRepository(self.store);self.runtime=AggregationRuntime(self.store,self.repo)
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def document(self,level='BOX',maximum=2,minimum=1,mode='MANUAL',direct=False):
        doc=default_document(level);doc.update(aggregation_min=minimum,aggregation_max=maximum,print_mode=mode)
        if level=='BOX' or direct:doc['child_level']='UNIT';doc['child_product']=product_choices(self.store)[0]
        return doc
    def test_product_choices_read_all_types_and_bind_by_id(self):
        source=self.path/'products.db'
        with sqlite3.connect(source) as db:
            db.execute('CREATE TABLE products (sku TEXT PRIMARY KEY, title TEXT)');db.executemany('INSERT INTO products VALUES (?,?)',[('B','Same name'),('A','Same name'),('C','Other')])
        config={'path':str(source),'table':'products','id_column':'sku','name_column':'title'};before=source.read_bytes()
        choices=product_choices(self.store,config);self.assertEqual({p['id'] for p in choices},{'A','B','C'});self.assertEqual(source.read_bytes(),before)
        doc=self.document();doc['child_product']=next(p for p in choices if p['id']=='B');identifier=self.repo.save(doc)
        other=Store(self.path/'app.db')
        try:
            saved=TemplateRepository(other).get(identifier)['document'];self.assertEqual(saved['child_product']['id'],'B');self.assertEqual(saved['child_product']['source'],config)
        finally:other.close()
    def test_carton_can_bypass_box_but_cannot_bind_both(self):
        doc=self.document('CARTON',direct=True);validate_document(doc);doc['child_template_id']='some-box'
        with self.assertRaises(ValueError):validate_document(doc)
        doc['child_template_id']=None;doc['child_level']='BOX'
        with self.assertRaises(ValueError):validate_document(doc)
        doc['child_product']=None;validate_document(doc)
    def test_quantity_bounds_reject_invalid_settings(self):
        for lo,hi in [(0,10),(11,10),(1,0),(True,10),(1,1000001)]:
            with self.assertRaises(ValueError):self.repo.save(self.document(minimum=lo,maximum=hi))
    def test_settings_and_label_are_saved_atomically(self):
        doc=self.document('CARTON',maximum=12,minimum=6,mode='AUTO',direct=True);identifier=self.repo.save(doc)
        row=dict(self.store.db.execute('SELECT * FROM template_agregasi WHERE template_id=?',(identifier,)).fetchone())
        self.assertEqual((row['child_level'],row['child_product_id'],row['target_min'],row['target_max'],row['print_mode']),('UNIT','CURRENT-PRODUCT',6,12,'AUTO'))
        self.assertEqual(json.loads(row['document']),self.repo.get(identifier)['document'])
        self.store.db.execute("CREATE TRIGGER reject_test_update BEFORE UPDATE ON template_agregasi BEGIN SELECT RAISE(ABORT,'test write failure'); END")
        changed=deepcopy(doc);changed['name']='MUST ROLLBACK'
        with self.assertRaises(sqlite3.IntegrityError):self.repo.save(changed,identifier)
        self.assertEqual(self.repo.get(identifier)['document']['name'],doc['name'])
    def test_old_document_migration_preserves_design_and_identity(self):
        identifier=self.repo.list('BOX')[0]['id'];doc=self.repo.get(identifier)['document']
        for key in ('aggregation_min','aggregation_max','print_mode','child_product'):doc.pop(key)
        self.store.db.execute('UPDATE label_templates SET document=? WHERE id=?',(json.dumps(doc),identifier));self.store.db.commit()
        repo=TemplateRepository(self.store);saved=repo.get(identifier)['document']
        self.assertEqual(saved['elements'],doc['elements']);self.assertEqual(saved['aggregation_max'],50);self.assertEqual(saved['print_mode'],'MANUAL')
        row=self.store.db.execute('SELECT target_max FROM template_agregasi WHERE template_id=?',(identifier,)).fetchone();self.assertEqual(row[0],50)
    def test_auto_print_trigger_occurs_once_at_max(self):
        identifier=self.repo.save(self.document(mode='AUTO'));run=self.runtime.start(identifier)
        run=self.runtime.scan(run['id'],'U1');self.assertEqual(run['state'],'OPEN');self.assertFalse(run['print_state']=='PENDING')
        with self.assertRaises(ValueError):self.runtime.scan(run['id'],'U1')
        run=self.runtime.scan(run['id'],'U2');self.assertEqual(run['quantity'],2);self.assertEqual(run['print_state'],'PENDING')
        self.assertTrue(self.runtime.claim_print(run['id'],automatic=True));self.assertFalse(self.runtime.claim_print(run['id'],automatic=True));self.runtime.print_result(run['id'])
        with self.assertRaises(ValueError):self.runtime.scan(run['id'],'U3')
        self.assertEqual(self.runtime.print_document(run['id'])['data']['quantity'],'2 UNIT')
    def test_manual_print_waits_and_minimum_guards_partial_lock(self):
        identifier=self.repo.save(self.document(maximum=3,minimum=2));run=self.runtime.start(identifier);run=self.runtime.scan(run['id'],'M1')
        with self.assertRaises(ValueError):self.runtime.finish_partial(run['id'])
        with self.assertRaises(ValueError):self.runtime.claim_print(run['id'])
        run=self.runtime.scan(run['id'],'M2');run=self.runtime.finish_partial(run['id']);self.assertEqual(run['print_state'],'WAITING')
        self.assertFalse(self.runtime.claim_print(run['id'],automatic=True));self.assertTrue(self.runtime.claim_print(run['id']))
    def test_maximum_target_always_queues_the_automatic_label(self):
        identifier=self.repo.save(self.document(maximum=2,mode='MANUAL'));run=self.runtime.start(identifier)
        run=self.runtime.scan(run['id'],'X1');self.assertEqual(run['print_state'],'WAITING')
        run=self.runtime.scan(run['id'],'X2')
        self.assertEqual(run['state'],'COMPLETE');self.assertEqual(run['print_state'],'PENDING')
        self.assertTrue(self.runtime.claim_print(run['id'],automatic=True))

    def test_carton_via_box_requires_completed_selected_box(self):
        box_id=self.repo.save(self.document(maximum=1));box=self.runtime.start(box_id);box=self.runtime.scan(box['id'],'RAW-1')
        doc=self.document('CARTON',maximum=1);doc['child_template_id']=box_id;carton_id=self.repo.save(doc);carton=self.runtime.start(carton_id)
        with self.assertRaises(ValueError):self.runtime.scan(carton['id'],'RAW-2')
        carton=self.runtime.scan(carton['id'],box['parent_code']);self.assertEqual(carton['quantity'],1)
        relation=self.store.db.execute('SELECT parent FROM packages WHERE code=?',(box['parent_code'],)).fetchone();self.assertEqual(relation['parent'],carton['parent_code'])
        self.assertEqual(self.runtime.get(carton['id'])['document']['child_product'],None)
    def test_carton_direct_counts_units_without_a_box(self):
        identifier=self.repo.save(self.document('CARTON',maximum=1,direct=True));run=self.runtime.start(identifier);run=self.runtime.scan(run['id'],'DIRECT-U1')
        self.assertEqual(run['state'],'COMPLETE');self.assertEqual(run['document']['child_level'],'UNIT')
        item=self.store.db.execute('SELECT * FROM aggregation_children WHERE run_id=?',(run['id'],)).fetchone();self.assertIsNone(item['child_template_id']);self.assertIsNotNone(item['product_id'])
    def test_pending_print_survives_restart_and_changed_targets_do_not_affect_session(self):
        doc=self.document(mode='AUTO');identifier=self.repo.save(doc);run=self.runtime.start(identifier);self.runtime.scan(run['id'],'S1')
        doc['aggregation_max']=5;self.repo.save(doc,identifier);run=self.runtime.scan(run['id'],'S2');self.assertEqual(run['quantity'],2)
        other=Store(self.path/'app.db')
        try:
            service=AggregationRuntime(other,TemplateRepository(other));resumed=service.start(identifier);self.assertEqual(resumed['id'],run['id']);self.assertEqual(resumed['print_state'],'PENDING')
        finally:other.close()
    def test_failed_print_can_be_retried_without_rescanning(self):
        identifier=self.repo.save(self.document(maximum=1,mode='AUTO'));run=self.runtime.scan(self.runtime.start(identifier)['id'],'E1')
        self.assertTrue(self.runtime.claim_print(run['id'],True));self.runtime.print_result(run['id'],'Printer offline')
        self.assertFalse(self.runtime.claim_print(run['id'],True));self.assertTrue(self.runtime.claim_print(run['id']));self.runtime.print_result(run['id'])
        self.assertEqual(self.runtime.get(run['id'])['quantity'],1)

if __name__=='__main__':unittest.main()
