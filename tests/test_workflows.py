import csv
import json
import tempfile
import unittest
from pathlib import Path
from agregasi.store import Store

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'store.sqlite3'
        self.store=Store(self.path)
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def test_valid_duplicate_and_invalid(self):
        self.assertEqual(self.store.scan('BOX','BOX-TEST-0001')[1],'VALID')
        self.assertEqual(self.store.scan('BOX','BOX-TEST-0001')[1],'DUPLIKAT')
        self.assertEqual(self.store.scan('BOX','bad-format')[1],'REJECT')
        self.assertEqual(self.store.summary()['stages']['BOX']['total'],259)
        self.assertEqual(len([p for p in self.store.available('BOX') if p['code']=='BOX-TEST-0001']),1)
    def test_empty_does_not_create_event(self):
        n=len(self.store.events())
        with self.assertRaises(ValueError):self.store.scan('BOX','  ')
        self.assertEqual(len(self.store.events()),n)
    def test_parent_integrity(self):
        self.store.scan('BOX','BOX-TEST-1');self.store.scan('CARTON','CTN-TEST-1')
        self.store.link('BOX','BOX-TEST-1','CTN-TEST-1')
        with self.assertRaises(ValueError):self.store.link('BOX','BOX-TEST-1','CTN-TEST-1')
        self.assertEqual(self.store.db.execute("SELECT parent FROM packages WHERE code='BOX-TEST-1'").fetchone()[0],'CTN-TEST-1')
    def test_cross_batch_rejected(self):
        self.store.scan('BOX','BOX-TEST-1')
        self.store.configure({'batch':'BATCH-OTHER'})
        self.store.scan('CARTON','CTN-TEST-1')
        with self.assertRaises(ValueError):self.store.link('BOX','BOX-TEST-1','CTN-TEST-1')
    def test_import_is_atomic(self):
        with self.assertRaises(ValueError):
            self.store.import_rows([{'stage':'BOX','code':'BOX-IMPORT-1'},{'stage':'UNKNOWN','code':'ANY'}])
        self.assertFalse(self.store.db.execute("SELECT 1 FROM packages WHERE code='BOX-IMPORT-1'").fetchone())
    def test_revision_is_audited(self):
        event_id,_=self.store.scan('BOX','BOX-TEST-1')
        self.store.revise(event_id,'Label diverifikasi ulang')
        self.assertEqual(self.store.events()[0]['note'],'Label diverifikasi ulang')
        row=self.store.db.execute("SELECT detail FROM audit WHERE action='REVISI CATATAN'").fetchone()
        self.assertIn('Label diverifikasi ulang',row[0])
    def test_data_survives_restart(self):
        self.store.scan('PALLET','PLT-TEST-1');self.store.close()
        self.store=Store(self.path)
        self.assertEqual(self.store.events()[0]['code'],'PLT-TEST-1')
        self.assertEqual(self.store.scan('PALLET','PLT-TEST-1')[1],'DUPLIKAT')
    def test_csv_and_json_round_trip(self):
        p=Path(self.tmp.name)/'input.csv';p.write_text('stage,code\nBOX,BOX-IMPORT-1\nBOX,BOX-IMPORT-1\n')
        rows=self.store.read_import(p)
        results=self.store.import_rows(rows)
        self.assertEqual([x[1] for x in results],['VALID','DUPLIKAT'])
        out=Path(self.tmp.name)/'output.json';self.store.export_json(out)
        data=json.loads(out.read_text())
        self.assertEqual(data['mode'],'SIMULASI LOKAL')
        self.assertEqual(data['events'][0]['status'],'DUPLIKAT')
    def test_reject_not_valid_package(self):
        _,status=self.store.scan('BOX','BOX-TEST-1',force_reject=True)
        self.assertEqual(status,'REJECT')
        self.assertFalse(self.store.db.execute("SELECT 1 FROM packages WHERE code='BOX-TEST-1'").fetchone())

if __name__=='__main__':unittest.main()
