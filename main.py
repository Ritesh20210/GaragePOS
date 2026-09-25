import flet as ft
import sqlite3
import os
import tempfile
import traceback
from datetime import datetime
import urllib.parse

def main(page: ft.Page):
    try:
        # --- 1. APP SETUP ---
        page.title = "Auto Workshop Pro ERP"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0
        
        # --- 2. SECURE DATABASE (v4 for Supplier Ledger & Deletes) ---
        db_folder = os.environ.get("HOME", tempfile.gettempdir())
        db_path = os.path.join(db_folder, "garage_pos_v4.db")
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        # Tables
        cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, cost_price REAL, selling_price REAL, stock INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, mobile TEXT, gadi_no TEXT, due_amount REAL DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, mobile TEXT, due_amount REAL DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, client_info TEXT, final_amount REAL, paid REAL, due REAL, date TEXT, month TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_id INTEGER, supplier_info TEXT, item_name TEXT, qty INTEGER, total_cost REAL, paid REAL, due REAL, date TEXT, month TEXT)''')
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

        # --- 4. UI VARIABLES ---
        cart = []

        # Inventory / Purchases
        inv_supplier_dropdown = ft.Dropdown(label="Select Supplier", expand=True)
        inv_name = ft.TextField(label="Item / Part Name", prefix_icon=ft.Icons.BUILD, expand=True)
        inv_cost_price = ft.TextField(label="Cost Price (₹)", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        inv_sell_price = ft.TextField(label="Selling Price (₹)", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        inv_stock = ft.TextField(label="Qty", keyboard_type=ft.KeyboardType.NUMBER, width=100)
        inv_paid_amount = ft.TextField(label="Cash Paid to Supplier (₹)", value="0", keyboard_type=ft.KeyboardType.NUMBER, border_color=ft.Colors.GREEN_700, expand=True)
        inventory_list = ft.ListView(expand=True, spacing=10)

        # Clients
        client_name = ft.TextField(label="Client Name", prefix_icon=ft.Icons.PERSON)
        client_mobile = ft.TextField(label="Mobile No.", keyboard_type=ft.KeyboardType.PHONE, prefix_icon=ft.Icons.PHONE)
        client_gadi = ft.TextField(label="Vehicle No. (ex: BA 1 PA 1234)", prefix_icon=ft.Icons.DIRECTIONS_CAR)
        client_list = ft.ListView(expand=True, spacing=10)

        # Suppliers
        supplier_name = ft.TextField(label="Supplier Name", prefix_icon=ft.Icons.BUSINESS)
        supplier_mobile = ft.TextField(label="Mobile No.", keyboard_type=ft.KeyboardType.PHONE, prefix_icon=ft.Icons.PHONE)
        supplier_list = ft.ListView(expand=True, spacing=10)

        # POS
        pos_client_dropdown = ft.Dropdown(label="Select Client")
        pos_item_dropdown = ft.Dropdown(label="Select Item", expand=True)
        pos_qty = ft.TextField(label="Qty", value="1", width=80, keyboard_type=ft.KeyboardType.NUMBER)
        pos_discount_type = ft.Dropdown(label="Disc. Type", options=[ft.dropdown.Option("₹ Amount"), ft.dropdown.Option("% Percent")], value="₹ Amount", width=120)
        pos_discount_value = ft.TextField(label="Discount", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        pos_paid_amount = ft.TextField(label="Cash Received (₹)", value="0", keyboard_type=ft.KeyboardType.NUMBER, border_color=ft.Colors.GREEN_700)
        cart_list = ft.ListView(expand=True, spacing=10)
        total_text = ft.Text("Total: ₹ 0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)
        due_text = ft.Text("Credit (Udhaar): ₹ 0", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700)
        
        # Reports
        report_dropdown = ft.Dropdown(label="Select Report Type", options=[
            ft.dropdown.Option("Today's Sales"), ft.dropdown.Option("Monthly Sales Summary"), 
            ft.dropdown.Option("Purchase Bills"), ft.dropdown.Option("Client Ledger"), ft.dropdown.Option("Supplier Ledger")
        ], value="Today's Sales")
        reports_list = ft.ListView(expand=True, spacing=10)

        # --- 5. CORE LOGIC ---
        def refresh_data():
            cur = conn.cursor()
            
            # Inventory List
            inventory_list.controls.clear()
            pos_item_dropdown.options.clear()
            cur.execute("SELECT id, item_name, cost_price, selling_price, stock FROM inventory")
            for row in cur.fetchall():
                action_row = ft.Row([
                    ft.IconButton(ft.Icons.EDIT, icon_color=ft.Colors.BLUE, on_click=lambda e, r=row: edit_item_setup(r)),
                    ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, on_click=lambda e, i=row[0]: delete_item(i))
                ])
                inventory_list.controls.append(
                    ft.ListTile(title=ft.Text(f"{row[1]} (Stock: {row[4]})", weight=ft.FontWeight.BOLD),
                                subtitle=ft.Text(f"CP: ₹{row[2]} | SP: ₹{row[3]}", color=ft.Colors.GREEN_700), trailing=action_row)
                )
                pos_item_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=f"{row[1]} - ₹{row[3]}"))

            # Clients List
            client_list.controls.clear()
            pos_client_dropdown.options.clear()
            cur.execute("SELECT id, name, mobile, gadi_no, due_amount FROM clients")
            for row in cur.fetchall():
                due_info = f"Udhaar: ₹{row[4]}" if row[4] > 0 else "Clear"
                client_list.controls.append(
                    ft.ListTile(leading=ft.Icon(ft.Icons.DIRECTIONS_CAR), title=ft.Text(f"{row[3]} - {row[1]}", weight=ft.FontWeight.BOLD), 
                                subtitle=ft.Text(f"{row[2]} | {due_info}", color=ft.Colors.RED_700 if row[4] > 0 else ft.Colors.GREEN_700),
                                trailing=ft.IconButton(ft.Icons.MONEY, tooltip="Receive Payment", on_click=lambda e, cid=row[0], n=row[1]: settle_due(cid, n, "client")) if row[4] > 0 else None)
                )
                pos_client_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=f"{row[3]} ({row[1]})"))

            # Suppliers List
            supplier_list.controls.clear()
            inv_supplier_dropdown.options.clear()
            cur.execute("SELECT id, name, mobile, due_amount FROM suppliers")
            for row in cur.fetchall():
                due_info = f"We Owe: ₹{row[3]}" if row[3] > 0 else "Clear"
                supplier_list.controls.append(
                    ft.ListTile(leading=ft.Icon(ft.Icons.BUSINESS), title=ft.Text(row[1], weight=ft.FontWeight.BOLD), 
                                subtitle=ft.Text(f"{row[2]} | {due_info}", color=ft.Colors.RED_700 if row[3] > 0 else ft.Colors.GREEN_700),
                                trailing=ft.IconButton(ft.Icons.MONEY, tooltip="Pay Supplier", on_click=lambda e, sid=row[0], n=row[1]: settle_due(sid, n, "supplier")) if row[3] > 0 else None)
                )
                inv_supplier_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=row[1]))
                
            refresh_reports(None)
            page.update()

        # --- INVENTORY & PURCHASE ACTIONS ---
        def add_or_update_inventory(e):
            if inv_name.value and inv_cost_price.value and inv_sell_price.value and inv_stock.value:
                cur = conn.cursor()
                cp = float(inv_cost_price.value)
                sp = float(inv_sell_price.value)
                qty = int(inv_stock.value)
                
                if app_state["edit_item_id"]:
                    cur.execute("UPDATE inventory SET item_name=?, cost_price=?, selling_price=?, stock=? WHERE id=?", 
                                (inv_name.value, cp, sp, qty, app_state["edit_item_id"]))
                    show_snack("Item Updated Successfully!")
                    app_state["edit_item_id"] = None
                else:
                    if not inv_supplier_dropdown.value:
                        show_snack("Please select a Supplier for new purchase!", is_error=True)
                        return
                    
                    # Log Purchase
                    supplier_id = int(inv_supplier_dropdown.value)
                    cur.execute("SELECT name FROM suppliers WHERE id=?", (supplier_id,))
                    supp_name = cur.fetchone()[0]
                    
                    try: paid_val = float(inv_paid_amount.value or 0)
                    except ValueError: paid_val = 0
                    
                    total_cost = cp * qty
                    due = total_cost - paid_val
                    if due < 0: due = 0
                    
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    month_str = datetime.now().strftime("%Y-%m")
                    
                    # Update Supplier Due
                    cur.execute("UPDATE suppliers SET due_amount = due_amount + ? WHERE id=?", (due, supplier_id))
                    
                    # Log to Purchases
                    cur.execute("INSERT INTO purchases (supplier_id, supplier_info, item_name, qty, total_cost, paid, due, date, month) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (supplier_id, supp_name, inv_name.value, qty, total_cost, paid_val, due, date_str, month_str))
                    
                    # Add to Inventory (Check if exists, else insert)
                    cur.execute("SELECT id FROM inventory WHERE item_name=?", (inv_name.value,))
                    existing = cur.fetchone()
                    if existing:
                        cur.execute("UPDATE inventory SET stock = stock + ?, cost_price=?, selling_price=? WHERE id=?", (qty, cp, sp, existing[0]))
                    else:
                        cur.execute("INSERT INTO inventory (item_name, cost_price, selling_price, stock) VALUES (?, ?, ?, ?)", (inv_name.value, cp, sp, qty))
                    
                    show_snack("Purchase Saved & Stock Updated!")
                    
                conn.commit()
                inv_name.value, inv_cost_price.value, inv_sell_price.value, inv_stock.value, inv_paid_amount.value = "", "", "", "", "0"
                refresh_data()

        def edit_item_setup(row):
            app_state["edit_item_id"] = row[0]
            inv_name.value = row[1]; inv_cost_price.value = str(row[2]); inv_sell_price.value = str(row[3]); inv_stock.value = str(row[4])
            show_snack("Editing Mode: Updating will NOT create a purchase bill.", is_error=False)
            page.update()

        def delete_item(item_id):
            conn.cursor().execute("DELETE FROM inventory WHERE id=?", (item_id,))
            conn.commit(); refresh_data(); show_snack("Item Deleted!")

        # --- ENTITY ACTIONS ---
        def add_client(e):
            if client_name.value and client_mobile.value and client_gadi.value:
                conn.cursor().execute("INSERT INTO clients (name, mobile, gadi_no, due_amount) VALUES (?, ?, ?, 0)", (client_name.value, client_mobile.value, client_gadi.value))
                conn.commit(); client_name.value, client_mobile.value, client_gadi.value = "", "", ""; refresh_data(); show_snack("Client Added!")

        def add_supplier(e):
            if supplier_name.value and supplier_mobile.value:
                conn.cursor().execute("INSERT INTO suppliers (name, mobile, due_amount) VALUES (?, ?, 0)", (supplier_name.value, supplier_mobile.value))
                conn.commit(); supplier_name.value, supplier_mobile.value = "", ""; refresh_data(); show_snack("Supplier Added!")

        def settle_due(entity_id, name, type_str):
            table = "clients" if type_str == "client" else "suppliers"
            conn.cursor().execute(f"UPDATE {table} SET due_amount = 0 WHERE id=?", (entity_id,))
            conn.commit(); refresh_data(); show_snack(f"Credit cleared for {name}!")

        # --- POS LOGIC ---
        def add_to_cart(e):
            if pos_item_dropdown.value and pos_qty.value:
                item_id = int(pos_item_dropdown.value); qty = int(pos_qty.value)
                cur = conn.cursor()
                cur.execute("SELECT item_name, selling_price, stock FROM inventory WHERE id=?", (item_id,))
                item = cur.fetchone()
                if item and item[2] >= qty:
                    cart.append({"id": item_id, "name": item[0], "price": item[1], "qty": qty})
                    update_cart_ui()
                else: show_snack("Not enough stock!", is_error=True)

        def update_cart_ui(e=None):
            cart_list.controls.clear()
            subtotal = 0
            for item in cart:
                item_total = item['price'] * item['qty']
                subtotal += item_total
                cart_list.controls.append(ft.Text(f"• {item['name']} (x{item['qty']}) = ₹ {item_total}", size=16))
            
            try: disc_val = float(pos_discount_value.value or 0)
            except ValueError: disc_val = 0
            try: paid_val = float(pos_paid_amount.value or 0)
            except ValueError: paid_val = 0
                
            discount_amount = subtotal * (disc_val / 100) if pos_discount_type.value == "% Percent" else disc_val
            final_total = subtotal - discount_amount
            due_amount = final_total - paid_val
            
            total_text.value = f"Subtotal: ₹{subtotal} | Final: ₹{final_total}"
            due_text.value = f"Credit (Udhaar): ₹{due_amount if due_amount > 0 else 0}"
            page.update()

        def checkout_and_generate_bill(e):
            if not pos_client_dropdown.value or not cart: return show_snack("Select a client and add items to cart!", is_error=True)
            client_id = int(pos_client_dropdown.value)
            cur = conn.cursor()
            cur.execute("SELECT name, gadi_no, due_amount FROM clients WHERE id=?", (client_id,))
            client = cur.fetchone()
            client_info = f"{client[1]} ({client[0]})"
            
            subtotal = 0; invoice_lines = []
            for item in cart:
                item_total = item['price'] * item['qty']
                subtotal += item_total
                invoice_lines.append(ft.Text(f"{item['name']} x{item['qty']} = ₹{item_total}"))
                cur.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))
            
            try: disc_val = float(pos_discount_value.value or 0)
            except ValueError: disc_val = 0
            try: paid_val = float(pos_paid_amount.value or 0)
            except ValueError: paid_val = 0
            
            discount_amount = subtotal * (disc_val / 100) if pos_discount_type.value == "% Percent" else disc_val
            final_total = subtotal - discount_amount
            due_amount = final_total - paid_val
            if due_amount < 0: due_amount = 0
            
            cur.execute("UPDATE clients SET due_amount = due_amount + ? WHERE id=?", (due_amount, client_id))
            current_date = datetime.now().strftime("%Y-%m-%d")
            cur.execute("INSERT INTO sales (client_id, client_info, final_amount, paid, due, date, month) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (client_id, client_info, final_total, paid_val, due_amount, current_date, datetime.now().strftime("%Y-%m")))
            conn.commit()
            
            receipt_content = ft.Column([
                ft.Text("AUTO WORKSHOP GARAGE", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                ft.Text(f"Date: {current_date}"), ft.Text(f"Vehicle: {client[1]} | Name: {client[0]}"), ft.Divider(),
                *invoice_lines, ft.Divider(),
                ft.Text(f"Subtotal: ₹{subtotal}"), ft.Text(f"Discount: ₹{discount_amount}", color=ft.Colors.RED_700),
                ft.Text(f"GRAND TOTAL: ₹{final_total}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                ft.Text(f"Paid: ₹{paid_val} | Added to Udhaar: ₹{due_amount}", color=ft.Colors.ORANGE_800),
            ], tight=True)
            
            dlg = ft.AlertDialog(title=ft.Text("Invoice Generated!"), content=receipt_content, actions=[ft.TextButton("Close Bill", on_click=lambda e: setattr(dlg, 'open', False) or page.update())])
            if hasattr(page, 'open'): page.open(dlg)
            else: page.dialog = dlg; dlg.open = True; page.update()

            cart.clear(); pos_discount_value.value = "0"; pos_paid_amount.value = "0"; update_cart_ui(); refresh_data()

        # --- DELETE BILLS LOGIC ---
        def delete_sale(sale_id, client_id, due_amount):
            cur = conn.cursor()
            cur.execute("DELETE FROM sales WHERE id=?", (sale_id,))
            if due_amount > 0 and client_id:
                cur.execute("UPDATE clients SET due_amount = due_amount - ? WHERE id=?", (due_amount, client_id))
            conn.commit(); refresh_data(); show_snack("Sales Bill Deleted & Credit Reverted!")

        def delete_purchase(pur_id, supp_id, due_amount):
            cur = conn.cursor()
            cur.execute("DELETE FROM purchases WHERE id=?", (pur_id,))
            if due_amount > 0 and supp_id:
                cur.execute("UPDATE suppliers SET due_amount = due_amount - ? WHERE id=?", (due_amount, supp_id))
            conn.commit(); refresh_data(); show_snack("Purchase Bill Deleted & Credit Reverted!")

        # --- REPORTS LOGIC ---
        def refresh_reports(e):
            cur = conn.cursor()
            reports_list.controls.clear()
            rep_type = report_dropdown.value
            
            if rep_type == "Today's Sales":
                cur.execute("SELECT id, client_id, client_info, final_amount, paid, due FROM sales WHERE date=?", (datetime.now().strftime("%Y-%m-%d"),))
                total_sales, total_cash = 0, 0
                for row in cur.fetchall():
                    del_btn = ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, on_click=lambda e, sid=row[0], cid=row[1], due=row[5]: delete_sale(sid, cid, due))
                    reports_list.controls.append(ft.ListTile(title=ft.Text(row[2]), subtitle=ft.Text(f"Total: ₹{row[3]} | Paid: ₹{row[4]} | Due: ₹{row[5]}"), trailing=del_btn))
                    total_sales += row[3]; total_cash += row[4]
                reports_list.controls.insert(0, ft.Text(f"Today's Business: ₹{total_sales} | Cash in Hand: ₹{total_cash}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800))
                
            elif rep_type == "Monthly Sales Summary":
                cur.execute("SELECT id, client_id, client_info, final_amount, date, due FROM sales WHERE month=?", (datetime.now().strftime("%Y-%m"),))
                month_total = 0
                for row in cur.fetchall():
                    del_btn = ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, on_click=lambda e, sid=row[0], cid=row[1], due=row[5]: delete_sale(sid, cid, due))
                    reports_list.controls.append(ft.ListTile(title=ft.Text(f"{row[4]} - {row[2]}"), subtitle=ft.Text(f"Amount: ₹{row[3]}"), trailing=del_btn))
                    month_total += row[3]
                reports_list.controls.insert(0, ft.Text(f"Total Sales This Month: ₹{month_total}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800))

            elif rep_type == "Purchase Bills":
                cur.execute("SELECT id, supplier_id, supplier_info, item_name, qty, total_cost, date, due FROM purchases ORDER BY id DESC LIMIT 50")
                for row in cur.fetchall():
                    del_btn = ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, on_click=lambda e, pid=row[0], sid=row[1], due=row[7]: delete_purchase(pid, sid, due))
                    reports_list.controls.append(ft.ListTile(title=ft.Text(f"{row[3]} from {row[2]}"), subtitle=ft.Text(f"Qty: {row[4]} | Cost: ₹{row[5]} | Date: {row[6]}"), trailing=del_btn))
                    
            elif rep_type == "Client Ledger":
                cur.execute("SELECT name, mobile, due_amount FROM clients WHERE due_amount > 0")
                total_market_due = sum([row[2] for row in cur.fetchall()])
                cur.execute("SELECT name, mobile, due_amount FROM clients WHERE due_amount > 0")
                for row in cur.fetchall(): reports_list.controls.append(ft.ListTile(title=ft.Text(f"{row[0]} ({row[1]})"), subtitle=ft.Text(f"Udhaar Pending: ₹{row[2]}", color=ft.Colors.RED_700)))
                reports_list.controls.insert(0, ft.Text(f"Market Owe Us: ₹{total_market_due}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800))
                
            elif rep_type == "Supplier Ledger":
                cur.execute("SELECT name, mobile, due_amount FROM suppliers WHERE due_amount > 0")
                total_supp_due = sum([row[2] for row in cur.fetchall()])
                cur.execute("SELECT name, mobile, due_amount FROM suppliers WHERE due_amount > 0")
                for row in cur.fetchall(): reports_list.controls.append(ft.ListTile(title=ft.Text(f"{row[0]} ({row[1]})"), subtitle=ft.Text(f"We Owe: ₹{row[2]}", color=ft.Colors.RED_700)))
                reports_list.controls.insert(0, ft.Text(f"We Owe Suppliers: ₹{total_supp_due}", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800))
            page.update()

        report_dropdown.on_change = refresh_reports

        # --- 7. SCREEN VIEWS ---
        pos_view = ft.Container(content=ft.Column([
            ft.Text("Point of Sale", size=24, weight=ft.FontWeight.BOLD), pos_client_dropdown, ft.Row([pos_item_dropdown, pos_qty]),
            custom_btn("Add to Cart", ft.Icons.ADD_SHOPPING_CART, ft.Colors.BLUE_700, add_to_cart), ft.Divider(), cart_list, 
            ft.Row([pos_discount_type, pos_discount_value]), ft.Row([pos_paid_amount]), total_text, due_text,
            custom_btn("Generate Bill & Save", ft.Icons.RECEIPT, ft.Colors.GREEN_700, checkout_and_generate_bill)
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=15, visible=True)

        inventory_view = ft.Container(content=ft.Column([
            ft.Text("Inventory & Purchases", size=24, weight=ft.FontWeight.BOLD), 
            ft.Row([inv_supplier_dropdown]), inv_name, ft.Row([inv_cost_price, inv_sell_price, inv_stock]), ft.Row([inv_paid_amount]),
            custom_btn("Save Purchase & Update Stock", ft.Icons.SAVE, ft.Colors.BLUE_700, add_or_update_inventory),
            ft.Divider(), ft.Text("Stock Status (Tap ✏️ to Edit):", weight=ft.FontWeight.BOLD, size=16), inventory_list
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=15, visible=False)

        client_view = ft.Container(content=ft.Column([
            ft.Text("Client Registry", size=24, weight=ft.FontWeight.BOLD), client_name, client_mobile, client_gadi,
            custom_btn("Register Client", ft.Icons.PERSON_ADD, ft.Colors.BLUE_700, add_client),
            ft.Divider(), ft.Text("Client Accounts (Tap 💵 to Clear Due):", weight=ft.FontWeight.BOLD, size=16), client_list
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=15, visible=False)
        
        supplier_view = ft.Container(content=ft.Column([
            ft.Text("Supplier Registry", size=24, weight=ft.FontWeight.BOLD), supplier_name, supplier_mobile,
            custom_btn("Register Supplier", ft.Icons.BUSINESS, ft.Colors.BLUE_700, add_supplier),
            ft.Divider(), ft.Text("Supplier Accounts (Tap 💵 to Clear Due):", weight=ft.FontWeight.BOLD, size=16), supplier_list
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=15, visible=False)
        
        reports_view = ft.Container(content=ft.Column([
            ft.Text("Business Reports", size=24, weight=ft.FontWeight.BOLD), report_dropdown, ft.Divider(), reports_list
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=15, visible=False)

        # --- 8. SIDEBAR ---
        def switch_tab(tab_name):
            pos_view.visible = (tab_name == "pos")
            inventory_view.visible = (tab_name == "inv")
            client_view.visible = (tab_name == "client")
            supplier_view.visible = (tab_name == "supplier")
            reports_view.visible = (tab_name == "reports")
            
            if tab_name == "pos": page.appbar.title.value = "Sales & POS"
            elif tab_name == "inv": page.appbar.title.value = "Purchases & Inventory"
            elif tab_name == "client": page.appbar.title.value = "Clients"
            elif tab_name == "supplier": page.appbar.title.value = "Suppliers"
            elif tab_name == "reports": page.appbar.title.value = "Reports & Analytics"
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
                ft.ListTile(leading=ft.Icon(ft.Icons.INVENTORY, color=ft.Colors.BLUE_800), title=ft.Text("Inventory & Purchases", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("inv")),
                ft.ListTile(leading=ft.Icon(ft.Icons.PEOPLE, color=ft.Colors.BLUE_800), title=ft.Text("Clients", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("client")),
                ft.ListTile(leading=ft.Icon(ft.Icons.BUSINESS, color=ft.Colors.BLUE_800), title=ft.Text("Suppliers", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("supplier")),
                ft.ListTile(leading=ft.Icon(ft.Icons.PIE_CHART, color=ft.Colors.BLUE_800), title=ft.Text("Reports & History", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("reports")),
                ft.Divider(),
                ft.ListTile(leading=ft.Icon(ft.Icons.EXIT_TO_APP, color=ft.Colors.RED_800), title=ft.Text("Logout", color=ft.Colors.RED_800, weight=ft.FontWeight.BOLD), on_click=lambda e: page.controls.clear() or setattr(page, 'appbar', None) or page.add(login_view) or page.update())
            ])
        )

        overlay_bg = ft.Container(expand=True, left=0, right=0, top=0, bottom=0, bgcolor=ft.Colors.BLACK_54, visible=False, on_click=toggle_sidebar)
        main_app_bar = ft.AppBar(leading=ft.IconButton(ft.Icons.MENU, on_click=toggle_sidebar, icon_color=ft.Colors.WHITE), title=ft.Text("Sales & POS", color=ft.Colors.WHITE), bgcolor=ft.Colors.BLUE_800)
        app_body = ft.Stack([ft.Column([pos_view, inventory_view, client_view, supplier_view, reports_view], expand=True), overlay_bg, sidebar], expand=True)

        # --- 9. LOGIN ---
        def handle_login(e):
            if username_input.value == "admin" and password_input.value == "Salam123":
                page.controls.clear(); page.appbar = main_app_bar; page.add(app_body); refresh_data()
            else: show_snack("Invalid Login!", is_error=True)

        username_input = ft.TextField(label="Username", prefix_icon=ft.Icons.PERSON, width=300)
        password_input = ft.TextField(label="Password", prefix_icon=ft.Icons.LOCK, password=True, can_reveal_password=True, width=300)
        
        login_view = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.GARAGE, size=80, color=ft.Colors.BLUE_800), ft.Text("Workshop ERP", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(height=20), username_input, password_input, ft.Container(height=10),
                custom_btn("Login", ft.Icons.LOGIN, ft.Colors.BLUE_800, handle_login)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment.CENTER, expand=True
        )
        page.add(login_view)

    except Exception as e:
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        page.add(ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=60), ft.Text("App Failed to Load", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.RED), ft.Text(traceback.format_exc(), color=ft.Colors.RED, selectable=True))

ft.run(main)
