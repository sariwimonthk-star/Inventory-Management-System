import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from storage import InventoryStore
from views.inventory_view import InventoryView


class PageStub:
    width = 1500

    def __init__(self):
        self.dialogs = []

    def update(self, *controls):
        self.dialogs = [dialog for dialog in self.dialogs if dialog.open]

    def show_dialog(self, dialog):
        dialog.open = True
        self.dialogs.append(dialog)

    def pop_dialog(self):
        self.dialogs.pop()


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'inventory.db'
        self.store = InventoryStore(self.path)

    def test_persistence_and_no_reseed_after_delete(self):
        self.store.adjust('P001', 3, 'delivery')
        self.assertEqual(InventoryStore(self.path).products()[0]['quantity'], 23)
        for p in self.store.products():
            self.store.delete(p['id'])
        self.assertEqual(InventoryStore(self.path).products(), [])
        self.assertEqual(len(self.store.history()), 6)

    def test_overdraw_is_atomic(self):
        with self.assertRaises(ValueError):
            self.store.adjust('P001', -21, 'order')
        self.assertEqual(self.store.products()[0]['quantity'], 20)
        self.assertEqual(self.store.history(), [])
        self.store.adjust('P001', -20, 'order')
        self.assertEqual(self.store.history()[0]['balance'], 0)

    def test_restock_card_includes_empty_stock_and_filters_both(self):
        import flet as ft
        page = PageStub()
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        self.assertEqual(view.summary_values['low_stock'].value, '2 รายการ')
        self.assertEqual(view.stock_breakdown.value, 'ใกล้หมด 1 · หมดแล้ว 1')
        card = view.summary_card('สินค้าที่ต้องเติม', view.summary_values['low_stock'], ft.Icons.WARNING, '#FFF3DD', '#C05621')
        card.content.on_click(None)
        self.assertEqual(view.active_nav, 'low_stock')
        view.filter_status('ต้องเติมสต็อก')
        self.assertEqual(len(view.table.rows), 2)
        self.store.adjust('P003', 10, 'restock')
        view.refresh_all()
        self.assertEqual(view.summary_values['low_stock'].value, '1 รายการ')
        self.assertEqual(len(view.table.rows), 1)
        self.assertIs(view.table.controls[0], view.table.header)
        self.assertIs(view.table.controls[1], view.table.body)
        self.assertEqual(len(view.table.body.controls), 1)

    def test_edit_cannot_change_id_or_history(self):
        p = self.store.products()[0]
        self.store.adjust(p['id'], 1, 'delivery')
        with self.assertRaises(ValueError):
            self.store.save({**p, 'id': 'NEW'}, 'P001')
        self.assertEqual(self.store.products()[0]['quantity'], 21)
        self.assertEqual(self.store.history()[0]['product_id'], 'P001')
        p['quantity'] = 25
        self.store.save(p, 'P001')
        self.assertEqual(self.store.history()[0]['delta'], 4)

    def test_generated_id_survives_delete_and_restart(self):
        product = {**self.store.products()[0], 'id': ''}
        self.assertEqual(self.store.save(product), 'P006')
        self.store.delete('P006')
        self.assertEqual(InventoryStore(self.path).save(product), 'P007')

    def test_failed_save_does_not_consume_number(self):
        product = {**self.store.products()[0], 'id': ''}
        with self.assertRaises(ValueError):
            self.store.save({**product, 'quantity': -1})
        self.assertEqual(self.store.save(product), 'P006')

    def test_sequence_migrates_deleted_legacy_ids(self):
        with self.store.connect() as db:
            db.execute("DROP TABLE product_sequence")
            db.execute("INSERT INTO movements(product_id,name,delta,balance,reason) VALUES ('P042','old',0,0,'deleted')")
        store = InventoryStore(self.path)
        self.assertEqual(store.save(store.products()[0]), 'P043')

    def test_concurrent_creates_have_unique_ids(self):
        from concurrent.futures import ThreadPoolExecutor
        product = self.store.products()[0]
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _: self.store.save(product), range(8)))
        self.assertEqual(len(set(ids)), 8)
        self.assertEqual(len(self.store.products()), 13)

    def test_invalid_values_rejected_without_writes(self):
        product = self.store.products()[0]
        for change in ({'quantity': 2**63}, {'quantity': 1.5}, {'quantity': True},
                       {'price': float('inf')}, {'price': float('nan')},
                       {'date': '31/02/2026'}, {'category': 'unknown'}, {'name': ''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.store.save({**product, **change})
        self.assertEqual(len(self.store.products()), 5)
        self.assertEqual(self.store.history(), [])
        with self.assertRaises(ValueError):
            self.store.adjust('P001', 2**63, 'too much')
        self.assertEqual(self.store.products()[0]['quantity'], 20)

    def test_default_database_migrates_outside_project_once(self):
        from storage import default_database_path
        legacy = Path(self.temp.name) / 'legacy'
        legacy.mkdir()
        old = InventoryStore(legacy / 'inventory.db')
        old.adjust('P001', 3, 'legacy delivery')
        local = Path(self.temp.name) / 'localappdata'
        with patch.dict('os.environ', {'LOCALAPPDATA': str(local), 'FLET_APP_STORAGE_DATA': str(legacy)}):
            target = default_database_path()
            self.assertTrue(target.is_relative_to(local))
            migrated = InventoryStore()
            self.assertEqual(migrated.products()[0]['quantity'], 23)
            self.assertEqual(len(migrated.history()), 1)
            migrated.adjust('P001', 2, 'new delivery')
            self.assertEqual(InventoryStore().products()[0]['quantity'], 25)
            self.assertEqual(old.products()[0]['quantity'], 23)

    def test_stale_edit_does_not_overwrite_stock_movement(self):
        before = self.store.products()[0]
        self.store.adjust(before['id'], 5, 'new delivery')
        with self.assertRaises(ValueError):
            self.store.save({**before, 'name': 'changed'}, before['id'], expected=before)
        self.assertEqual(self.store.products()[0]['quantity'], 25)
        self.assertEqual(len(self.store.history()), 1)

    def test_reopening_editor_loads_latest_stock(self):
        page = PageStub()
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        cached = view.products[0]
        self.store.adjust(cached['id'], 5, 'delivery')
        view.edit_product(cached)
        self.assertEqual(view.quantity_field.value, '25')
        view.name_field.value = 'Updated'
        view.save_edit(None)
        self.assertEqual(self.store.products()[0]['quantity'], 25)
        self.assertEqual(self.store.products()[0]['name'], 'Updated')

    def test_stock_movement_repeated_click_only_saves_once(self):
        page = PageStub()
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        view.open_movement(view.products[0])
        dialog = page.dialogs[-1]
        dialog.content.controls[2].value = '3'
        dialog.content.controls[3].value = 'delivery'
        save = dialog.actions[1].on_click
        save(None)
        save(None)
        self.assertEqual(self.store.products()[0]['quantity'], 23)
        self.assertEqual(len(self.store.history()), 1)

    def test_date_field_opens_picker_and_reopens_after_selection(self):
        from datetime import datetime
        from types import SimpleNamespace
        page = PageStub()
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        view.new_product(None)
        view.date_field.on_click(None)
        first = view.date_picker
        view.open_date_picker(None)
        self.assertIs(view.date_picker, first)
        first.value = datetime(2026, 9, 10)
        view.set_received_date(SimpleNamespace(control=first))
        self.assertEqual(view.date_field.value, '10/09/2026')
        view.open_date_picker(None)
        second = view.date_picker
        self.assertIsNot(second, first)
        self.assertEqual(second.value, datetime(2026, 9, 10))
        view.dismiss_date_picker(SimpleNamespace(control=second))
        view.open_date_picker(None)
        self.assertIsNot(view.date_picker, second)
        self.assertEqual(view.date_field.value, '10/09/2026')

    def test_dialog_field_updates_target_the_field(self):
        page = PageStub()
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        view.new_product(None)
        with patch.object(page, 'update') as update:
            view.quantity_field.value = '0'
            view.update_status_preview(None)
            update.assert_called_with(view.status_group)
            self.assertEqual(view.status_group.value, 'หมด')
            from datetime import datetime
            view.date_picker.value = datetime(2026, 9, 16)
            view.set_received_date(None)
            update.assert_called_with(view.date_field)

    def test_view_filters_form_reset_and_history(self):
        page = PageStub()
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        view.filter_status('ใกล้หมด')
        self.assertEqual(len(view.table.rows), 1)
        view.filter_status('ต้องเติมสต็อก')
        self.assertEqual(len(view.table.rows), 2)
        view.category_filter.value = 'เครื่องใช้ไฟฟ้า'
        view.status_filter.value = 'ทั้งหมด'
        view.refresh_all()
        self.assertEqual(len(view.table.rows), 1)
        view.search_field.value = 'no-such-product'
        view.refresh_all()
        self.assertEqual(len(view.table.rows), 0)
        view.edit_product(view.products[0])
        view.close_form()
        self.assertIsNone(view.editing_id)
        self.assertFalse(view.add_button.disabled)
        view.open_movement(view.products[0])
        page.pop_dialog()
        view.show_history(None)
        self.assertEqual(view.active_nav, "history")
        self.assertEqual(len(page.dialogs), 0)

    def test_resize_stops_updating_when_width_is_unchanged(self):
        page = PageStub()
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        with patch.object(type(view.table), 'update') as table_update, patch.object(page, 'update') as page_update:
            for _ in range(10):
                view.on_resize(None)
            table_update.assert_not_called()
            page.width = 1800
            view.on_resize(None)
            table_update.assert_called_once()
            for _ in range(10):
                view.on_resize(None)
            table_update.assert_called_once()
            page_update.assert_not_called()

    def test_success_closes_product_form_and_invalid_input_keeps_it(self):
        import flet as ft
        page = PageStub()
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        view.new_product(None)
        form = view.form_dialog
        view.add_product(None)
        self.assertTrue(form.open)
        page.pop_dialog()
        self.assertTrue(view.id_field.read_only)
        view.name_field.value = 'Fan'
        view.category_field.value = 'เครื่องใช้ไฟฟ้า'
        view.price_field.value = '599'
        view.quantity_field.value = '500'
        view.date_field.value = '15/09/2026'
        view.add_product(None)
        self.assertFalse(form.open)
        self.assertIsNone(view.form_dialog)
        self.assertIsInstance(page.dialogs[-1], ft.SnackBar)
        self.assertEqual(len(self.store.products()), 6)
        page.pop_dialog()
        view.edit_product(self.store.products()[-1])
        edit_form = view.form_dialog
        view.name_field.value = 'Updated Fan'
        view.save_edit(None)
        self.assertFalse(edit_form.open)
        self.assertIsNone(view.editing_id)
        self.assertEqual(self.store.products()[-1]['name'], 'Updated Fan')

    def test_real_flet_page_sends_close_patch_for_dialog(self):
        import weakref
        import flet as ft
        from unittest.mock import Mock

        session = Mock()
        page = ft.Page(sess=session)
        # Normally attached by the Flet session when the page is mounted.
        page._dialogs._parent = weakref.ref(page)
        with patch('views.inventory_view.InventoryStore', return_value=self.store):
            view = InventoryView(page)
        for save in (False, True):
            view.new_product(None)
            dialog = view.form_dialog
            sent_states = []
            session.patch_control.side_effect = lambda control: sent_states.append((control, getattr(control, 'open', None)))
            if save:
                self.assertTrue(view.id_field.read_only)
                view.name_field.value = 'Fan'
                view.category_field.value = 'เครื่องใช้ไฟฟ้า'
                view.price_field.value = '599'
                view.quantity_field.value = '500'
                view.date_field.value = '15/09/2026'
                view.add_product(None)
            else:
                dialog.actions[0].on_click(None)
            self.assertTrue(any(control is dialog and state is False for control, state in sent_states))
            self.assertIsNone(view.form_dialog)


if __name__ == '__main__':
    unittest.main()
