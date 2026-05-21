import flet as ft
import requests

API_BASE_URL = "http://127.0.0.1:8000"

def main(page: ft.Page):
    page.title = "Floxpay Nigeria"
    page.window.width = 430
    page.window.height = 840
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.ADAPTIVE

    session = {"phone": None}

    # UI Display Components
    brand_header = ft.Text("FLOXPAY NIGERIA", size=26, weight=ft.FontWeight.BOLD, color="orange")
    user_welcome = ft.Text("Secure Digital Ledger System", size=14, color="grey")
    
    account_label = ft.Text("Account: Log in to view details", size=13, color="grey")
    balance_label = ft.Text("₦0.00", size=38, weight=ft.FontWeight.BOLD, color="white")
    status_bar = ft.Text("", size=14, weight=ft.FontWeight.W_500)
    
    history_container = ft.Column(spacing=5)

    # Form fields
    in_login_phone = ft.TextField(label="Registered Phone Number", hint_text="e.g. 08011112222")
    in_transfer_acc = ft.TextField(label="Beneficiary 10-Digit Account")
    in_transfer_amt = ft.TextField(label="Amount (₦)", keyboard_type=ft.KeyboardType.NUMBER)

    in_reg_name = ft.TextField(label="Full Legal Name")
    in_reg_phone = ft.TextField(label="Mobile Number")
    in_reg_bvn = ft.TextField(label="11-Digit BVN (Optional if NIN is filled)", max_length=11)
    in_reg_nin = ft.TextField(label="11-Digit NIN (Optional if BVN is filled)", max_length=11)

    def sync_dashboard(phone):
        try:
            res = requests.get(f"{API_BASE_URL}/api/v1/wallet/{phone}")
            if res.status_code == 200:
                data = res.json()
                user_welcome.value = f"Welcome, {data['name']}"
                account_label.value = f"{data['bank_partner']} | Nuban: {data['account_number']}"
                balance_label.value = f"₦{data['balance']:,.2f}"
                session["phone"] = phone
                
                history_container.controls.clear()
                tx_list = data.get("history", [])
                
                if not tx_list:
                    history_container.controls.append(ft.Text("No recent transaction logs found.", size=12, color="grey"))
                else:
                    for tx in tx_list:
                        history_container.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Column([
                                        ft.Text(f"To: {tx['recipient_name']}", size=12, weight=ft.FontWeight.BOLD),
                                        ft.Text(f"Ref: {tx['reference']}", size=10, color="grey")
                                    ]),
                                    ft.Text(f"₦{tx['amount']:,.2f}", size=13, color="red", weight=ft.FontWeight.BOLD)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                padding=10, bgcolor="black", border_radius=6
                            )
                        )
                status_bar.value = "Wallet ledger update completed."
                status_bar.color = "green"
            else:
                status_bar.value = "Lookup rejected by clearing interface."
                status_bar.color = "red"
        except Exception:
            status_bar.value = "CRITICAL: Floxpay secure background core is unreachable."
            status_bar.color = "red"
        page.update()

    def action_login(e):
        p = in_login_phone.value.strip()
        if not p:
            status_bar.value = "Please complete entry requirement."
            status_bar.color = "orange"
            page.update()
            return
        sync_dashboard(p)

    def action_signup(e):
        name = in_reg_name.value.strip()
        phone = in_reg_phone.value.strip()
        bvn = in_reg_bvn.value.strip()
        nin = in_reg_nin.value.strip()

        # Check core fields first
        if not name or not phone:
            status_bar.value = "Name and Mobile Number fields are mandatory!"
            status_bar.color = "red"
            page.update()
            return

        # Flexible Check: Ensure AT LEAST one of BVN or NIN has data
        if not bvn and not nin:
            status_bar.value = "Please enter either your BVN or your NIN to verify."
            status_bar.color = "orange"
            page.update()
            return
        
        payload = {
            "full_name": name,
            "phone_number": phone,
            "bvn": bvn if bvn else None,
            "nin": nin if nin else None
        }
        
        try:
            res = requests.post(f"{API_BASE_URL}/api/v1/auth/signup", json=payload)
            if res.status_code == 201:
                status_bar.value = "Account Activated! Welcome bonus of ₦10k added."
                status_bar.color = "green"
                sync_dashboard(payload["phone_number"])
            else:
                status_bar.value = res.json().get("detail", "Registration failed.")
                status_bar.color = "red"
        except Exception:
            status_bar.value = "Handshake error to verification servers."
            status_bar.color = "red"
        page.update()

    def action_transfer(e):
        if not session["phone"]:
            status_bar.value = "Please sign in to authenticate session tokens."
            status_bar.color = "red"
            page.update()
            return
        
        payload = {
            "sender_phone": session["phone"],
            "destination_account": in_transfer_acc.value.strip(),
            "amount": float(in_transfer_amt.value or 0)
        }
        
        try:
            res = requests.post(f"{API_BASE_URL}/api/v1/transfer/send", json=payload)
            if res.status_code == 200:
                status_bar.value = "Settlement execution completed via NIP core switch!"
                status_bar.color = "green"
                sync_dashboard(session["phone"])
            else:
                status_bar.value = res.json().get("detail", "Transaction declined.")
                status_bar.color = "red"
        except Exception:
            status_bar.value = "Internal transaction clearance processing timeout."
            status_bar.color = "red"
        page.update()

    balance_card = ft.Container(
        content=ft.Column([
            account_label,
            ft.Text("Available Balance (NGN)", size=11, color="orange"),
            balance_label
        ]),
        padding=20, bgcolor="grey", border_radius=16
    )

    history_card = ft.Container(
        content=ft.Column([
            ft.Text("Recent Transaction History Logs", size=13, weight=ft.FontWeight.BOLD, color="orange"),
            ft.Divider(color="grey"),
            history_container
        ]),
        padding=15, bgcolor="black", border_radius=12
    )

    page.add(
        ft.Container(
            content=ft.Column([
                brand_header, user_welcome,
                balance_card,
                ft.Divider(color="grey"),
                ft.Text("Account Access (Sign In)", size=14, weight=ft.FontWeight.BOLD, color="orange"),
                in_login_phone,
                ft.ElevatedButton("Login to Floxpay Account", on_click=action_login, bgcolor="orange", color="white", width=390),
                ft.Divider(color="grey"),
                ft.Text("Open Instant Floxpay Wallet", size=14, weight=ft.FontWeight.BOLD, color="orange"),
                in_reg_name, in_reg_phone, in_reg_bvn, in_reg_nin,
                ft.ElevatedButton("Register (BVN / NIN)", on_click=action_signup, bgcolor="black", color="white", width=390),
                ft.Divider(color="grey"),
                ft.Text("Instant NIP Interbank Funds Router", size=14, weight=ft.FontWeight.BOLD, color="orange"),
                in_transfer_acc, in_transfer_amt,
                ft.ElevatedButton("Authorize Fund Settlement", on_click=action_transfer, bgcolor="green", color="white", width=390),
                ft.Divider(color="grey"),
                history_card,
                ft.Divider(color="grey"),
                status_bar
            ], spacing=14),
            padding=15
        )
    )

if __name__ == "__main__":
    ft.app(target=main)