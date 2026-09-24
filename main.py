import flet as ft
import sqlite3
import urllib.parse
import os
import tempfile
import traceback

def main(page: ft.Page):
    try:
        # --- 1. APP SETUP ---
        page.title = "Auto Workshop Garage POS"
        page.theme_mode = ft.ThemeMode.LIGHT
        
        # --- 2. SECURE ANDROID DATABASE ---
        db_folder = os.environ.get("HOME", tempfile.gettempdir())
        db_path = os.path.join(db_folder, "garage_pos.db")
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            item_name TEXT, price REAL, stock INTEGER)''')
                            
        cursor.execute('''CREATE TABLE IF NOT EXISTS clients (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT, mobile TEXT, gadi_no TEXT)''')
        conn.commit()

        # --- 3. UI VARIABLES ---
        cart = []

        inv_name = ft.TextField(label="Item Name", prefix_icon=ft.Icons.BUILD, expand=True)
        inv_price = ft.TextField(label="Price (Rs)", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        inv_stock = ft.TextField(label="Qty", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        inventory_list = ft.ListView(expand=True, spacing=10)

        client_name = ft.TextField(label="Client Name", prefix_icon=ft.Icons.PERSON)
        client_mobile = ft.TextField(label="Mobile No.", keyboard_type=ft.KeyboardType.PHONE, prefix_icon=ft.Icons.PHONE)
        client_gadi = ft.TextField(label="Vehicle No. (ex: BA 1 PA 1234)", prefix_icon=ft.Icons.DIRECTIONS_CAR)
        client_list = ft.ListView(expand=True, spacing=10)

        pos_client_dropdown = ft.Dropdown(label="Select Client")
        pos_item_dropdown = ft.Dropdown(label="Select Item", expand=True)
        pos_qty = ft.TextField(label="Qty", value="1", width=80, keyboard_type=ft.KeyboardType.NUMBER)
        pos_discount = ft.TextField(label="Discount (Rs)", value="0", keyboard_type=ft.KeyboardType.NUMBER)
        cart_list = ft.ListView(expand=True, spacing=10)
        total_text = ft.Text("Total: Rs. 0", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)

        # --- 4. APP LOGIC ---
        def refresh_data():
            cursor = conn.cursor()
            
            # Refresh Inventory
            inventory_list.controls.clear()
            pos_item_dropdown.options.clear()
            cursor.execute("SELECT id, item_name, price, stock FROM inventory")
            for row in cursor.fetchall():
                inventory_list.controls.append(
                    ft.ListTile(
                        title=ft.Text(f"{row[1]} (Stock: {row[3]})", weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(f"Rs. {row[2]}"),
                        trailing=ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, on_click=lambda e, i=row[0]: delete_item(i))
                    )
                )
                pos_item_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=f"{row[1]} - Rs.{row[2]}"))

            # Refresh Clients
            client_list.controls.clear()
            pos_client_dropdown.options.clear()
            cursor.execute("SELECT id, name, mobile, gadi_no FROM clients")
            for row in cursor.fetchall():
                client_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.DIRECTIONS_CAR),
                        title=ft.Text(f"{row[3]} - {row[1]}", weight=ft.FontWeight.BOLD), 
                        subtitle=ft.Text(row[2])
                    )
                )
                pos_client_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=f"{row[3]} ({row[1]})"))
            page.update()

        def add_inventory(e):
            if inv_name.value and inv_price.value and inv_stock.value:
                conn.cursor().execute("INSERT INTO inventory (item_name, price, stock) VALUES (?, ?, ?)", 
                                      (inv_name.value, float(inv_price.value), int(inv_stock.value)))
                conn.commit()
                inv_name.value, inv_price.value, inv_stock.value = "", "", ""
                refresh_data()
                show_snack("Item Added Successfully!")

        def delete_item(item_id):
            conn.cursor().execute("DELETE FROM inventory WHERE id=?", (item_id,))
            conn.commit()
            refresh_data()
            show_snack("Item Deleted!")

        def add_client(e):
            if client_name.value and client_mobile.value and client_gadi.value:
                conn.cursor().execute("INSERT INTO clients (name, mobile, gadi_no) VALUES (?, ?, ?)", 
                                      (client_name.value, client_mobile.value, client_gadi.value))
                conn.commit()
                client_name.value, client_mobile.value, client_gadi.value = "", "", ""
                refresh_data()
                show_snack("Client Added Successfully!")

        def add_to_cart(e):
            if pos_item_dropdown.value and pos_qty.value:
                item_id = int(pos_item_dropdown.value)
                qty = int(pos_qty.value)
                cursor = conn.cursor()
                cursor.execute("SELECT item_name, price, stock FROM inventory WHERE id=?", (item_id,))
                item = cursor.fetchone()
                
                if item and item[2] >= qty:
                    cart.append({"id": item_id, "name": item[0], "price": item[1], "qty": qty})
                    update_cart_ui()
                else:
                    show_snack("Not enough stock!", is_error=True)

        def update_cart_ui():
            cart_list.controls.clear()
            subtotal = 0
            for item in cart:
                item_total = item['price'] * item['qty']
                subtotal += item_total
                cart_list.controls.append(ft.Text(f"• {item['name']} x{item['qty']} = Rs. {item_total}", size=16))
            
            try: discount = float(pos_discount.value or 0)
            except ValueError: discount = 0
            
            total_text.value = f"Total: Rs. {subtotal - discount}"
            page.update()

        def checkout_and_whatsapp(e):
            if not pos_client_dropdown.value or not cart:
                show_snack("Select a client and add items to cart!", is_error=True)
                return
                
            client_id = int(pos_client_dropdown.value)
            cursor = conn.cursor()
            cursor.execute("SELECT name, mobile, gadi_no FROM clients WHERE id=?", (client_id,))
            client = cursor.fetchone()
            
            subtotal = 0
            invoice_lines = []
            for item in cart:
                item_total = item['price'] * item['qty']
                subtotal += item_total
                invoice_lines.append(f"▪ {item['name']} (x{item['qty']}): Rs. {item_total}")
                cursor.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))
            conn.commit()
            
            try: discount = float(pos_discount.value or 0)
            except ValueError: discount = 0
            
            msg = f"Hello {client[0]},\nInvoice for your vehicle *{client[2]}*\n\n" + "\n".join(invoice_lines)
            msg += f"\n\nSubtotal: Rs. {subtotal}\nDiscount: Rs. {discount}\n*Final Total: Rs. {subtotal - discount}*\n\nThank you for visiting!"
            
            mobile_no = client[1].replace("+", "").replace(" ", "")
            if len(mobile_no) == 10: mobile_no = "977" + mobile_no 
                
            wa_url = f"https://wa.me/{mobile_no}?text={urllib.parse.quote(msg)}"
            
            cart.clear()
            pos_discount.value = "0"
            update_cart_ui()
            refresh_data()
            page.launch_url(wa_url)

        def show_snack(text, is_error=False):
            page.open(ft.SnackBar(content=ft.Text(text), bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700))

        pos_discount.on_change = lambda e: update_cart_ui()

        # --- 5. SCREEN VIEWS ---
        pos_view = ft.Column([
            ft.Text("Point of Sale", size=24, weight=ft.FontWeight.BOLD),
            pos_client_dropdown, 
            ft.Row([pos_item_dropdown, pos_qty]),
            ft.Button(content="Add to Cart", on_click=add_to_cart, icon=ft.Icons.ADD_SHOPPING_CART, width=float('inf')),
            ft.Divider(), cart_list, pos_discount, total_text,
            ft.Button(content="Checkout & WhatsApp", on_click=checkout_and_whatsapp, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, height=50, width=float('inf'), icon=ft.Icons.SEND)
        ], expand=True, visible=True)

        inventory_view = ft.Column([
            ft.Text("Inventory Management", size=24, weight=ft.FontWeight.BOLD),
            ft.Row([inv_name]), ft.Row([inv_price, inv_stock]),
            ft.Button(content="Save Purchase", on_click=add_inventory, icon=ft.Icons.SAVE, width=float('inf')),
            ft.Divider(), ft.Text("Stock Status:", weight=ft.FontWeight.BOLD, size=18), inventory_list
        ], expand=True, visible=False)

        client_view = ft.Column([
            ft.Text("Client Registry", size=24, weight=ft.FontWeight.BOLD),
            client_name, client_mobile, client_gadi,
            ft.Button(content="Register Client", on_click=add_client, icon=ft.Icons.PERSON_ADD, width=float('inf')),
            ft.Divider(), ft.Text("Database:", weight=ft.FontWeight.BOLD, size=18), client_list
        ], expand=True, visible=False)

        main_content = ft.Container(content=ft.Column([pos_view, inventory_view, client_view], expand=True), padding=15, expand=True)

        # --- 6. SIDEBAR NAVIGATION ---
        def handle_drawer_change(e):
            pos_view.visible = False
            inventory_view.visible = False
            client_view.visible = False
            
            if e.control.selected_index == 0:
                pos_view.visible = True
                page.appbar.title.value = "Sales & POS"
            elif e.control.selected_index == 1:
                inventory_view.visible = True
                page.appbar.title.value = "Inventory"
            elif e.control.selected_index == 2:
                client_view.visible = True
                page.appbar.title.value = "Clients"
                
            page.drawer.open = False  
            page.update()

        app_drawer = ft.NavigationDrawer(
            on_change=handle_drawer_change,
            selected_index=0,
            controls=[
                ft.Container(height=20),
                ft.NavigationDrawerDestination(label="POS & Sales", icon=ft.Icons.POINT_OF_SALE),
                ft.NavigationDrawerDestination(label="Inventory", icon=ft.Icons.INVENTORY),
                ft.NavigationDrawerDestination(label="Clients", icon=ft.Icons.PEOPLE),
            ],
        )

        main_app_bar = ft.AppBar(
            leading=ft.IconButton(ft.Icons.MENU, on_click=lambda e: setattr(page.drawer, 'open', True) or page.update(), icon_color=ft.Colors.WHITE),
            title=ft.Text("Sales & POS", color=ft.Colors.WHITE),
            bgcolor=ft.Colors.BLUE_800
        )

        # --- 7. LOGIN SCREEN ---
        def handle_login(e):
            if username_input.value == "admin" and password_input.value == "Salam123":
                page.controls.clear()
                page.vertical_alignment = ft.MainAxisAlignment.START
                page.horizontal_alignment = ft.CrossAxisAlignment.START
                
                page.drawer = app_drawer
                page.appbar = main_app_bar
                page.add(main_content)
                refresh_data()
            else:
                show_snack("Invalid Login!", is_error=True)

        username_input = ft.TextField(label="Username", prefix_icon=ft.Icons.PERSON, width=300)
        password_input = ft.TextField(label="Password", prefix_icon=ft.Icons.LOCK, password=True, can_reveal_password=True, width=300)
        login_btn = ft.Button(content="Login", on_click=handle_login, width=300, height=45, bgcolor=ft.Colors.BLUE_800, color=ft.Colors.WHITE)

        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        page.add(ft.Column([
            ft.Icon(ft.Icons.GARAGE, size=80, color=ft.Colors.BLUE_800),
            ft.Text("Garage POS", size=28, weight=ft.FontWeight.BOLD),
            ft.Container(height=20), username_input, password_input, ft.Container(height=10), login_btn
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    except Exception as e:
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        page.add(
            ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=60),
            ft.Text("App Failed to Load", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
            ft.Text(traceback.format_exc(), color=ft.Colors.RED, selectable=True)
        )

ft.run(main)
