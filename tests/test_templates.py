import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import tempfile
import unittest

from PySide6.QtCore import QPointF,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtPrintSupport import QPrinter

from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.template_model import TemplateRepository,default_document,validate_document,new_element
from agregasi.label_render import check_renderable,render_image,export_pdf,UNITS


class TemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet((Path(__file__).resolve().parents[1]/'styles/theme.qss').read_text())
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.store=Store(self.path/'data.db')
        self.window=MainWindow(self.store);self.window.resize(1448,1086);self.window.show();self.window.navigate('template');self.app.processEvents();self.page=self.window.pages['template']
    def tearDown(self):
        for e in self.page.editors.values():
            e._data_dirty=False;e.canvas.undo.setClean()
            if e.identifier is None:e.identifier='discard-test-draft'
        self.window.close();self.store.close();self.tmp.cleanup();self.app.processEvents()
    def test_selectors_open_three_independent_drafts(self):
        box=self.page.editors['BOX'];carton=self.page.editors['CARTON'];pallet=self.page.editors['PALLET']
        self.assertEqual(self.page.stack.count(),3)
        self.page.selectors['BOX'].click();self.assertIs(self.page.stack.currentWidget(),box)
        before=deepcopy(pallet.document);box.canvas.add('text',text='BOX ONLY')
        self.page.selectors['PALLET'].click();self.assertIs(self.page.stack.currentWidget(),pallet);self.assertEqual(pallet.document,before)
        self.page.selectors['BOX'].click();self.assertEqual(box.document['elements'][-1]['text'],'BOX ONLY')
        self.assertEqual([e.document['prefix'] for e in (box,carton,pallet)],['BOX','CTN','PLT'])
        self.assertEqual([e.document['child_level'] for e in (box,carton,pallet)],['UNIT','BOX','CARTON'])
    def test_saved_document_survives_database_restart(self):
        e=self.page.active_editor;e.name_edit.setText('PALLET PRODUCTION');e.gtin.setText('12345678901234');e.apply_metadata();e.canvas.add('text',text='{{product_name}}')
        e.save();identifier=e.identifier;expected=deepcopy(e.document)
        other=Store(self.path/'data.db')
        try:self.assertEqual(TemplateRepository(other).get(identifier)['document'],expected)
        finally:other.close()
    def test_duplicate_delete_and_default_are_real_and_level_scoped(self):
        e=self.page.active_editor;original=e.identifier;e.duplicate_template();copy_id=e.identifier
        self.assertNotEqual(original,copy_id);self.assertEqual(len(self.page.repo.list('PALLET')),2)
        e.make_default();self.assertEqual([r['id'] for r in self.page.repo.list('PALLET') if r['is_default']],[copy_id])
        self.assertEqual(len([r for r in self.page.repo.list('BOX') if r['is_default']]),1)
        e.delete_template(confirmed=True);self.assertEqual(len(self.page.repo.list('PALLET')),1)
        with self.assertRaises(ValueError):self.page.repo.get(copy_id)
    def test_published_snapshot_is_retained_while_draft_changes(self):
        e=self.page.active_editor;e.publish();published=deepcopy(self.page.repo.get(e.identifier)['published_document'])
        e.canvas.add('text',text='DRAFT ONLY');e.save();row=self.page.repo.get(e.identifier)
        self.assertEqual(row['published_document'],published);self.assertNotEqual(row['published_document'],row['document']);self.assertEqual(row['revision'],1)
        e.publish();self.assertEqual(self.page.repo.get(e.identifier)['revision'],2)
    def test_import_export_round_trip_preserves_images_and_elements(self):
        e=self.page.editors['CARTON'];logo=render_image(default_document('BOX'),72);logo.save(str(self.path/'logo.png'))
        e.add_image(self.path/'logo.png');e.save();expected=deepcopy(e.document);count=len(self.page.repo.list())
        exported=e.export_template(self.path/'portable.json');identifier=self.page.import_template(exported)
        self.assertEqual(self.page.template_kind,'CARTON');self.assertEqual(len(self.page.repo.list()),count+1)
        self.assertEqual(self.page.repo.get(identifier)['document'],expected)
        self.assertTrue(any(x['type']=='image' and x['image'] for x in expected['elements']))
    def test_malformed_import_does_not_write_partial_template(self):
        count=len(self.page.repo.list());doc=default_document('BOX');doc['elements'][0]['x']=math.nan
        path=self.path/'bad.json';path.write_text(json.dumps({'format':'AGREGASI_LABEL_TEMPLATE','version':1,'document':doc}))
        with self.assertRaises(ValueError):self.page.import_template(path)
        self.assertEqual(len(self.page.repo.list()),count)
    def test_undo_redo_clipboard_and_alignment_change_real_objects(self):
        c=self.page.active_editor.canvas;doc=deepcopy(c.document);doc['elements']=[];c.set_document(doc)
        c.add('text',text='A');first=c.document['elements'][0]['id'];c.nudge(10,5);self.assertEqual(c.document['elements'][0]['x'],15)
        c.undo.undo();self.assertEqual(c.document['elements'][0]['x'],5);c.undo.redo();self.assertEqual(c.document['elements'][0]['x'],15)
        c.duplicate();self.assertEqual(len(c.document['elements']),2);second=c.selected_ids()[0];self.assertNotEqual(first,second)
        c.select_ids([first,second]);c.align('left');self.assertEqual(len({e['x'] for e in c.document['elements']}),1)
        c.cut();self.assertEqual(c.document['elements'],[]);c.paste();self.assertEqual(len(c.document['elements']),2)
        c.delete();self.assertEqual(c.document['elements'],[]);c.undo.undo();self.assertEqual(len(c.document['elements']),2)
    def test_canvas_mouse_drag_resize_and_undo(self):
        e=self.page.active_editor;c=e.canvas;doc=deepcopy(c.document);doc['elements']=[];c.set_document(doc);c.add('text',text='DRAG');self.app.processEvents()
        view=c.view;point=view.mapFromScene(QPointF(15*UNITS,9*UNITS));end=view.mapFromScene(QPointF(25*UNITS,14*UNITS))
        QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=point);QTest.mouseMove(view.viewport(),end,20);QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=end);self.app.processEvents()
        moved=deepcopy(c.document['elements'][0]);self.assertGreater(moved['x'],10);self.assertGreater(moved['y'],7)
        c.undo.undo();self.assertEqual(c.document['elements'][0]['x'],5);self.assertEqual(c.document['elements'][0]['y'],5)
        self.app.processEvents();obj=c.document['elements'][0];start=view.mapFromScene(QPointF((obj['x']+obj['w'])*UNITS-2,(obj['y']+obj['h'])*UNITS-2));end=start+view.mapFromScene(QPointF(8*UNITS,5*UNITS))-view.mapFromScene(QPointF(0,0))
        QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=start);QTest.mouseMove(view.viewport(),end,20);QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=end);self.app.processEvents()
        self.assertGreater(c.document['elements'][0]['w'],35);self.assertGreater(c.document['elements'][0]['h'],8)
        c.undo.undo();self.assertEqual(c.document['elements'][0]['w'],35)
    def test_properties_data_and_paper_size_affect_saved_design(self):
        e=self.page.active_editor;e.canvas.add('text',text='{{batch}}');e.object_text.setPlainText('{{product_name}}');e.font_size.setValue(10);e.object_color.setText('#123456');e.apply_properties()
        self.assertEqual(e.document['elements'][-1]['color'],'#123456')
        e.width_mm_edit.setValue(120);e.height_mm_edit.setValue(180);e.apply_metadata();self.assertEqual(e.document['width_mm'],120);validate_document(e.document)
        i=next(i for i in range(e.data_table.rowCount()) if e.data_table.item(i,0).text()=='product_name');e.data_table.item(i,1).setText('PRODUK BARU');e.apply_data();e.save()
        self.assertEqual(self.page.repo.get(e.identifier)['document']['data']['product_name'],'PRODUK BARU')
    def test_real_code128_qr_and_datamatrix_decode(self):
        try:import zxingcpp
        except ImportError:self.skipTest('Optional independent barcode decoder not installed.')
        from PIL import Image
        for kind in ('barcode','qr','datamatrix'):
            doc=default_document('BOX');doc['elements']=[new_element(kind,5,5,85 if kind=='barcode' else 45,25 if kind=='barcode' else 45,text='ABC-2026-0099')]
            path=self.path/(kind+'.png');render_image(doc).save(str(path));codes=zxingcpp.read_barcodes(Image.open(path))
            self.assertIn('ABC-2026-0099',[code.text for code in codes],kind)
    def test_pdf_and_printer_output_use_physical_label_dimensions(self):
        e=self.page.active_editor;doc=e.document;path=self.path/'label.pdf';export_pdf(doc,path)
        raw=path.read_bytes();self.assertTrue(raw.startswith(b'%PDF'))
        match=re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)',raw);self.assertIsNotNone(match)
        # Qt stores PDF page bounds in integer points: at most half a point
        # (0.177 mm) of rounding for a custom paper size.
        self.assertAlmostEqual(float(match[1])*25.4/72,100,delta=.18);self.assertAlmostEqual(float(match[2])*25.4/72,150,delta=.18)
        printer=QPrinter(QPrinter.PrinterMode.HighResolution);printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat);printer.setOutputFileName(str(self.path/'printer.pdf'))
        self.assertTrue(self.page.print_document(doc,e.identifier,printer=printer,confirm=False));self.assertTrue((self.path/'printer.pdf').read_bytes().startswith(b'%PDF'))
    def test_invalid_barcode_and_unbound_field_are_not_published(self):
        doc=default_document('BOX');doc['elements'].append(new_element('qr',1,1,10,10,text='{{missing}}'))
        with self.assertRaises(ValueError):check_renderable(doc)
        doc['elements'][-1]['text']='valid';doc['elements'][0]['w']=500
        with self.assertRaises(ValueError):validate_document(doc)
    def test_reset_canvas_is_undoable_and_preserves_metadata(self):
        e=self.page.active_editor;e.canvas.add('text',text='KEEP UNTIL RESET');before=deepcopy(e.document);e.reset_canvas(confirmed=True)
        self.assertNotEqual(e.document['elements'],before['elements']);self.assertEqual(e.document['name'],before['name']);e.canvas.undo.undo();self.assertEqual(e.document,before)

    def test_editor_menu_and_level_navigation_remain_independent(self):
        self.page.selectors['BOX'].click();editor=self.page.active_editor
        self.assertEqual([editor.tabs.tabText(i) for i in range(editor.tabs.count())],['Template','Objek','Data'])
        for index in (1,2,0):
            QTest.mouseClick(editor.tabs.tabBar(),Qt.MouseButton.LeftButton,pos=editor.tabs.tabBar().tabRect(index).center())
            self.assertEqual(editor.tabs.currentIndex(),index);self.assertEqual(self.page.template_kind,'BOX')
        self.page.selectors['CARTON'].click();self.assertEqual(self.page.template_kind,'CARTON')
        self.page.summary_buttons['PALLET'].click();self.assertEqual(self.page.template_kind,'PALLET')
        self.assertTrue(self.page.selectors['PALLET'].isChecked())
    def test_pagination_status_and_dashboard_use_persisted_rows(self):
        editor=self.page.active_editor
        for n in range(5):
            doc=default_document('PALLET');doc['name']='PRESET '+str(n);self.page.repo.save(doc)
        editor.refresh_list();self.assertEqual(len(editor.rows),4);self.assertTrue(editor.next_button.isEnabled())
        editor.next_button.click();self.assertEqual(len(editor.rows),2);self.assertFalse(editor.next_button.isEnabled())
        identifier=editor.rows[0]['id'];editor.choose_row(0,0);self.assertEqual(editor.identifier,identifier)
        row=next(i for i,r in enumerate(editor.rows) if r['id']==identifier);editor.toggle_active(row)
        self.assertFalse(self.page.repo.get(identifier)['document']['active'])
        metrics=self.page.sidebar_metrics();self.assertEqual(metrics['total'],8);self.assertEqual(metrics['active'],7)
        self.page.repo.record(identifier,'PALLET','PREVIEW','Pagination test')
        self.assertEqual(self.page.sidebar_metrics()['usage']['PALLET'],1)
    def test_child_serial_and_saved_design_are_linked_to_same_template(self):
        editor=self.page.active_editor;child=self.page.editors['CARTON'].identifier
        editor.child.setCurrentIndex(editor.child.findData(child));editor.serial_type.choices['UNIX'].click()
        editor.canvas.add('text',text='DESIGN OF THIS TEMPLATE');editor.nie.setText('NIE-TEST-009');editor.save()
        doc=self.page.repo.get(editor.identifier)['document']
        self.assertEqual(doc['child_template_id'],child);self.assertEqual(doc['serial_type'],'UNIX')
        self.assertEqual(doc['nie'],'NIE-TEST-009');self.assertEqual(doc['data']['nie'],'NIE-TEST-009')
        self.assertEqual(doc['elements'][-1]['text'],'DESIGN OF THIS TEMPLATE')
        self.assertFalse(hasattr(editor,'print_template'));self.assertNotIn('print_template_id',doc)

    def test_saved_gallery_paginates_five_templates_per_level(self):
        for level in ('BOX','CARTON','PALLET'):
            for n in range(11):
                doc=default_document(level);doc['name']=f'{level} LABEL {n+2:02}'
                self.page.repo.save(doc)
            self.page.select_level(level);self.app.processEvents();self.page.refresh_shared()
            editor=self.page.active_editor;before=deepcopy(editor.document);table_page=editor.list_page
            expected=[row['id'] for row in self.page.repo.list(level)];seen=[]
            for page_index,count in enumerate((5,5,2)):
                self.assertEqual(editor.preview_page,page_index);self.assertEqual(len(editor.thumbnails),count)
                self.assertEqual([t.identifier for t in editor.thumbnails],expected[page_index*5:page_index*5+count])
                self.assertEqual(editor.preview_previous.isEnabled(),page_index>0)
                self.assertEqual(editor.preview_next.isEnabled(),page_index<2)
                for thumb in editor.thumbnails:
                    self.assertEqual(thumb.document['level'],level);self.assertTrue(thumb.isVisible())
                    self.assertIsNotNone(thumb.image);seen.append(thumb.identifier)
                editor.preview_next.click()
            self.assertEqual(seen,expected);self.assertEqual(editor.preview_page,2)
            editor.preview_previous.click();self.assertEqual(editor.preview_page,1)
            self.assertEqual(editor.document,before);self.assertEqual(editor.list_page,table_page)
            # Table paging and gallery paging must not reset each other.
            editor.next_button.click();self.assertEqual(editor.preview_page,1)
        for level in ('BOX','CARTON','PALLET'):
            self.page.select_level(level);self.assertEqual(self.page.active_editor.preview_page,1)

    def test_saved_gallery_handles_empty_five_and_six_templates(self):
        editor=self.page.active_editor
        self.page.repo.delete(editor.identifier);self.page.refresh_shared()
        self.assertEqual(editor.thumbnails,[]);self.assertTrue(editor.preview_empty.isVisible())
        self.assertEqual(editor.preview_cache,{});self.assertTrue(editor.preview_next.isHidden())
        for count in range(1,7):
            doc=default_document('PALLET');doc['name']=f'SAVED {count}'
            self.page.repo.save(doc);self.page.refresh_shared()
            self.assertFalse(editor.preview_empty.isVisible());self.assertEqual(len(editor.thumbnails),min(count,5))
            self.assertEqual(editor.preview_next.isVisible(),count>5)
        editor.preview_next.click();self.assertEqual(len(editor.thumbnails),1)
        removed=editor.thumbnails[0].identifier;self.page.repo.delete(removed);self.page.refresh_shared()
        self.assertEqual(editor.preview_page,0);self.assertEqual(len(editor.thumbnails),5)
        self.assertNotIn(removed,editor.preview_cache);self.assertTrue(editor.preview_next.isHidden())
        for row in self.page.repo.list('PALLET'):self.page.repo.delete(row['id'])
        self.page.refresh_shared();self.assertEqual(editor.thumbnails,[])
        self.assertTrue(all(t.isHidden() and t.image is None for t in editor._thumbnail_slots))

    def test_saved_gallery_ignores_draft_and_updates_after_save(self):
        editor=self.page.active_editor;identifier=editor.identifier
        saved=deepcopy(self.page.repo.get(identifier)['document']);image_key=editor.thumbnails[0].image.cacheKey()
        editor.canvas.add('text',text='BELUM DISIMPAN');editor.name_edit.setText('DRAFT PALLET');editor.apply_metadata()
        self.page.refresh_shared()
        self.assertEqual(editor.thumbnails[0].document,saved)
        self.assertEqual(editor.thumbnails[0].image.cacheKey(),image_key)
        editor.save();self.page.refresh_shared()
        self.assertEqual(editor.thumbnails[0].document,editor.document)
        self.assertNotEqual(editor.thumbnails[0].image.cacheKey(),image_key)
        self.assertIn('DRAFT PALLET',editor.thumbnails[0].toolTip())
        editor.new_template();self.page.refresh_shared()
        self.assertEqual(len(editor.thumbnails),1);self.assertFalse(editor.thumbnails[0].current)
        editor.name_edit.setText('NEW SAVED PALLET');editor.save();self.page.refresh_shared()
        self.assertEqual(len(editor.thumbnails),2)
        self.assertEqual([t.identifier for t in editor.thumbnails if t.current],[editor.identifier])

    def test_saved_gallery_click_loads_template_and_respects_unsaved_cancel(self):
        from unittest.mock import patch
        editor=self.page.active_editor;original=editor.identifier
        for n in range(6):
            doc=default_document('PALLET');doc['name']=f'OTHER PALLET {n}'
            self.page.repo.save(doc)
        editor.refresh_previews();editor.preview_next.click();target=editor.thumbnails[0].identifier
        editor.canvas.add('text',text='UNSAVED');before=deepcopy(editor.document)
        with patch.object(editor,'confirm_discard',return_value=False):editor.thumbnails[0].click()
        self.assertEqual(editor.identifier,original);self.assertEqual(editor.document,before)
        with patch.object(editor,'confirm_discard',return_value=True):editor.thumbnails[0].click()
        self.assertEqual(editor.identifier,target);self.assertFalse(editor.dirty)
        self.assertEqual(editor.document,self.page.repo.get(target)['document'])
        self.assertEqual([t.identifier for t in editor.thumbnails if t.current],[target])
        self.assertEqual(editor.preview_page,1)

    def test_preview_fits_on_resize_without_scrollbars(self):
        from agregasi.template_page import PreviewDialog
        from PySide6.QtWidgets import QScrollBar
        from PySide6.QtCore import QRectF
        for level in ('BOX','PALLET'):
            editor=self.page.editors[level];dialog=PreviewDialog(self.page,editor.document,editor.identifier)
            dialog.show();self.app.processEvents()
            self.assertIs(dialog.parentWidget(),self.window);self.assertIsNone(dialog.graphicsProxyWidget())
            for width,height in ((460,340),(900,620),(600,720)):
                dialog.resize(width,height);self.app.processEvents();dialog.grab()
                target=dialog.preview.target
                self.assertTrue(QRectF(dialog.preview.rect()).contains(target))
                self.assertAlmostEqual(target.width()/target.height(),editor.document['width_mm']/editor.document['height_mm'],delta=.02)
                self.assertFalse(dialog.findChildren(QScrollBar))
            dialog.close()

    def test_delete_dialog_can_cancel_and_confirm_without_proxy(self):
        from agregasi.ui_dialogs import NotificationDialog,MessageBox
        editor=self.page.active_editor;identifier=editor.identifier
        def choose(code):
            dialog=next(w for w in self.app.topLevelWidgets() if isinstance(w,NotificationDialog) and w.isVisible())
            self.assertIs(dialog.parentWidget(),self.window);self.assertIsNone(dialog.graphicsProxyWidget())
            self.assertIn(editor.document['name'],dialog.message_label.text());dialog.buttons[code].click()
        QTimer.singleShot(0,lambda:choose(MessageBox.StandardButton.No))
        self.assertFalse(editor.delete_template());self.assertEqual(editor.identifier,identifier)
        QTimer.singleShot(0,lambda:choose(MessageBox.StandardButton.Yes))
        self.assertTrue(editor.delete_template())
        with self.assertRaises(ValueError):self.page.repo.get(identifier)

    def test_unsaved_dialog_and_paper_dialog_use_real_window(self):
        from agregasi.ui_dialogs import NotificationDialog,MessageBox
        editor=self.page.active_editor;editor.canvas.add('text',text='UNSAVED')
        for choice,expected in ((MessageBox.StandardButton.Cancel,False),(MessageBox.StandardButton.Save,True)):
            def choose(c=choice):
                dialog=next(w for w in self.app.topLevelWidgets() if isinstance(w,NotificationDialog) and w.isVisible())
                self.assertIsNone(dialog.graphicsProxyWidget());dialog.buttons[c].click()
            QTimer.singleShot(0,choose);self.assertEqual(editor.confirm_discard(),expected)
        self.assertFalse(editor.dirty)
        editor.paper_dialog.show();self.app.processEvents()
        self.assertIs(editor.paper_dialog.parentWidget(),self.window);self.assertIsNone(editor.paper_dialog.graphicsProxyWidget());editor.paper_dialog.close()

    def test_product_name_and_nie_update_bindings_and_survive_restart(self):
        from agregasi.template_model import resolve_text
        editor=self.page.editors['BOX'];self.page.select_level('BOX')
        editor.product_name.setText('PRODUK UNIT BARU');editor.nie.setText('NIE-009');editor.save()
        self.assertEqual(editor.child_product.currentData()['id'],'CURRENT-PRODUCT')
        self.assertEqual(editor.child_product.currentText(),self.store.get('product'))
        self.assertEqual(resolve_text('{{product_name}} / {{nie}}',editor.document),'PRODUK UNIT BARU / NIE-009')
        other=Store(self.path/'data.db')
        try:
            doc=TemplateRepository(other).get(editor.identifier)['document']
            self.assertEqual(doc['child_product']['id'],'CURRENT-PRODUCT');self.assertEqual(doc['nie'],'NIE-009')
        finally:other.close()

    def test_database_schema_orders_fields_and_marks_missing_immediately(self):
        self.store.db.execute('CREATE TABLE source_product (product_name TEXT, nie TEXT, gtin TEXT, batch TEXT, custom_column TEXT)')
        self.store.configure({'template_data_source':{'path':str(self.store.path),'table':'source_product'}})
        editor=self.page.active_editor;editor.refresh_field_schema()
        keys=[editor.data_table.item(i,0).text() for i in range(editor.data_table.rowCount())]
        self.assertEqual(keys[:5],['product_name','nie','gtin','batch','custom_column'])
        self.assertEqual(editor.data_table.item(0,0).data(Qt.ItemDataRole.UserRole),'matched')
        row=keys.index('quantity');self.assertEqual(editor.data_table.item(row,0).data(Qt.ItemDataRole.UserRole),'missing')
        editor.data_table.item(0,0).setText('missing_name')
        self.assertEqual(editor.data_table.item(0,0).data(Qt.ItemDataRole.UserRole),'missing')
        editor.data_table.item(0,0).setText('product_name')
        self.assertEqual(editor.data_table.item(0,0).data(Qt.ItemDataRole.UserRole),'matched')
        editor.data_table.item(4,1).setText('EXTRA');editor.save()
        self.assertEqual(self.page.repo.get(editor.identifier)['document']['data']['custom_column'],'EXTRA')

    def test_external_schema_is_read_only_and_unavailable_is_not_a_match(self):
        import sqlite3,hashlib
        from agregasi.template_database import columns
        path=self.path/'external.db'
        with sqlite3.connect(path) as db:db.execute('CREATE TABLE product (nie TEXT, product_name TEXT)')
        before=hashlib.sha256(path.read_bytes()).digest()
        self.store.configure({'template_data_source':{'path':str(path),'table':'product'}})
        self.assertEqual([c['name'] for c in columns(self.store)],['nie','product_name'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),before)
        editor=self.page.active_editor;editor.refresh_field_schema();path.unlink();editor.refresh_field_schema()
        self.assertTrue(editor.schema_error)
        self.assertTrue(all(editor.data_table.item(i,0).data(Qt.ItemDataRole.UserRole)=='pending' for i in range(editor.data_table.rowCount())))

    def test_source_dialog_persists_real_table_selection(self):
        from agregasi.template_database import DatabaseSourceDialog
        self.store.db.execute('CREATE TABLE product_source (product_name TEXT, nie TEXT)')
        dialog=DatabaseSourceDialog(self.store,self.page);dialog.table.setCurrentText('product_source');dialog.apply()
        self.assertEqual(self.store.get('template_data_source')['table'],'product_source')
        self.assertEqual(dialog.grid.rowCount(),2)

    def test_dropdown_and_shortcuts_have_padding(self):
        from agregasi.ui_controls import ThemedComboBox
        from PySide6.QtCore import QRect
        for page in self.window.pages.values():
            for combo in page.findChildren(ThemedComboBox):
                self.assertIn('QAbstractItemView::item',combo.styleSheet())
        self.page.select_level('CARTON');combo=self.page.active_editor.child
        combo.showPopup();self.app.processEvents();self.assertGreaterEqual(combo.view().height(),36);combo.hidePopup()
        from agregasi.sidebar_layout import map_sidebar_rect, TEMPLATE_SOURCE
        panel=map_sidebar_rect(QRect(1102,936,322,50), TEMPLATE_SOURCE)
        for button in self.page.shortcut_buttons.values():self.assertTrue(panel.adjusted(4,15,-4,-4).contains(button.geometry()))

    def test_child_combo_and_carton_mode_are_exclusive_and_persisted(self):
        self.store.db.execute("INSERT INTO aggregation_products VALUES('P2','PRODUK CHILD KEDUA')");self.store.db.commit()
        editor=self.page.editors['CARTON'];self.page.select_level('CARTON')
        editor.child_mode.choices['UNIT'].click();self.assertTrue(editor.child_mode.choices['UNIT'].isChecked());self.assertFalse(editor.child_mode.choices['BOX'].isChecked())
        index=next(i for i in range(editor.child_product.count()) if (editor.child_product.itemData(i) or {}).get('id')=='P2')
        editor.child_product.setCurrentIndex(index);editor.target_min.setValue(4);editor.target_max.setValue(10);editor.print_mode.setCurrentText('AUTO');editor.save()
        doc=self.page.repo.get(editor.identifier)['document'];self.assertEqual(doc['child_product']['id'],'P2');self.assertEqual(doc['child_level'],'UNIT');self.assertIsNone(doc['child_template_id'])
        self.assertEqual((doc['aggregation_min'],doc['aggregation_max'],doc['print_mode']),(4,10,'AUTO'))
        editor.child_mode.choices['BOX'].click();editor.child.setCurrentIndex(editor.child.findData(self.page.editors['BOX'].identifier));editor.save()
        doc=self.page.repo.get(editor.identifier)['document'];self.assertEqual(doc['child_level'],'BOX');self.assertIsNone(doc['child_product'])
        self.assertEqual(doc['child_template_id'],self.page.editors['BOX'].identifier)
        row=self.store.db.execute('SELECT * FROM template_agregasi WHERE template_id=?',(editor.identifier,)).fetchone();self.assertEqual(row['target_max'],10);self.assertIsNone(row['child_product_id'])

    def test_operation_auto_and_manual_use_saved_settings(self):
        editor=self.page.editors['BOX'];editor.target_max.setValue(2);editor.print_mode.setCurrentText('AUTO');editor.save()
        operation=self.window.pages['box'];self.window.navigate('box');operation.refresh();self.app.processEvents();self.assertTrue(operation.template_selector.isVisible());printed=[]
        operation.print_callback=lambda doc,identifier,automatic:printed.append((doc,identifier,automatic)) or True
        operation.template_selector.setCurrentIndex(operation.template_selector.findData(editor.identifier))
        for code in ('QA-U1','QA-U2'):
            operation.scan_input.setText(code);operation.scan()
        self.assertEqual(len(printed),1);self.assertTrue(printed[0][2]);self.assertEqual(printed[0][0]['data']['quantity'],'2 UNIT')
        editor.print_mode.setCurrentText('MANUAL');editor.target_max.setValue(1);editor.save()
        operation.local_action('stage_reset');operation.template_selector.setCurrentIndex(operation.template_selector.findData(editor.identifier));operation.scan_input.setText('QA-U3');operation.scan();self.assertEqual(len(printed),1)
        operation.local_action('stage_print_label');self.assertEqual(len(printed),2);self.assertFalse(printed[1][2])

    def test_toolbar_grid_snap_zoom_and_layer_actions(self):
        editor=self.page.active_editor;canvas=editor.canvas
        editor.grid_button.click();editor.snap_button.click();self.assertFalse(canvas.grid);self.assertFalse(canvas.snap)
        initial=canvas.view.transform().m11();editor.step_zoom(1);self.assertGreater(canvas.view.transform().m11(),initial)
        doc=deepcopy(canvas.document);doc['elements']=[new_element('text',x,5,10,5,text=str(x)) for x in (5,17,65)];canvas.set_document(doc);canvas.select_all();canvas.distribute(True)
        positions=[e['x'] for e in canvas.document['elements']];self.assertAlmostEqual(positions[1]-positions[0],positions[2]-positions[1])
        selected=canvas.document['elements'][0]['id'];canvas.select_ids([selected]);canvas.reorder(True);self.assertEqual(canvas.document['elements'][-1]['id'],selected)
    def test_history_search_and_refresh_shutdown(self):
        from PySide6.QtWidgets import QLineEdit,QTableWidget
        self.page.repo.record(None,'BOX','PREVIEW','FIND THIS UNIQUE TEMPLATE');observed=[]
        def inspect():
            dialog=self.page.history_dialog;dialog.findChild(QLineEdit).setText('FIND THIS UNIQUE TEMPLATE')
            observed.append(dialog.findChild(QTableWidget).rowCount());dialog.accept()
        QTimer.singleShot(0,inspect);self.page.history_button.click();self.assertEqual(observed,[1])
        self.window.close();self.assertFalse(self.page.live_timer.isActive());self.assertFalse(self.page.refresh_timer.isActive())
    def test_visible_action_labels_and_list_fit_their_layout(self):
        from PySide6.QtGui import QFontMetrics
        from agregasi.template_style import GlassButton
        from agregasi.typography import ui_font
        editor=self.page.active_editor
        for button in editor.findChildren(GlassButton):
            if not button.text():continue
            font=ui_font(button.font_size);icon_width=button.iconSize().width() if not button.icon().isNull() else 0
            available=button.width()-14-icon_width-(6 if icon_width else 0)
            while QFontMetrics(font).horizontalAdvance(button.text())>available and font.pixelSize()>8:font.setPixelSize(font.pixelSize()-1)
            self.assertLessEqual(QFontMetrics(font).horizontalAdvance(button.text()),available,button.text())
        self.assertEqual(editor.list_table.horizontalScrollBar().maximum(),0)
        self.assertGreaterEqual(editor.list_table.y()+self.page.stack.y(),782)


if __name__=='__main__':unittest.main()
