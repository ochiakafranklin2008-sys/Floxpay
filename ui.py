import flet as ft
import requests

API_BASE_URL = "http://127.0.0.1:8000"

def main(page: ft.Page):
    page.title = "Floxpay Pro"
    page.window.width = 410
    page.window.height = 820
    page.bgcolor = "#F5F6FA"  # Clean white/grey modern background
    page.scroll = ft.ScrollMode.ADAPTIVE

    session = {"phone": None, "balance_hidden": False, "raw_balance": 0.0}

    # --- UI STATE COMPONENTS ---
    user_greeting = ft.Text("Welcome to Floxpay", size=16, color="#1A1A1A", weight=ft.FontWeight.BOLD)
    bank_details_label = ft.Text("Sign in or Sign up below to generate your wallet", size=12, color="#666666")
    balance_label = ft.Text("₦0.00", size=32, weight=ft.FontWeight.BOLD, color="#FFFFFF")
    status_bar = ft.Text("", size=13, weight=ft.FontWeight.W_500)
    history_container = ft.Column(spacing=8)

    # --- INPUT COMPONENT FIELDS ---
    in_login_phone = ft.TextField(label="Mobile Phone Number", border_color="#10B981", focused_border_color="#059669", border_radius=10, bgcolor="white")
    in_reg_name = ft.TextField(label="Full Legal Name (As it appears on NIN)", border_radius=10, bgcolor="white")
    in_reg_phone = ft.TextField(label="Mobile Number", border_radius=10, bgcolor="white")
    in_reg_nin = ft.TextField(label="11-Digit NIN / BVN", max_length=11, border_radius=10, bgcolor="white")
    in_transfer_acc = ft.TextField(label="Beneficiary 10-Digit NUBAN Account", border_radius=10, bgcolor="white")
    in_transfer_amt = ft.TextField(label="Amount to Send (₦)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=10, bgcolor="white")

    # --- TOGGLE BALANCE VISIBILITY ---
    def toggle_balance(e):
        session["balance_hidden"] = not session["balance_hidden"]
        if session["balance_hidden"]:
            balance_label.value = "••••••"
            eye_button.icon = ft.icons.VISIBILITY_OFF
        else:
            balance_label.value = f"₦{session['raw_balance']:,.2f}"
            eye_button.icon = ft.icons.VISIBILITY
        page.update()

    eye_button = ft.IconButton(icon=ft.icons.VISIBILITY, icon_color="white", on_click=toggle_balance)

    # --- BACKEND INTEGRATION FUNCTIONS ---
    def sync_wallet_dashboard(phone):
        try:
            res = requests.get(f"{API_BASE_URL}/api/v1/wallet/{phone}")
            if res.status_code == 200:
                data = res.json()
                session["phone"] = phone
                session["raw_balance"] = data["balance"]
                
                user_greeting.value = f"Hello, {data['name']}"
                bank_details_label.value = f"{data['bank_partner']}  •  Account: {data['account_number']}"
                
                if not session["balance_hidden"]:
                    balance_label.value = f"₦{data['balance']:,.2f}"
                
                history_container.controls.clear()
                tx_list = data.get("history", [])
                
                if not tx_list:
                    history_container.controls.append(ft.Text("No transaction logs recorded yet.", size=12, color="#999999"))
                else:
                    for tx in tx_list:
                        history_container.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Column([
                                        ft.Text(f"Transfer to {tx['recipient_name']}", size=13, weight=ft.FontWeight.W_500, color="#1A1A1A"),
                                        ft.Text(f"Ref: {tx['reference']}", size=11, color="#888888")
                                    ]),
                                    ft.Text(f"-₦{tx['amount']:,.2f}", size=14, color="#EF4444", weight=ft.FontWeight.BOLD)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                padding=12, bgcolor="#F9FAFB", border_radius=10, border=ft.border.all(1, "#E5E7EB")
                            )
                        )
                status_bar.value = "Wallet data synced successfully."
                status_bar.color = "#10B981"
            else:
                status_bar.value = "Account lookup rejected."
                status_bar.color = "#EF4444"
        except Exception:
            status_bar.value = "Error: Core banking engine unreachable."
            status_bar.color = "#EF4444"
        page.update()

    def submit_login(e):
        phone = in_login_phone.value.strip()
        if not phone:
            status_bar.value = "Please enter your phone number."
            status_bar.color = "#F59E0B"
            page.update()
            return
        sync_wallet_dashboard(phone)

    def submit_signup(e):
        if not in_reg_name.value or not in_reg_phone.value or not in_reg_nin.value:
            status_bar.value = "All onboarding fields are required."
            status_bar.color = "#EF4444"
            page.update()
            return
        payload = {"full_name": in_reg_name.value.strip(), "phone_number": in_reg_phone.value.strip(), "nin": in_reg_nin.value.strip()}
        try:
            res = requests.post(f"{API_BASE_URL}/api/v1/auth/signup", json=payload)
            if res.status_code == 201:
                status_bar.value = "Account setup successful! ₦10k added."
                status_bar.color = "#10B981"
                sync_wallet_dashboard(payload["phone_number"])
            else:
                status_bar.value = res.json().get("detail", "Registration rejected.")
                status_bar.color = "#EF4444"
        except Exception:
            status_bar.value = "Handshake error with authentication server."
            status_bar.color = "#EF4444"
        page.update()

    def submit_transfer(e):
        if not session["phone"]:
            status_bar.value = "Please sign into your wallet first."
            status_bar.color = "#EF4444"
            page.update()
            return
        payload = {"sender_phone": session["phone"], "destination_account": in_transfer_acc.value.strip(), "amount": float(in_transfer_amt.value or 0)}
        try:
            res = requests.post(f"{API_BASE_URL}/api/v1/transfer/send", json=payload)
            if res.status_code == 200:
                status_bar.value = "Transfer completed successfully!"
                status_bar.color = "#10B981"
                in_transfer_acc.value = ""
                in_transfer_amt.value = ""
                sync_wallet_dashboard(session["phone"])
            else:
                status_bar.value = res.json().get("detail", "Transaction declined.")
                status_bar.color = "#EF4444"
        except Exception:
            status_bar.value = "Transaction engine connection timeout."
            status_bar.color = "#EF4444"
        page.update()

    # --- PREMIUM LAYOUT CONTAINER BOARDS ---
    premium_wallet_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Available Balance", size=12, color="#E0F2FE"),
                eye_button
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            balance_label,
            ft.Divider(color="#38BDF8", thickness=0.5),
            bank_details_label
        ]),
        padding=20,
        gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=["#0284C7", "#0369A1"]),
        border_radius=18,
        shadow=ft.BoxShadow(spread_radius=1, blur_radius=10, color="#30000000")
    )

    action_grid = ft.Row([
        ft.Column([ft.IconButton(icon=ft.icons.SEND, icon_color="#0284C7", bgcolor="#E0F2FE", icon_size=24), ft.Text("Transfer", size=11, color="#1A1A1A")], horizontal_alignment="center"),
        ft.Column([ft.IconButton(icon=ft.icons.PHONE_ANDROID, icon_color="#10B981", bgcolor="#D1FAE5", icon_size=24), ft.Text("Airtime", size=11, color="#1A1A1A")], horizontal_alignment="center"),
        ft.Column([ft.IconButton(icon=ft.icons.LIGHTBULB, icon_color="#F59E0B", bgcolor="#FEF3C7", icon_size=24), ft.Text("Bills", size=11, color="#1A1A1A")], horizontal_alignment="center"),
        ft.Column([ft.IconButton(icon=ft.icons.CREDIT_CARD, icon_color="#6366F1", bgcolor="#E0E7FF", icon_size=24), ft.Text("Cards", size=11, color="#1A1A1A")], horizontal_alignment="center"),
    ], alignment=ft.MainAxisAlignment.SPACE_AROUND)

    # --- PACKAGING MAIN SCREEN MOUNT ---
    page.add(
        ft.Container(
            content=ft.Column([
                ft.Row([user_greeting, ft.Icon(ft.icons.NOTIFICATIONS_OUTLINED, color="#1A1A1A")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                premium_wallet_card,
                ft.Container(content=action_grid, padding=ft.padding.symmetric(vertical=10)),
                
                # Sign In Framework Section
                ft.Card(content=ft.Container(content=ft.Column([
                    ft.Text("Access Existing Account", size=14, weight=ft.FontWeight.BOLD, color="#1A1A1A"),
                    in_login_phone,
                    ft.ElevatedButton("Secure Log In", on_click=submit_login, bgcolor="#0284C7", color="white", width=360, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ]), padding=15), bgcolor="white"),
                
                # Sign Up Framework Section
                ft.Card(content=ft.Container(content=ft.Column([
                    ft.Text("Open Instant Digital Account (KYC Tier-1)", size=14, weight=ft.FontWeight.BOLD, color="#1A1A1A"),
                    in_reg_name, in_reg_phone, in_reg_nin,
                    ft.ElevatedButton("Verify & Activate Wallet", on_click=submit_signup, bgcolor="#10B981", color="white", width=360, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ]), padding=15), bgcolor="white"),
                
                # Fund Interbank Routing Section
                ft.Card(content=ft.Container(content=ft.Column([
                    ft.Text("Send Funds Instant NIP Router", size=14, weight=ft.FontWeight.BOLD, color="#1A1A1A"),
                    in_transfer_acc, in_transfer_amt,
                    ft.ElevatedButton("Authorize Fund Transfer", on_click=submit_transfer, bgcolor="#EF4444", color="white", width=360, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ]), padding=15), bgcolor="white"),
                
                # Transaction History View
                ft.Text("Transaction Ledger Logs", size=14, weight=ft.FontWeight.BOLD, color="#1A1A1A"),
                history_container,
                ft.Divider(height=10, color="transparent"),
                status_bar
            ], spacing=16),
            padding=15
        )
    )

if __name__ == "__main__":
    ft.app(target=main)