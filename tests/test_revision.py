import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from agregasi.store import Store
from agregasi.app import MainWindow
from agregasi.revision_model import RevisionRepository
from agregasi.settings_runtime import SettingsRuntime
from agregasi.aggregation_runtime import AggregationRuntime
from agregasi.template_model import TemplateRepository,default_document

class RevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=Store(self.root/'db.sqlite3');self.repo=RevisionRepository(self.store);self.window=None;self.runtime=None
    def tearDown(self):
        if self.window:self.window.close();self.window.deleteLater()
        if self.runtime:self.runtime.shutdown();self.runtime.deleteLater()
        self.app.processEvents();self.store.close();self.tmp.cleanup()
    def package(self,level,code):self.store.scan(level,code);return level,code
    def manual_tree(self):
        b=self.package('BOX','BOX-TEST-001');c=self.package('CARTON','CTN-TEST-001');p=self.package('PALLET','PLT-TEST-001')
        self.store.link('BOX',b[1],c[1]);self.store.link('CARTON',c[1],p[1]);return b,c,p
    def make_run(self,name,units,max_qty=5):
        if not hasattr(self,'templates'):self.templates=TemplateRepository(self.store);self.aggregation=AggregationRuntime(self.store,self.templates)
        doc=default_document('BOX');doc.update(name=name,aggregation_min=1,aggregation_max=max_qty)
        # Construct a genuine completed session fixture with an immutable document.
        identifier=name;code='BOX-'+name
        with self.store.db:
            self.store.db.execute('INSERT INTO aggregation_runs(id,template_id,level,batch,document,quantity,state,parent_code,print_state,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(identifier,'fixture','BOX',self.store.get('batch'),json.dumps(doc),len(units),'COMPLETE',code,'SENT','2026-09-06T10:00:00'))
            self.store.db.execute('INSERT INTO packages(stage,code,batch) VALUES(?,?,?)',('BOX',code,self.store.get('batch')))
            for unit in units:self.store.db.execute('INSERT INTO aggregation_children(run_id,child_level,code,ts) VALUES(?,?,?,?)',(identifier,'UNIT',unit,'2026-09-06T10:00:00'))
            self.store._event('BOX','Agregasi BOX',code,'VALID',source='template')
        return ('BOX',code)
    def test_search_intersects_fields_along_same_branch(self):
        b,c,p=self.manual_tree();other=self.package('BOX','BOX-OTHER-001');self.store.link('BOX',other[1],c[1])
        found=self.repo.search({'BOX':b[1],'PALLET':p[1]});self.assertEqual({r['code'] for r in found},{b[1],c[1],p[1]})
        self.assertEqual(self.repo.search({'BOX':b[1],'CARTON':'CTN-MISSING'}),[])
    def test_unit_search_never_matches_sibling_branch(self):
        a=self.make_run('RUN1',['UNIT-001','UNIT-002']);b=self.make_run('RUN2',['UNIT-003']);parent=self.package('CARTON','CTN-ROOT')
        self.store.link('BOX',a[1],parent[1]);self.store.link('BOX',b[1],parent[1])
        self.assertEqual(self.repo.search({'UNIT':'UNIT-001','BOX':b[1]}),[])
        self.assertEqual({r['code'] for r in self.repo.search({'UNIT':'UNIT-001','BOX':a[1]})},{'UNIT-001',a[1],parent[1]})
    def test_date_batch_status_filters_and_invalid_range(self):
        key=self.package('BOX','BOX-DATE-001');rows=self.repo.search(batch=self.store.get('batch'),status='VALID',start='2020-01-01',end='2099-01-01');self.assertIn(key[1],[r['code'] for r in rows])
        self.assertEqual(self.repo.search(batch='NONE'),[])
        with self.assertRaises(ValueError):self.repo.search(start='2026-02-01',end='2026-01-01')
    def test_locked_status_change_rejected_then_audited(self):
        key=self.package('BOX','BOX-STATUS-001');before=list(self.store.events())
        with self.assertRaises(ValueError):self.repo.change_status(key,'REJECT','label rusak')
        self.repo.unlock(key,'verifikasi QC');self.repo.change_status(key,'REJECT','label rusak')
        self.assertEqual(self.repo.get(key)['status'],'REJECT');self.assertTrue(self.repo.get(key)['locked']);self.assertFalse(self.store.db.execute('SELECT active FROM packages WHERE code=?',(key[1],)).fetchone()[0])
        log=self.repo.logs()[0];self.assertEqual(json.loads(log['before_json'])['status'],'VALID');self.assertEqual(json.loads(log['after_json'])['status'],'REJECT')
        original=self.store.db.execute('SELECT * FROM events WHERE id=?',(before[0]['id'],)).fetchone();self.assertEqual(original['status'],'VALID')
    def test_restore_reenables_package_and_new_event_is_uploadable(self):
        key=self.package('BOX','BOX-RESTORE-001');self.repo.unlock(key,'QC pemeriksaan');self.repo.change_status(key,'REJECT','barcode rusak');self.repo.unlock(key,'QC perbaikan');self.repo.change_status(key,'VALID','sudah diperbaiki')
        self.runtime=SettingsRuntime(self.store);self.assertEqual(self.runtime.delivery.validate_rows(self.runtime.delivery.rows()),[]);self.assertIn(key[1],[r['code'] for r in self.store.available('BOX')])
    def test_pending_and_unit_revision_do_not_break_dashboard_or_upload(self):
        self.make_run('UNITRUN',['UNIT-TEST-001']);key=('UNIT','UNIT-TEST-001');self.repo.unlock(key,'verifikasi unit');self.repo.change_status(key,'PENDING','menunggu QC')
        self.window=MainWindow(self.store);self.window.show();self.window.navigate('dashboard');self.app.processEvents();self.assertFalse(self.window.pages['dashboard'].grab().isNull());self.assertEqual(self.window.settings_runtime.delivery.validate_rows(self.window.settings_runtime.delivery.rows()),[])
    def test_move_manual_updates_hierarchy_and_marks_ancestors(self):
        b,c,p=self.manual_tree();target=self.package('CARTON','CTN-TARGET');self.repo.unlock(b,'perbaiki parent');self.repo.move(b,target,'pindah sesuai dokumen')
        self.assertEqual(self.repo.get(b)['parent'],target[1]);self.assertEqual(self.repo.get(p)['print_state'],'CETAK ULANG');self.assertNotIn(c[1],{r['code'] for r in self.repo.family(b)})
    def test_move_rejects_cross_batch_and_invalid_level_atomically(self):
        b,c,p=self.manual_tree();self.store.configure({'batch':'OTHER'});target=self.package('CARTON','CTN-OTHER');self.repo.unlock(b,'verifikasi parent');n=len(self.repo.logs())
        for bad in (target,p):
            with self.assertRaises(ValueError):self.repo.move(b,bad,'pindah parent')
        self.assertEqual(self.repo.get(b)['parent'],c[1]);self.assertEqual(len(self.repo.logs()),n)
    def test_unit_move_updates_both_quantities_and_snapshot_print_data(self):
        a=self.make_run('A',['UNIT-A','UNIT-B']);b=self.make_run('B',['UNIT-C']);unit=('UNIT','UNIT-B');self.repo.unlock(unit,'verifikasi unit');self.repo.move(unit,b,'koreksi unit kemasan')
        self.assertEqual(self.repo.get(a)['quantity'],1);self.assertEqual(self.repo.get(b)['quantity'],2);self.assertEqual(self.repo.get(unit)['parent'],b[1]);self.assertEqual(self.aggregation.print_document('B')['data']['quantity'],'2 UNIT')
    def test_capacity_and_minimum_block_unit_move(self):
        a=self.make_run('A',['UNIT-A']);b=self.make_run('B',['UNIT-B'],1);unit=('UNIT','UNIT-A');self.repo.unlock(unit,'verifikasi unit')
        with self.assertRaises(ValueError):self.repo.move(unit,b,'koreksi isi kemasan')
        self.assertEqual(self.repo.get(unit)['parent'],a[1]);self.assertEqual(self.repo.get(a)['quantity'],1)
    def test_revision_blocked_while_sending(self):
        key=self.package('BOX','BOX-UPLOADING');self.runtime=SettingsRuntime(self.store);identifier=self.store.events()[0]['id'];self.runtime.repo.mark_delivery([identifier],'SENDING');self.repo.unlock(key,'verifikasi data')
        with self.assertRaises(ValueError):self.repo.change_status(key,'REJECT','perbaikan data')
    def test_reprint_pdf_contains_selected_serial_and_records_result(self):
        key=self.package('BOX','BOX-PRINT-SELECTED');doc=self.repo.label(key,None,None);self.assertEqual(doc['data']['serial'],key[1])
        from agregasi.label_render import export_pdf
        path=self.root/'label.pdf';export_pdf(doc,path);self.assertTrue(path.read_bytes().startswith(b'%PDF'))
        self.repo.record_print(key,'salinan QC','PDF TERSIMPAN');self.assertEqual(self.repo.get(key)['print_state'],'PDF TERSIMPAN');self.assertEqual(self.repo.logs()[0]['action'],'REPRINT LABEL')
    def test_csv_exports_actual_before_after_and_formula_safety(self):
        key=self.package('BOX','BOX-CSV');self.repo.unlock(key,'cek data');self.repo.change_status(key,'PENDING','=1+1')
        path=self.root/'logs.csv';self.repo.export(path,self.repo.logs(),True);text=path.read_text(encoding='utf-8-sig');self.assertIn('VALID,PENDING',text);self.assertIn("'=1+1",text)
    def test_ui_pagination_sort_and_action_buttons_change_records(self):
        for i in range(21):self.package('BOX',f'BOX-UI-{i:03}')
        self.window=MainWindow(self.store);p=self.window.pages['revision'];self.assertEqual(p.grid.rowCount(),8);p.buttons['next'].click();self.assertEqual(p.page_index,1);p.sort_by(2);self.assertEqual(p.page_index,0)
        p.box.setText('BOX-UI-005');p.buttons['revision_search'].click();self.assertEqual(len(p.rows),1);key=p.key
        with patch.object(p,'edit_dialog',return_value=('verifikasi QC',None,None)):p.buttons['rev_unlock'].click();p.buttons['rev_reject'].click()
        self.assertEqual(self.repo.get(key)['status'],'REJECT');self.assertEqual(p.item['status'],'REJECT')
    def test_record_survives_restart(self):
        key=self.package('BOX','BOX-PERSIST');self.repo.unlock(key,'verifikasi QC');self.repo.change_status(key,'PENDING','cek ulang label');other=Store(self.store.path)
        try:self.assertEqual(RevisionRepository(other).get(key)['status'],'PENDING')
        finally:other.close()

    def test_rejected_unit_blocks_parent_from_next_aggregation(self):
        from agregasi.template_database import product_choices
        templates=TemplateRepository(self.store);aggregation=AggregationRuntime(self.store,templates)
        box=default_document('BOX');box.update(aggregation_max=1,child_product=product_choices(self.store)[0])
        box_id=templates.save(box);run=aggregation.start(box_id);run=aggregation.scan(run['id'],'UNIT-REJECT-CHILD')
        carton=default_document('CARTON');carton.update(child_template_id=box_id,aggregation_max=2)
        carton_id=templates.save(carton);target=aggregation.start(carton_id)
        unit=('UNIT','UNIT-REJECT-CHILD');self.repo.unlock(unit,'QC unit');self.repo.change_status(unit,'REJECT','unit rusak')
        with self.assertRaisesRegex(ValueError,'belum VALID'):aggregation.scan(target['id'],run['parent_code'])
        self.assertEqual(aggregation.get(target['id'])['quantity'],0)

    def test_trace_cards_follow_selected_unit_branch(self):
        a=self.make_run('ONE',['UNIT-ONE']);b=self.make_run('TWO',['UNIT-TWO']);c=self.package('CARTON','CTN-BOTH')
        self.store.link('BOX',a[1],c[1]);self.store.link('BOX',b[1],c[1]);self.window=MainWindow(self.store)
        p=self.window.pages['revision'];p.serial.setText('UNIT-TWO');p.search_now()
        p.key=('UNIT','UNIT-TWO');p.refresh()
        self.assertEqual(p.trace_path['BOX']['code'],b[1]);self.assertEqual(p.trace_path['CARTON']['code'],c[1])

if __name__=='__main__':unittest.main()
