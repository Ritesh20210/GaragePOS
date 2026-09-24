import flet as ft
import sqlite3
import urllib.parse

# ==========================================
# 1. DATABASE SETUP (OFFLINE SQLITE)
# ==========================================
def init_db():
    conn = sqlite3.connect("garage_pos.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Inventory Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_name TEXT,
                        price REAL,
                        stock INTEGER)''')
                        
    # Clients Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS clients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        mobile TEXT,
                        gadi_no TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 2. MAIN GUI APPLICATION
# ==========================================
def main(page: ft.Page):
    # Modern Flet window properties (Zero Legacy)
    page.title = "Auto Workshop Garage POS"
    page.window.width = 400
    page.window.height = 800
    page.theme_mode = ft.ThemeMode.LIGHT
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    # State Variables
    cart = []

    # ==========================================
    # 3. APP UI COMPONENTS
    # ==========================================
    # --- UI Elements: Inventory ---
    inv_name = ft.TextField(label="Item Name", prefix_icon=ft.icons.BUILD)
    inv_price = ft.TextField(label="Selling Price", keyboard_type=ft.KeyboardType.NUMBER, prefix_icon=ft.icons.MONETIZATION_ON)
    inv_stock = ft.TextField(label="Stock Qty", keyboard_type=ft.KeyboardType.NUMBER, prefix_icon=ft.icons.LAYERS)
    inventory_list = ft.ListView(expand=True, spacing=10)

    # --- UI Elements: Client ---
    client_name = ft.TextField(label="Client Name", prefix_icon=ft.icons.PERSON)
    client_mobile = ft.TextField(label="Mobile No. (ex: 98XXXXXX)", keyboard_type=ft.KeyboardType.PHONE, prefix_icon=ft.icons.PHONE)
    client_gadi = ft.TextField(label="Gadi No. (ex: BA 1 PA 1234)", prefix_icon=ft.icons.DIRECTIONS_CAR)
    client_list = ft.ListView(expand=True, spacing=10)

    # --- UI Elements: POS / Sales ---
    pos_client_dropdown = ft.Dropdown(label="Select Client (Gadi No)")
    pos_item_dropdown = ft.Dropdown(label="Select Item")
    pos_qty = ft.TextField(label="Qty", value="1", width=80, keyboard_type=ft.KeyboardType.NUMBER)
    pos_discount = ft.TextField(label="Discount (Rs)", value="0", width=120, keyboard_type=ft.KeyboardType.NUMBER)
    cart_list = ft.ListView(expand=True, spacing=10)
    total_text = ft.Text("Total: Rs. 0", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_900)

    # ==========================================
    # 4. HELPER FUNCTIONS & LOGIC
    # ==========================================
    def refresh_data():
        """Fetches latest DB data and updates dropdowns and lists."""
        cursor = conn.cursor()
        
        # Refresh Inventory List
        inventory_list.controls.clear()
        pos_item_dropdown.options.clear()
        cursor.execute("SELECT id, item_name, price, stock FROM inventory")
        for row in cursor.fetchall():
            item_id, name, price, stock = row
            inventory_list.controls.append(
                ft.ListTile(
                    title=ft.Text(f"{name} (Stock: {stock})", weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(f"Rs. {price}"),
                    trailing=ft.IconButton(
                        ft.icons.DELETE, 
                        icon_color=ft.colors.RED,
                        on_click=lambda e, i=item_id: delete_item(i)
                    )
                )
            )
            pos_item_dropdown.options.append(ft.dropdown.Option(key=str(item_id), text=f"{name} - Rs.{price}"))

        # Refresh Client List
        client_list.controls.clear()
        pos_client_dropdown.options.clear()
        cursor.execute("SELECT id, name, mobile, gadi_no FROM clients")
        for row in cursor.fetchall():
            c_id, name, mob, gadi = row
            client_list.controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.icons.DIRECTIONS_CAR),
                    title=ft.Text(f"{gadi} - {name}", weight=ft.FontWeight.BOLD), 
                    subtitle=ft.Text(mob)
                )
            )
            pos_client_dropdown.options.append(ft.dropdown.Option(key=str(c_id), text=f"{gadi} ({name})"))

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
        
        try:
            discount = float(pos_discount.value or 0)
        except ValueError:
            discount = 0
            
        final_total = subtotal - discount
        total_text.value = f"Total: Rs. {final_total}"
        page.update()

    def checkout_and_whatsapp(e):
        if not pos_client_dropdown.value or not cart:
            show_snack("Please select a client and add items to cart!", is_error=True)
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
        
        try:
            discount = float(pos_discount.value or 0)
        except ValueError:
            discount = 0
            
        final_total = subtotal - discount
        
        # Format WhatsApp Message
        msg = f"Hello {client[0]},\n"
        msg += f"Invoice for your vehicle *{client[2]}*\n\n"
        msg += "\n".join(invoice_lines)
        msg += f"\n\nSubtotal: Rs. {subtotal}\nDiscount: Rs. {discount}\n"
        msg += f"*Final Total: Rs. {final_total}*\n\nThank you for visiting our Garage!"
        
        mobile_no = client[1].replace("+", "").replace(" ", "")
        if len(mobile_no) == 10: 
            mobile_no = "977" + mobile_no 
            
        encoded_msg = urllib.parse.quote(msg)
        wa_url = f"https://wa.me/{mobile_no}?text={encoded_msg}"
        
        # Reset cart and UI
        cart.clear()
        pos_discount.value = "0"
        update_cart_ui()
        refresh_data()
        
        # Open WhatsApp
        page.launch_url(wa_url)

    # Modern Flet SnackBar handling (Zero Legacy)
    def show_snack(text, is_error=False):
        color = ft.colors.RED_700 if is_error else ft.colors.GREEN_700
        page.open(ft.SnackBar(content=ft.Text(text), bgcolor=color))

    # Trigger UI update whenever discount text changes
    pos_discount.on_change = lambda e: update_cart_ui()

    # ==========================================
    # 5. APP LAYOUT & TABS
    # ==========================================
    pos_tab = ft.Tab(text="POS & Invoice", icon=ft.icons.POINT_OF_SALE, content=ft.Column([
        ft.Container(height=10),
        pos_client_dropdown,
        ft.Row([pos_item_dropdown, pos_qty]),
        ft.ElevatedButton("Add to Cart", on_click=add_to_cart, icon=ft.icons.ADD_SHOPPING_CART),
        ft.Divider(),
        cart_list,
        pos_discount,
        total_text,
        ft.ElevatedButton("Generate & WhatsApp Invoice", on_click=checkout_and_whatsapp, 
                          bgcolor=ft.colors.GREEN_700, color=ft.colors.WHITE, height=50, width=float('inf'),
                          icon=ft.icons.SEND)
    ]))

    inventory_tab = ft.Tab(text="Inventory", icon=ft.icons.INVENTORY, content=ft.Column([
        ft.Container(height=10),
        inv_name, inv_price, inv_stock,
        ft.ElevatedButton("Save Purchase Item", on_click=add_inventory, icon=ft.icons.SAVE, width=float('inf')),
        ft.Divider(),
        ft.Text("Current Stock:", weight=ft.FontWeight.BOLD, size=18),
        inventory_list
    ]))

    client_tab = ft.Tab(text="Clients", icon=ft.icons.PEOPLE, content=ft.Column([
        ft.Container(height=10),
        client_name, client_mobile, client_gadi,
        ft.ElevatedButton("Register Client", on_click=add_client, icon=ft.icons.PERSON_ADD, width=float('inf')),
        ft.Divider(),
        ft.Text("Client Database:", weight=ft.FontWeight.BOLD, size=18),
        client_list
    ]))

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[pos_tab, inventory_tab, client_tab],
        expand=True
    )

    # ==========================================
    # 6. AUTHENTICATION (LOGIN SCREEN)
    # ==========================================
    def handle_login(e):
        if username_input.value == "admin" and password_input.value == "Salam123":
            # Clear login screen, setup main app structure
            page.controls.clear()
            page.vertical_alignment = ft.MainAxisAlignment.START
            page.horizontal_alignment = ft.CrossAxisAlignment.START
            page.add(tabs)
            refresh_data()
        else:
            show_snack("Invalid Username or Password!", is_error=True)

    username_input = ft.TextField(label="Username", prefix_icon=ft.icons.PERSON, width=300)
    password_input = ft.TextField(label="Password", prefix_icon=ft.icons.LOCK, password=True, can_reveal_password=True, width=300)
    login_btn = ft.ElevatedButton("Login", on_click=handle_login, width=300, height=45, bgcolor=ft.colors.BLUE_800, color=ft.colors.WHITE)

    login_view = ft.Column(
        controls=[
            ft.Icon(ft.icons.GARAGE, size=80, color=ft.colors.BLUE_800),
            ft.Text("Garage POS System", size=28, weight=ft.FontWeight.BOLD),
            ft.Text("Please login to continue", size=14, color=ft.colors.GREY_700),
            ft.Container(height=20),
            username_input,
            password_input,
            ft.Container(height=10),
            login_btn
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # Start the app by showing only the login screen
    page.add(login_view)

# Run the Application
ft.app(target=main)
