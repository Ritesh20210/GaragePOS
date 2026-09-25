import flet as ft
import sqlite3
import os
import tempfile
import traceback
from datetime import datetime

def main(page: ft.Page):
    try:
        # --- 1. APP SETUP ---
        page.title = "Mama Bhanja Autowork Shop ERP"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0
        
        # --- 2. SECURE DATABASE ---
        db_folder = os.environ.get("HOME", tempfile.gettempdir())
        db_path = os.path.join(db_folder, "garage_pos_v6.db")
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT UNIQUE, cost_price REAL, selling_price REAL, stock INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, mobile TEXT, gadi_no TEXT, due_amount REAL DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, mobile TEXT, due_amount REAL DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, client_info TEXT, final_amount REAL, paid REAL, due REAL, date TEXT, month TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_id INTEGER, supplier_info TEXT, total_cost REAL, paid REAL, due REAL, date TEXT, month TEXT)''')
        
        # NEW TABLE FOR SHOP SETTINGS
        cursor.execute('''CREATE TABLE IF NOT EXISTS shop_settings (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_name TEXT, address TEXT, mobile TEXT)''')
        cursor.execute("SELECT * FROM shop_settings")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO shop_settings (shop_name, address, mobile) VALUES (?, ?, ?)", ("MAMA BHANJA AUTOWORK SHOP", "Biratnagar, Nepal", "+977-"))
        
        conn.commit()

        # --- 3. STATE & SNACKBAR ---
        app_state = {"edit_item_id": None}

        def show_snack(text, is_error=False):
            color = ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700
            snack = ft.SnackBar(content=ft.Text(text, color=ft.Colors.WHITE), bgcolor=color)
            if hasattr(page, 'open'): page.open(snack)
            else: page.snack_bar = snack; page.snack_bar.open = True; page.update()

        def custom_btn(text, icon, color, on_click):
            return ft.Container(
                content=ft.Row([ft.Icon(icon, color=ft.Colors.WHITE), ft.Text(text, color=ft.Colors.WHITE, size=16, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
                bgcolor=color, height=50, border_radius=8, ink=True, on_click=on_click
            )

        def data_card(title, subtitle, trailing):
            return ft.Card(
                elevation=2,
                content=ft.Container(
                    padding=10,
                    content=ft.Row([
                        ft.Column([
                            ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                            ft.Text(subtitle, size=13, color=ft.Colors.GREEN_700)
                        ], expand=True), 
                        trailing
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
            )

        # --- 4. UI VARIABLES ---
        sales_cart = []
        purchase_cart = []

        # Product Menu
        edit_inv_name = ft.TextField(label="Item Name", prefix_icon=ft.Icons.BUILD)
        edit_inv_cp = ft.TextField(label="Cost (₹)", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        edit_inv_sp = ft.TextField(label="Sell (₹)", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        edit_inv_qty = ft.TextField(label="Stock", keyboard_type=ft.KeyboardType.NUMBER, width=100)
        product_list = ft.ListView(expand=True, spacing=5)

        # Bulk Purchase
        pos_supplier_dropdown = ft.Dropdown(label="Select Supplier", expand=True)
        pur_item_name = ft.TextField(label="Product Name", prefix_icon=ft.Icons.BUILD, expand=True)
        pur_cost_price = ft.TextField(label="Cost Price (₹)", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        pur_sell_price = ft.TextField(label="Selling Price (₹)", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        pur_stock = ft.TextField(label="Qty", keyboard_type=ft.KeyboardType.NUMBER, width=80)
        pur_paid_amount = ft.TextField(label="Cash Paid to Supplier (₹)", value="0", keyboard_type=ft.KeyboardType.NUMBER, border_color=ft.Colors.BLUE_700)
        purchase_cart_list = ft.ListView(expand=True, spacing=10)
        pur_total_text = ft.Text("Bulk Total: ₹ 0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)

        # Clients & Suppliers
        client_name = ft.TextField(label="Client Name * (Mandatory)", prefix_icon=ft.Icons.PERSON)
        client_mobile = ft.TextField(label="Mobile No. (Optional)", keyboard_type=ft.KeyboardType.PHONE, prefix_icon=ft.Icons.PHONE)
        client_gadi = ft.TextField(label="Vehicle No. (Optional)", prefix_icon=ft.Icons.DIRECTIONS_CAR)
        client_list = ft.ListView(expand=True, spacing=10)
        
        sup_name = ft.TextField(label="Supplier Name * (Mandatory)", prefix_icon=ft.Icons.BUSINESS)
        sup_mobile = ft.TextField(label="Mobile No. (Optional)", keyboard_type=ft.KeyboardType.PHONE, prefix_icon=ft.Icons.PHONE)
        supplier_list = ft.ListView(expand=True, spacing=10)

        # POS Billing
        pos_client_dropdown = ft.Dropdown(label="Select Client")
        pos_item_dropdown = ft.Dropdown(label="Select Item", expand=True)
        pos_qty = ft.TextField(label="Qty", value="1", width=80, keyboard_type=ft.KeyboardType.NUMBER)
        pos_discount_type = ft.Dropdown(label="Disc.", options=[ft.dropdown.Option("₹"), ft.dropdown.Option("%")], value="₹", width=80)
        pos_discount_value = ft.TextField(label="Discount", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        pos_paid_amount = ft.TextField(label="Cash Received (₹)", value="0", keyboard_type=ft.KeyboardType.NUMBER, border_color=ft.Colors.GREEN_700)
        sales_cart_list = ft.ListView(expand=True, spacing=10)
        total_text = ft.Text("Total: ₹ 0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)
        due_text = ft.Text("Credit (Udhaar): ₹ 0", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700)
        
        # Reports
        report_dropdown = ft.Dropdown(label="Select Report Type", options=[
            ft.dropdown.Option("Today's Sales"), ft.dropdown.Option("Monthly Sales Summary"), 
            ft.dropdown.Option("Purchase Bills"), ft.dropdown.Option("Client Ledger (Dues)"), ft.dropdown.Option("Supplier Ledger (Dues)")
        ], value="Today's Sales")
        reports_list = ft.ListView(expand=True, spacing=10)

        # Settings
        set_shop_name = ft.TextField(label="Shop Name", prefix_icon=ft.Icons.STORE, border_color=ft.Colors.BLUE_700)
        set_shop_address = ft.TextField(label="Address", prefix_icon=ft.Icons.LOCATION_ON)
        set_shop_mobile = ft.TextField(label="Mobile Number", prefix_icon=ft.Icons.PHONE)

        # --- 5. DATA REFRESH ---
        def refresh_data():
            cur = conn.cursor()
            
            # Load Shop Settings
            cur.execute("SELECT shop_name, address, mobile FROM shop_settings WHERE id=1")
            s_row = cur.fetchone()
            if s_row:
                set_shop_name.value, set_shop_address.value, set_shop_mobile.value = s_row[0], s_row[1], s_row[2]
            
            # Products
            product_list.controls.clear()
            pos_item_dropdown.options.clear()
            product_list.controls.append(
                ft.Container(
                    bgcolor=ft.Colors.BLUE_100, padding=10, border_radius=5,
                    content=ft.Row([
                        ft.Text("Item", weight=ft.FontWeight.BOLD, expand=3, color=ft.Colors.BLACK),
                        ft.Text("CP", weight=ft.FontWeight.BOLD, width=45, color=ft.Colors.BLACK),
                        ft.Text("SP", weight=ft.FontWeight.BOLD, width=45, color=ft.Colors.BLACK),
                        ft.Text("Qty", weight=ft.FontWeight.BOLD, width=50, color=ft.Colors.BLACK),
                        ft.Text("Act", weight=ft.FontWeight.BOLD, width=60, text_align=ft.TextAlign.CENTER, color=ft.Colors.BLACK)
                    ])
                )
            )
            
            cur.execute("SELECT id, item_name, cost_price, selling_price, stock FROM inventory ORDER BY item_name ASC")
            for row in cur.fetchall():
                stock_val = row[4]
                stock_color = ft.Colors.RED_700 if stock_val <= 5 else ft.Colors.BLUE_900
                stock_icon = " ⚠️" if stock_val <= 5 else ""

                table_row = ft.Container(
                    padding=5,
                    content=ft.Column([
                        ft.Row([
                            ft.Text(row[1], expand=3, size=14, color=ft.Colors.BLACK_87),
                            ft.Text(str(row[2]), width=45, size=13, color=ft.Colors.GREY_800),
                            ft.Text(str(row[3]), width=45, size=13, color=ft.Colors.GREEN_700),
                            ft.Text(f"{stock_val}{stock_icon}", width=50, size=14, weight=ft.FontWeight.BOLD, color=stock_color),
                            ft.Row([
                                ft.IconButton(ft.Icons.EDIT, icon_color=ft.Colors.BLUE, icon_size=18, padding=0, width=30, on_click=lambda e, r=row: edit_item_setup(r)),
                                ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, icon_size=18, padding=0, width=30, on_click=lambda e, i=row[0]: delete_item(i))
                            ], width=60, spacing=0, alignment=ft.MainAxisAlignment.END)
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Divider(height=1, color=ft.Colors.GREY_300)
                    ], spacing=0)
                )
                product_list.controls.append(table_row)
                pos_item_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=f"{row[1]} - ₹{row[3]} (Stock: {stock_val})"))

            # Clients
            client_list.controls.clear()
            pos_client_dropdown.options.clear()
            cur.execute("SELECT id, name, mobile, gadi_no, due_amount FROM clients")
            for row in cur.fetchall():
                due_info = f"Udhaar: ₹{row[4]}" if row[4] > 0 else "Clear"
                action = ft.IconButton(ft.Icons.MONEY, icon_color=ft.Colors.GREEN, tooltip="Clear Due", on_click=lambda e, cid=row[0], n=row[1]: settle_client_due(cid, n)) if row[4] > 0 else ft.Container()
                client_list.controls.append(data_card(f"{row[1]} ({row[3]})", f"{row[2]} | {due_info}", action))
                pos_client_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=f"{row[1]}"))
                
            # Suppliers
            supplier_list.controls.clear()
            pos_supplier_dropdown.options.clear()
            cur.execute("SELECT id, name, mobile, due_amount FROM suppliers")
            for row in cur.fetchall():
                due_info = f"We Owe: ₹{row[3]}" if row[3] > 0 else "Clear"
                action = ft.IconButton(ft.Icons.MONEY, icon_color=ft.Colors.GREEN, tooltip="Pay Supplier", on_click=lambda e, sid=row[0], n=row[1]: settle_supplier_due(sid, n)) if row[3] > 0 else ft.Container()
                supplier_list.controls.append(data_card(row[1], f"{row[2]} | {due_info}", action))
                pos_supplier_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=f"{row[1]}"))
                
            if report_dropdown.value: refresh_reports(None)
            page.update()

        # --- PRODUCT LOGIC ---
        def add_or_update_product(e):
            if edit_inv_name.value and edit_inv_cp.value and edit_inv_sp.value and edit_inv_qty.value and app_state["edit_item_id"]:
                cur = conn.cursor()
                cur.execute("UPDATE inventory SET item_name=?, cost_price=?, selling_price=?, stock=? WHERE id=?", 
                            (edit_inv_name.value, float(edit_inv_cp.value), float(edit_inv_sp.value), int(edit_inv_qty.value), app_state["edit_item_id"]))
                conn.commit()
                edit_inv_name.value, edit_inv_cp.value, edit_inv_sp.value, edit_inv_qty.value = "", "", "", ""
                app_state["edit_item_id"] = None
                refresh_data(); show_snack("Product Updated!")
            elif edit_inv_name.value and edit_inv_cp.value and edit_inv_sp.value and edit_inv_qty.value:
                cur = conn.cursor()
                cur.execute("INSERT INTO inventory (item_name, cost_price, selling_price, stock) VALUES (?, ?, ?, ?)", 
                            (edit_inv_name.value, float(edit_inv_cp.value), float(edit_inv_sp.value), int(edit_inv_qty.value)))
                conn.commit()
                edit_inv_name.value, edit_inv_cp.value, edit_inv_sp.value, edit_inv_qty.value = "", "", "", ""
                refresh_data(); show_snack("New Product Added!")

        def edit_item_setup(row):
            app_state["edit_item_id"] = row[0]
            edit_inv_name.value, edit_inv_cp.value, edit_inv_sp.value, edit_inv_qty.value = row[1], str(row[2]), str(row[3]), str(row[4])
            show_snack("Editing Product. Modify details above and click Save.", is_error=False); page.update()

        def delete_item(item_id):
            conn.cursor().execute("DELETE FROM inventory WHERE id=?", (item_id,)); conn.commit(); refresh_data(); show_snack("Product Deleted!")

        # --- BULK PURCHASE LOGIC ---
        def add_to_purchase_cart(e):
            if pur_item_name.value and pur_cost_price.value and pur_sell_price.value and pur_stock.value:
                purchase_cart.append({
                    "name": pur_item_name.value, "cp": float(pur_cost_price.value), "sp": float(pur_sell_price.value), "qty": int(pur_stock.value)
                })
                pur_item_name.value, pur_cost_price.value, pur_sell_price.value, pur_stock.value = "", "", "", ""
                update_purchase_ui()

        def update_purchase_ui(e=None):
            purchase_cart_list.controls.clear()
            subtotal = sum([item['cp'] * item['qty'] for item in purchase_cart])
            for item in purchase_cart:
                purchase_cart_list.controls.append(ft.Text(f"• {item['name']} (x{item['qty']}) = ₹ {item['cp'] * item['qty']}"))
            pur_total_text.value = f"Bulk Total: ₹ {subtotal}"
            page.update()

        def confirm_bulk_purchase(e):
            if not pos_supplier_dropdown.value or not purchase_cart: return show_snack("Select Supplier and add items!", is_error=True)
            sup_id = int(pos_supplier_dropdown.value)
            cur = conn.cursor()
            cur.execute("SELECT name FROM suppliers WHERE id=?", (sup_id,))
            sup_name_str = cur.fetchone()[0]
            
            subtotal = sum([item['cp'] * item['qty'] for item in purchase_cart])
            try: paid_val = float(pur_paid_amount.value or 0)
            except: paid_val = 0
            due = subtotal - paid_val
            if due < 0: due = 0

            for item in purchase_cart:
                cur.execute("SELECT id, stock FROM inventory WHERE item_name=? COLLATE NOCASE", (item['name'],))
                existing = cur.fetchone()
                if existing:
                    cur.execute("UPDATE inventory SET stock=stock+?, cost_price=?, selling_price=? WHERE id=?", (item['qty'], item['cp'], item['sp'], existing[0]))
                else:
                    cur.execute("INSERT INTO inventory (item_name, cost_price, selling_price, stock) VALUES (?, ?, ?, ?)", (item['name'], item['cp'], item['sp'], item['qty']))

            cur.execute("UPDATE suppliers SET due_amount = due_amount + ? WHERE id=?", (due, sup_id))
            cur.execute("INSERT INTO purchases (supplier_id, supplier_info, total_cost, paid, due, date, month) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (sup_id, sup_name_str, subtotal, paid_val, due, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m")))
            
            conn.commit(); purchase_cart.clear(); pur_paid_amount.value = "0"
            update_purchase_ui(); refresh_data(); show_snack("Bulk Purchase Saved & Stock Instantly Updated!")

        # --- SETTINGS LOGIC ---
        def save_shop_settings(e):
            cur = conn.cursor()
            cur.execute("UPDATE shop_settings SET shop_name=?, address=?, mobile=? WHERE id=1", 
                        (set_shop_name.value, set_shop_address.value, set_shop_mobile.value))
            conn.commit()
            show_snack("Shop Details Updated! Will reflect in next invoice.")

        # --- CLIENT & SUPPLIER ACTIONS ---
        def add_client(e):
            if client_name.value: 
                conn.cursor().execute("INSERT INTO clients (name, mobile, gadi_no, due_amount) VALUES (?, ?, ?, 0)", (client_name.value, client_mobile.value or "", client_gadi.value or ""))
                conn.commit(); client_name.value, client_mobile.value, client_gadi.value = "", "", ""; refresh_data(); show_snack("Client Added!")
            else: show_snack("Client Name is mandatory!", is_error=True)
            
        def add_supplier(e):
            if sup_name.value: 
                conn.cursor().execute("INSERT INTO suppliers (name, mobile, due_amount) VALUES (?, ?, 0)", (sup_name.value, sup_mobile.value or ""))
                conn.commit(); sup_name.value, sup_mobile.value = "", ""; refresh_data(); show_snack("Supplier Added!")
            else: show_snack("Supplier Name is mandatory!", is_error=True)
            
        def settle_client_due(cid, n):
            conn.cursor().execute("UPDATE clients SET due_amount = 0 WHERE id=?", (cid,)); conn.commit(); refresh_data(); show_snack(f"Credit cleared for: {n}")
        def settle_supplier_due(sid, n):
            conn.cursor().execute("UPDATE suppliers SET due_amount = 0 WHERE id=?", (sid,)); conn.commit(); refresh_data(); show_snack(f"Credit cleared for: {n}")

        # --- SMART CART & LOW STOCK LOGIC ---
        def add_to_sales_cart(e):
            if pos_item_dropdown.value and pos_qty.value:
                item_id, qty = int(pos_item_dropdown.value), int(pos_qty.value)
                cur = conn.cursor()
                cur.execute("SELECT item_name, selling_price, stock FROM inventory WHERE id=?", (item_id,))
                item = cur.fetchone()
                
                if item:
                    current_cart_qty = sum([c['qty'] for c in sales_cart if c['id'] == item_id])
                    total_requested_qty = current_cart_qty + qty
                    
                    if item[2] >= total_requested_qty:
                        found = False
                        for c in sales_cart:
                            if c['id'] == item_id:
                                c['qty'] += qty; found = True; break
                        if not found:
                            sales_cart.append({"id": item_id, "name": item[0], "price": item[1], "qty": qty})
                        update_sales_ui()
                    else: 
                        show_snack(f"⚠️ Low Stock! Only {item[2]} available in shop. (You have {current_cart_qty} in cart)", is_error=True)

        def update_sales_ui(e=None):
            sales_cart_list.controls.clear()
            subtotal = sum([item['price'] * item['qty'] for item in sales_cart])
            for item in sales_cart: sales_cart_list.controls.append(ft.Text(f"• {item['name']} (x{item['qty']}) = ₹ {item['price'] * item['qty']}"))
            
            try: disc_val = float(pos_discount_value.value or 0)
            except: disc_val = 0
            try: paid_val = float(pos_paid_amount.value or 0)
            except: paid_val = 0
                
            discount_amount = subtotal * (disc_val / 100) if pos_discount_type.value == "%" else disc_val
            final_total = subtotal - discount_amount
            due_amount = final_total - paid_val
            
            total_text.value = f"Subtotal: ₹{subtotal} | Final: ₹{final_total}"
            due_text.value = f"Credit (Udhaar): ₹{due_amount if due_amount > 0 else 0}"
            page.update()

        # 📸 DYNAMIC SHOP NAME INVOICE GENERATOR
        def generate_receipt_ui(client_name_str, vehicle, items_list, subtotal_amt, discount_amt, final_total_amt, paid_amt, due_amt, date_str):
            cur = conn.cursor()
            cur.execute("SELECT shop_name, address, mobile FROM shop_settings WHERE id=1")
            shop_data = cur.fetchone()
            s_name = shop_data[0].upper() if shop_data else "MAMA BHANJA AUTOWORK SHOP"
            s_addr = shop_data[1] if shop_data else "Biratnagar, Nepal"
            s_mob = shop_data[2] if shop_data else ""
            
            header_text = f"{s_addr} | Mobile: {s_mob}" if s_mob else s_addr

            return ft.Container(
                bgcolor=ft.Colors.WHITE, padding=20, border_radius=5,
                content=ft.Column([
                    ft.Text(s_name, size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK, text_align=ft.TextAlign.CENTER),
                    ft.Text(header_text, size=14, color=ft.Colors.BLACK_54, text_align=ft.TextAlign.CENTER),
                    ft.Divider(color=ft.Colors.BLACK_26, height=1, thickness=1), 
                    ft.Text(f"Date: {date_str}", color=ft.Colors.BLACK_87),
                    ft.Text(f"Name: {client_name_str}", color=ft.Colors.BLACK_87),
                    ft.Text(f"Vehicle: {vehicle}", color=ft.Colors.BLACK_87),
                    ft.Divider(color=ft.Colors.BLACK_26, height=1, thickness=1),
                    ft.Row([ft.Text("Item", weight=ft.FontWeight.BOLD, expand=2, color=ft.Colors.BLACK), ft.Text("Qty", weight=ft.FontWeight.BOLD, expand=1, color=ft.Colors.BLACK), ft.Text("Total", weight=ft.FontWeight.BOLD, expand=1, text_align=ft.TextAlign.RIGHT, color=ft.Colors.BLACK)]),
                    *[ft.Row([ft.Text(item['name'], expand=2, color=ft.Colors.BLACK), ft.Text(str(item['qty']), expand=1, color=ft.Colors.BLACK), ft.Text(f"₹{item['price']*item['qty']}", expand=1, text_align=ft.TextAlign.RIGHT, color=ft.Colors.BLACK)]) for item in items_list],
                    ft.Divider(color=ft.Colors.BLACK_26, height=1, thickness=1),
                    ft.Row([ft.Text("Subtotal:", expand=True, color=ft.Colors.BLACK), ft.Text(f"₹{subtotal_amt}", color=ft.Colors.BLACK)]),
                    ft.Row([ft.Text("Discount:", expand=True, color=ft.Colors.BLACK), ft.Text(f"-₹{discount_amt}", color=ft.Colors.BLACK)]),
                    ft.Row([ft.Text("GRAND TOTAL:", weight=ft.FontWeight.BOLD, expand=True, color=ft.Colors.BLACK), ft.Text(f"₹{final_total_amt}", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK)]),
                    ft.Divider(color=ft.Colors.BLACK_26, height=1, thickness=1),
                    ft.Row([ft.Text("Paid:", expand=True, color=ft.Colors.BLACK), ft.Text(f"₹{paid_amt}", color=ft.Colors.BLACK)]),
                    ft.Row([ft.Text("Due (Udhaar):", expand=True, color=ft.Colors.BLACK), ft.Text(f"₹{due_amt}", color=ft.Colors.BLACK)]),
                    ft.Container(height=10),
                    ft.Text("Thank you for your business!", italic=True, text_align=ft.TextAlign.CENTER, color=ft.Colors.BLACK_87)
                ], tight=True, scroll=ft.ScrollMode.AUTO)
            )

        def checkout(e):
            if not pos_client_dropdown.value or not sales_cart: return show_snack("Add items & select client!", is_error=True)
            client_id = int(pos_client_dropdown.value)
            cur = conn.cursor()
            cur.execute("SELECT name, gadi_no, due_amount FROM clients WHERE id=?", (client_id,))
            client = cur.fetchone()
            
            subtotal = sum([item['price'] * item['qty'] for item in sales_cart])
            for item in sales_cart: cur.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))
            
            try: disc_val = float(pos_discount_value.value or 0)
            except: disc_val = 0
            try: paid_val = float(pos_paid_amount.value or 0)
            except: paid_val = 0
            
            discount_amount = subtotal * (disc_val / 100) if pos_discount_type.value == "%" else disc_val
            final_total = subtotal - discount_amount
            due_amount = final_total - paid_val
            if due_amount < 0: due_amount = 0
            
            date_str, month_str = datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.now().strftime("%Y-%m")
            
            cur.execute("UPDATE clients SET due_amount = due_amount + ? WHERE id=?", (due_amount, client_id))
            cur.execute("INSERT INTO sales (client_id, client_info, final_amount, paid, due, date, month) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (client_id, f"{client[0]}", final_total, paid_val, due_amount, date_str, month_str))
            conn.commit()

            receipt = generate_receipt_ui(client[0], client[1], sales_cart, subtotal, discount_amount, final_total, paid_val, due_amount, date_str)
            
            def close_invoice(e):
                if hasattr(page, 'close'): page.close(invoice_dlg)
                else: invoice_dlg.open = False; page.update()
                
            invoice_dlg = ft.AlertDialog(content=receipt, actions=[ft.TextButton("Close Bill", on_click=close_invoice)])
            
            if hasattr(page, 'open'): page.open(invoice_dlg)
            else: page.overlay.append(invoice_dlg); invoice_dlg.open = True; page.update()
            
            sales_cart.clear(); pos_discount_value.value, pos_paid_amount.value = "0", "0"
            update_sales_ui(); refresh_data()

        pos_discount_value.on_change = update_sales_ui; pos_discount_type.on_change = update_sales_ui; pos_paid_amount.on_change = update_sales_ui

        # --- DELETE BILLS WITH LEDGER REVERSAL ---
        def delete_sale_bill(sale_id, client_id, due_amount):
            cur = conn.cursor()
            if client_id: cur.execute("UPDATE clients SET due_amount = due_amount - ? WHERE id=?", (due_amount, client_id))
            cur.execute("DELETE FROM sales WHERE id=?", (sale_id,)); conn.commit(); refresh_data(); show_snack("Sales Bill Deleted & Ledger Reversed!")

        def delete_purchase_bill(purchase_id, supplier_id, due_amount):
            cur = conn.cursor()
            if supplier_id: cur.execute("UPDATE suppliers SET due_amount = due_amount - ? WHERE id=?", (due_amount, supplier_id))
            cur.execute("DELETE FROM purchases WHERE id=?", (purchase_id,)); conn.commit(); refresh_data(); show_snack("Purchase Bill Deleted & Ledger Reversed!")

        # --- REPORTS LOGIC ---
        def refresh_reports(e):
            cur = conn.cursor()
            reports_list.controls.clear()
            rep_type = report_dropdown.value
            today_date, this_month = datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m")
            
            if rep_type == "Today's Sales":
                cur.execute("SELECT id, client_id, client_info, final_amount, paid, due FROM sales WHERE date LIKE ? ORDER BY id DESC", (f"{today_date}%",))
                total_sales, total_cash = 0, 0
                for row in cur.fetchall():
                    action = ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, tooltip="Delete Bill", on_click=lambda e, sid=row[0], cid=row[1], due=row[5]: delete_sale_bill(sid, cid, due))
                    reports_list.controls.append(data_card(row[2], f"Total: ₹{row[3]} | Paid: ₹{row[4]} | Due: ₹{row[5]}", action))
                    total_sales += row[3]; total_cash += row[4]
                reports_list.controls.insert(0, ft.Text(f"Today's Business: ₹{total_sales} | Cash: ₹{total_cash}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
                
            elif rep_type == "Monthly Sales Summary":
                cur.execute("SELECT id, client_id, client_info, final_amount, due, date FROM sales WHERE month=? ORDER BY id DESC", (this_month,))
                month_total = 0
                for row in cur.fetchall():
                    action = ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, on_click=lambda e, sid=row[0], cid=row[1], due=row[4]: delete_sale_bill(sid, cid, due))
                    reports_list.controls.append(data_card(f"{row[5][:10]} - {row[2]}", f"Amount: ₹{row[3]}", action))
                    month_total += row[3]
                reports_list.controls.insert(0, ft.Text(f"Month Total Sales: ₹{month_total}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800))

            elif rep_type == "Purchase Bills":
                cur.execute("SELECT id, supplier_id, supplier_info, total_cost, paid, due, date FROM purchases ORDER BY id DESC LIMIT 50")
                for row in cur.fetchall():
                    action = ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, tooltip="Delete Purchase", on_click=lambda e, pid=row[0], sid=row[1], due=row[5]: delete_purchase_bill(pid, sid, due))
                    reports_list.controls.append(data_card(f"Sup: {row[2]}", f"Bill: ₹{row[3]} | Paid: ₹{row[4]} | Due: ₹{row[5]}", action))
                    
            elif rep_type == "Client Ledger (Dues)":
                cur.execute("SELECT name, mobile, due_amount FROM clients WHERE due_amount > 0")
                total_market_due = 0
                for row in cur.fetchall():
                    reports_list.controls.append(data_card(f"{row[0]}", f"Pending from Client: ₹{row[2]}", ft.Container()))
                    total_market_due += row[2]
                reports_list.controls.insert(0, ft.Text(f"Total Market Udhaar: ₹{total_market_due}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800))
                
            elif rep_type == "Supplier Ledger (Dues)":
                cur.execute("SELECT name, mobile, due_amount FROM suppliers WHERE due_amount > 0")
                total_sup_due = 0
                for row in cur.fetchall():
                    reports_list.controls.append(data_card(f"{row[0]}", f"We Owe Supplier: ₹{row[2]}", ft.Container()))
                    total_sup_due += row[2]
                reports_list.controls.insert(0, ft.Text(f"Total Supplier Udhaar: ₹{total_sup_due}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800))
            page.update()

        report_dropdown.on_change = refresh_reports

        # --- 7. TABS VIEWS ---
        pos_view = ft.Container(content=ft.Column([
            ft.Text("Point of Sale", size=24, weight=ft.FontWeight.BOLD), pos_client_dropdown, ft.Row([pos_item_dropdown, pos_qty]),
            custom_btn("Add to Cart", ft.Icons.ADD_SHOPPING_CART, ft.Colors.BLUE_700, add_to_sales_cart), ft.Divider(), sales_cart_list, 
            ft.Row([pos_discount_type, pos_discount_value]), ft.Row([pos_paid_amount]), total_text, due_text,
            custom_btn("Generate Bill", ft.Icons.RECEIPT, ft.Colors.GREEN_700, checkout)
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=15, visible=True)

        bulk_purchase_view = ft.Container(content=ft.Column([
            ft.Text("Bulk Purchase (Vendor Bills)", size=24, weight=ft.FontWeight.BOLD), pos_supplier_dropdown,
            pur_item_name, ft.Row([pur_cost_price, pur_sell_price, pur_stock]),
            custom_btn("Add to Bill List", ft.Icons.ADD_BOX, ft.Colors.BLUE_700, add_to_purchase_cart),
            ft.Divider(), purchase_cart_list, ft.Row([pur_paid_amount]), pur_total_text,
            custom_btn("Save Supplier Bill", ft.Icons.SAVE, ft.Colors.GREEN_700, confirm_bulk_purchase)
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=15, visible=False)
        
        products_view = ft.Container(content=ft.Column([
            ft.Text("Products Menu (Direct Stock)", size=24, weight=ft.FontWeight.BOLD),
            edit_inv_name, ft.Row([edit_inv_cp, edit_inv_sp, edit_inv_qty]),
            custom_btn("Add / Update Product", ft.Icons.SAVE, ft.Colors.BLUE_700, add_or_update_product),
            ft.Divider(), product_list
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=10, visible=False)

        client_view = ft.Container(content=ft.Column([
            ft.Text("Clients Registry", size=24, weight=ft.FontWeight.BOLD), client_name, client_mobile, client_gadi,
            custom_btn("Register Client", ft.Icons.PERSON_ADD, ft.Colors.BLUE_700, add_client),
            ft.Divider(), ft.Text("Client Accounts (Tap 💵 to Clear Due):", weight=ft.FontWeight.BOLD, size=16), client_list
        ], expand=True), padding=15, visible=False)
        
        supplier_view = ft.Container(content=ft.Column([
            ft.Text("Supplier Registry", size=24, weight=ft.FontWeight.BOLD), sup_name, sup_mobile,
            custom_btn("Register Supplier", ft.Icons.BUSINESS, ft.Colors.BLUE_700, add_supplier),
            ft.Divider(), ft.Text("Supplier Accounts (Tap 💵 to Clear Due):", weight=ft.FontWeight.BOLD, size=16), supplier_list
        ], expand=True), padding=15, visible=False)
        
        reports_view = ft.Container(content=ft.Column([
            ft.Text("Business Reports", size=24, weight=ft.FontWeight.BOLD), report_dropdown, ft.Divider(), reports_list
        ], expand=True), padding=15, visible=False)

        settings_view = ft.Container(content=ft.Column([
            ft.Text("Shop Settings", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("This information will be printed on the invoice:", color=ft.Colors.GREY_700),
            set_shop_name, set_shop_address, set_shop_mobile,
            custom_btn("Save Settings", ft.Icons.SAVE, ft.Colors.ORANGE_800, save_shop_settings)
        ], expand=True), padding=15, visible=False)

        # --- 8. SIDEBAR ---
        def switch_tab(tab_name):
            pos_view.visible = (tab_name == "pos"); bulk_purchase_view.visible = (tab_name == "buy")
            products_view.visible = (tab_name == "prod"); client_view.visible = (tab_name == "client")
            supplier_view.visible = (tab_name == "sup"); reports_view.visible = (tab_name == "reports")
            settings_view.visible = (tab_name == "settings")
            
            titles = {"pos": "Sales & POS", "buy": "Bulk Purchases", "prod": "Products & Stock", "client": "Client Ledger", "sup": "Supplier Ledger", "reports": "Reports & Bills", "settings": "Shop Settings"}
            page.appbar.title.value = titles[tab_name]
            toggle_sidebar(None)

        def toggle_sidebar(e):
            if sidebar.left == 0: sidebar.left = -250; overlay_bg.visible = False
            else: sidebar.left = 0; overlay_bg.visible = True
            page.update()

        sidebar = ft.Container(
            width=250, left=-250, top=0, bottom=0, bgcolor=ft.Colors.WHITE, animate_position=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            content=ft.Column([
                ft.Container(height=60, bgcolor=ft.Colors.BLUE_800, padding=10, content=ft.Row([ft.Icon(ft.Icons.GARAGE, color=ft.Colors.WHITE, size=30), ft.Text("ERP Menu", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)])),
                ft.ListTile(leading=ft.Icon(ft.Icons.POINT_OF_SALE, color=ft.Colors.BLUE_800), title=ft.Text("POS Billing", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("pos")),
                ft.ListTile(leading=ft.Icon(ft.Icons.SHOPPING_CART, color=ft.Colors.BLUE_800), title=ft.Text("Buy Stock (Bulk)", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("buy")),
                ft.ListTile(leading=ft.Icon(ft.Icons.INVENTORY, color=ft.Colors.BLUE_800), title=ft.Text("Products Menu", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("prod")),
                ft.ListTile(leading=ft.Icon(ft.Icons.PEOPLE, color=ft.Colors.BLUE_800), title=ft.Text("Clients Ledger", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("client")),
                ft.ListTile(leading=ft.Icon(ft.Icons.BUSINESS, color=ft.Colors.BLUE_800), title=ft.Text("Suppliers Ledger", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("sup")),
                ft.ListTile(leading=ft.Icon(ft.Icons.PIE_CHART, color=ft.Colors.BLUE_800), title=ft.Text("Reports & Bills", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("reports")),
                ft.ListTile(leading=ft.Icon(ft.Icons.SETTINGS, color=ft.Colors.ORANGE_800), title=ft.Text("Shop Settings", weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_800), on_click=lambda e: switch_tab("settings")),
                ft.Divider(),
                ft.ListTile(leading=ft.Icon(ft.Icons.EXIT_TO_APP, color=ft.Colors.RED_800), title=ft.Text("Logout", color=ft.Colors.RED_800, weight=ft.FontWeight.BOLD), on_click=lambda e: page.controls.clear() or setattr(page, 'appbar', None) or page.add(login_view) or page.update())
            ])
        )

        overlay_bg = ft.Container(expand=True, left=0, right=0, top=0, bottom=0, bgcolor=ft.Colors.BLACK_54, visible=False, on_click=toggle_sidebar)
        main_app_bar = ft.AppBar(leading=ft.IconButton(ft.Icons.MENU, on_click=toggle_sidebar, icon_color=ft.Colors.WHITE), title=ft.Text("Sales & POS", color=ft.Colors.WHITE), bgcolor=ft.Colors.BLUE_800)
        app_body = ft.Stack([ft.Column([pos_view, bulk_purchase_view, products_view, client_view, supplier_view, reports_view, settings_view], expand=True), overlay_bg, sidebar], expand=True)

        # --- 🔔 LOW STOCK NOTIFICATION ALERT ON LOGIN ---
        def check_low_stock_on_login():
            cur = conn.cursor()
            cur.execute("SELECT item_name, stock FROM inventory WHERE stock <= 5")
            low_items = cur.fetchall()
            if low_items:
                msg = "\n".join([f"• {r[0]} (Only {r[1]} left)" for r in low_items])
                def close_alert(e):
                    if hasattr(page, 'close'): page.close(alert_dlg)
                    else: alert_dlg.open = False; page.update()
                alert_dlg = ft.AlertDialog(
                    title=ft.Text("⚠️ Low Stock Alert!", color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD),
                    content=ft.Text(f"Please refill these items soon:\n\n{msg}", color=ft.Colors.BLACK_87),
                    actions=[ft.TextButton("Got it", on_click=close_alert)]
                )
                if hasattr(page, 'open'): page.open(alert_dlg)
                else: page.overlay.append(alert_dlg); alert_dlg.open = True; page.update()

        # --- 9. INSTANT PIN LOGIN (Password = 99) ---
        def check_pin(e):
            if pin_input.value == "99":
                page.controls.clear(); page.appbar = main_app_bar; page.add(app_body); refresh_data()
                check_low_stock_on_login()
            elif len(pin_input.value) >= 2:
                show_snack("Incorrect PIN!", is_error=True)
                pin_input.value = ""; page.update()

        pin_input = ft.TextField(label="Enter Secret PIN", password=True, keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER, width=200, on_change=check_pin)
        
        login_view = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.LOCK, size=80, color=ft.Colors.BLUE_800), ft.Text("RK AUTO ERP", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(height=20), pin_input, ft.Text("Type PIN '99' to unlock automatically.", color=ft.Colors.GREY_700)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment.CENTER, expand=True
        )
        page.add(login_view)

    except Exception as e:
        page.vertical_alignment = ft.MainAxisAlignment.CENTER; page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        page.add(ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=60), ft.Text("App Failed", size=22, color=ft.Colors.RED), ft.Text(traceback.format_exc(), color=ft.Colors.RED, selectable=True))

ft.run(main)
