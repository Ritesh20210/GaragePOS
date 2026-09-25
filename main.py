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
        page.padding = 0  # To allow the custom sidebar to span the whole screen
        
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

        # --- 3. SMART SNACKBAR (CRASH-PROOF) ---
        def show_snack(text, is_error=False):
            color = ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700
            snack = ft.SnackBar(content=ft.Text(text, color=ft.Colors.WHITE), bgcolor=color)
            # Checks what version of Flet is running and uses the correct method instantly
            if hasattr(page, 'open'):
                page.open(snack)
            else:
                page.snack_bar = snack
                page.snack_bar.open = True
                page.update()

        # --- 4. BULLETPROOF BUTTONS (No lag, no crashes) ---
        def custom_btn(text, icon, color, on_click):
            return ft.Container(
                content=ft.Row([ft.Icon(icon, color=ft.Colors.WHITE), ft.Text(text, color=ft.Colors.WHITE, size=16, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
                bgcolor=color, height=50, border_radius=8, ink=True, on_click=on_click
            )

        # --- 5. UI VARIABLES ---
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

        # --- 6. APP LOGIC ---
        def refresh_data():
            cursor = conn.cursor()
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

            client_list.controls.clear()
            pos_client_dropdown.options.clear()
            cursor.execute("SELECT id, name, mobile, gadi_no FROM clients")
            for row in cursor.fetchall():
                client_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.DIRECTIONS_CAR),
                        title=ft.Text(f"{row[3]} - {row[1]}", weight=ft.FontWeight.BOLD), subtitle=ft.Text(row[2])
                    )
                )
                pos_client_dropdown.options.append(ft.dropdown.Option(key=str(row[0]), text=f"{row[3]} ({row[1]})"))
            page.update()

        def add_inventory(e):
            if inv_name.value and inv_price.value and inv_stock.value:
                conn.cursor().execute("INSERT INTO inventory (item_name, price, stock) VALUES (?, ?, ?)", (inv_name.value, float(inv_price.value), int(inv_stock.value)))
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
                conn.cursor().execute("INSERT INTO clients (name, mobile, gadi_no) VALUES (?, ?, ?)", (client_name.value, client_mobile.value, client_gadi.value))
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
            show_snack("Invoice Shared Successfully!")

        pos_discount.on_change = lambda e: update_cart_ui()

        # --- 7. SCREEN VIEWS ---
        pos_view = ft.Container(content=ft.Column([
            ft.Text("Point of Sale", size=24, weight=ft.FontWeight.BOLD), pos_client_dropdown, ft.Row([pos_item_dropdown, pos_qty]),
            custom_btn("Add to Cart", ft.Icons.ADD_SHOPPING_CART, ft.Colors.BLUE_700, add_to_cart),
            ft.Divider(), cart_list, pos_discount, total_text,
            custom_btn("Checkout & WhatsApp", ft.Icons.SEND, ft.Colors.GREEN_700, checkout_and_whatsapp)
        ], expand=True), padding=15, visible=True)

        inventory_view = ft.Container(content=ft.Column([
            ft.Text("Inventory Management", size=24, weight=ft.FontWeight.BOLD), ft.Row([inv_name]), ft.Row([inv_price, inv_stock]),
            custom_btn("Save Purchase", ft.Icons.SAVE, ft.Colors.BLUE_700, add_inventory),
            ft.Divider(), ft.Text("Stock Status:", weight=ft.FontWeight.BOLD, size=18), inventory_list
        ], expand=True), padding=15, visible=False)

        client_view = ft.Container(content=ft.Column([
            ft.Text("Client Registry", size=24, weight=ft.FontWeight.BOLD), client_name, client_mobile, client_gadi,
            custom_btn("Register Client", ft.Icons.PERSON_ADD, ft.Colors.BLUE_700, add_client),
            ft.Divider(), ft.Text("Database:", weight=ft.FontWeight.BOLD, size=18), client_list
        ], expand=True), padding=15, visible=False)

        # --- 8. LIGHT-SPEED CUSTOM SIDEBAR (AUTO-HIDE) ---
        def switch_tab(tab_name):
            pos_view.visible = (tab_name == "pos")
            inventory_view.visible = (tab_name == "inv")
            client_view.visible = (tab_name == "client")
            
            if tab_name == "pos": page.appbar.title.value = "Sales & POS"
            elif tab_name == "inv": page.appbar.title.value = "Inventory Management"
            elif tab_name == "client": page.appbar.title.value = "Client Registry"
            
            toggle_sidebar(None) # Automatically close sidebar!

        def toggle_sidebar(e):
            if sidebar.left == 0:
                sidebar.left = -250
                overlay_bg.visible = False
            else:
                sidebar.left = 0
                overlay_bg.visible = True
            page.update()

        def logout(e):
            page.controls.clear()
            page.appbar = None
            page.add(login_view)
            page.update()

        sidebar = ft.Container(
            width=250, left=-250, top=0, bottom=0, bgcolor=ft.Colors.WHITE,
            animate_position=ft.animation.Animation(250, ft.AnimationCurve.EASE_OUT),
            content=ft.Column([
                ft.Container(height=60, bgcolor=ft.Colors.BLUE_800, padding=10, content=ft.Row([ft.Icon(ft.Icons.GARAGE, color=ft.Colors.WHITE, size=30), ft.Text("Menu", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)])),
                ft.ListTile(leading=ft.Icon(ft.Icons.POINT_OF_SALE, color=ft.Colors.BLUE_800), title=ft.Text("POS & Sales", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("pos")),
                ft.ListTile(leading=ft.Icon(ft.Icons.INVENTORY, color=ft.Colors.BLUE_800), title=ft.Text("Inventory", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("inv")),
                ft.ListTile(leading=ft.Icon(ft.Icons.PEOPLE, color=ft.Colors.BLUE_800), title=ft.Text("Clients", weight=ft.FontWeight.BOLD), on_click=lambda e: switch_tab("client")),
                ft.Divider(),
                ft.ListTile(leading=ft.Icon(ft.Icons.EXIT_TO_APP, color=ft.Colors.RED_800), title=ft.Text("Logout", color=ft.Colors.RED_800, weight=ft.FontWeight.BOLD), on_click=logout)
            ])
        )

        overlay_bg = ft.Container(expand=True, left=0, right=0, top=0, bottom=0, bgcolor=ft.Colors.BLACK54, visible=False, on_click=toggle_sidebar)

        main_app_bar = ft.AppBar(
            leading=ft.IconButton(ft.Icons.MENU, on_click=toggle_sidebar, icon_color=ft.Colors.WHITE),
            title=ft.Text("Sales & POS", color=ft.Colors.WHITE), bgcolor=ft.Colors.BLUE_800
        )

        app_body = ft.Stack([
            ft.Column([pos_view, inventory_view, client_view], expand=True),
            overlay_bg, sidebar
        ], expand=True)

        # --- 9. LOGIN SCREEN ---
        def handle_login(e):
            if username_input.value == "admin" and password_input.value == "Salam123":
                page.controls.clear()
                page.appbar = main_app_bar
                page.add(app_body)
                refresh_data()
            else:
                show_snack("Invalid Login!", is_error=True)

        username_input = ft.TextField(label="Username", prefix_icon=ft.Icons.PERSON, width=300)
        password_input = ft.TextField(label="Password", prefix_icon=ft.Icons.LOCK, password=True, can_reveal_password=True, width=300)
        
        login_view = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.GARAGE, size=80, color=ft.Colors.BLUE_800), ft.Text("Garage POS", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(height=20), username_input, password_input, ft.Container(height=10),
                custom_btn("Login", ft.Icons.LOGIN, ft.Colors.BLUE_800, handle_login)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center, expand=True
        )

        page.add(login_view)

    except Exception as e:
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        page.add(
            ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=60),
            ft.Text("App Failed to Load", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
            ft.Text(traceback.format_exc(), color=ft.Colors.RED, selectable=True)
        )

ft.run(main)
