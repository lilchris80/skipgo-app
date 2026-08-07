import streamlit as st
from supabase import create_client
from datetime import date
import math
import base64
import uuid
import streamlit.components.v1 as components
from pdf_generator import generate_invoice_pdf, generate_quote_pdf
from reports import build_invoices_csv, build_quotes_csv, generate_invoice_report_pdf, generate_quote_report_pdf
from streamlit_cookies_controller import CookieController

def calculate_amount_due(start_date_str, end_date_str, base_price, weekly_late_rate, free_days, grace_days=0):
    """
    Works out the total owed for a rental: the base price, plus a late fee
    if it's been kept longer than the free period (e.g. 30 days) plus a
    grace window (e.g. 3 extra days that are still free before charging starts).
    Counts from the start date to either the return date (if returned)
    or today (if still out).
    """
    start = date.fromisoformat(start_date_str)
    end = date.fromisoformat(end_date_str) if end_date_str else date.today()
    days_out = (end - start).days

    if days_out <= free_days + grace_days:
        late_fee = 0.0
        weeks_late = 0
    else:
        extra_days = days_out - (free_days + grace_days)
        weeks_late = math.ceil(extra_days / 7)
        late_fee = weeks_late * weekly_late_rate

    return {
        "days_out": days_out,
        "weeks_late": weeks_late,
        "late_fee": late_fee,
        "total_due": base_price + late_fee
    }

def fmt_date(value):
    """
    Converts a date (either an ISO string like '2026-08-03' from the
    database, or a real date object from a date picker) into DD/MM/YYYY
    for display. Anything that isn't a real date (None, 'Not set', etc.)
    is returned unchanged rather than causing an error.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%d/%m/%Y")

# ----------------------------------------------------------------
# CONNECTION SETUP
# ----------------------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_client()

def pdf_view_button(label, pdf_bytes):
    """
    Renders a button that opens a PDF in a new browser tab using the
    browser's own PDF viewer, rather than forcing a download.

    Technical note: a plain link straight to a base64 PDF (data: URL)
    gets silently blocked by modern Chrome/Edge when opened in a new tab
    - this is a deliberate anti-phishing restriction, not a bug. The
    workaround is to convert the PDF into a temporary in-browser file
    (a "Blob") using JavaScript, and open THAT instead - blob: URLs
    aren't subject to the same block.
    """
    b64 = base64.b64encode(pdf_bytes).decode()
    button_id = f"pdfbtn_{uuid.uuid4().hex}"
    html = f"""
    <button id="{button_id}" style="display:inline-block;padding:0.5em 1.1em;
        background-color:#035B2B;color:white;border:none;border-radius:6px;
        font-weight:600;font-size:14px;cursor:pointer;margin:4px 0;">
        {label}
    </button>
    <script>
    document.getElementById("{button_id}").addEventListener("click", function() {{
        const b64 = "{b64}";
        const byteChars = atob(b64);
        const byteNumbers = new Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) {{
            byteNumbers[i] = byteChars.charCodeAt(i);
        }}
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], {{ type: "application/pdf" }});
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
    }});
    </script>
    """
    components.html(html, height=50)

st.set_page_config(page_title="SkipGO", page_icon="🗑️", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background-color: #FFFFFF;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    h3 {
        color: #035B2B !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------------------------------------------------
# LOGIN
# ----------------------------------------------------------------
COOKIE_NAME = "skipgo_refresh_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 400  # 400 days — the maximum browsers allow.
# This gets refreshed to a new 400-day window every time the app is opened,
# so as long as it's used at least once within any 400-day stretch, it
# effectively never expires. After 400 days of total inactivity, a normal
# login is needed again.

cookies = CookieController()

if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.company = None

def _load_company_for_user(user_id):
    profile = supabase.table("app_users").select("*").eq("id", user_id).single().execute()
    company_id = profile.data["company_id"]
    company = supabase.table("companies").select("*").eq("id", company_id).single().execute()
    return company.data

USERNAME_DOMAIN = "@skipgo.internal"

def login(username, password):
    try:
        email = username.strip().lower() + USERNAME_DOMAIN
        result = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = result.user
        st.session_state.company = _load_company_for_user(result.user.id)

        if result.session and result.session.refresh_token:
            cookies.set(COOKIE_NAME, result.session.refresh_token, max_age=COOKIE_MAX_AGE)

        st.rerun()
    except Exception as e:
        st.error("Login failed — check your username and password.")

def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.company = None
    cookies.remove(COOKIE_NAME)
    st.rerun()

# If this browser isn't already logged in for this session (e.g. the page
# was just refreshed), try to silently restore login using the saved cookie
# before showing the login screen.
if not st.session_state.user:
    saved_refresh_token = cookies.get(COOKIE_NAME)
    if saved_refresh_token:
        try:
            result = supabase.auth.refresh_session(saved_refresh_token)
            st.session_state.user = result.user
            st.session_state.company = _load_company_for_user(result.user.id)
            if result.session and result.session.refresh_token:
                cookies.set(COOKIE_NAME, result.session.refresh_token, max_age=COOKIE_MAX_AGE)
        except Exception:
            # Saved token is invalid or expired — fall through to a normal login screen.
            cookies.remove(COOKIE_NAME)

if not st.session_state.user:
    st.image("cycraftware_logo.png", width=200)
    st.title("SkipGO Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Log in", type="primary"):
        login(username, password)
    st.stop()

# ----------------------------------------------------------------
# LOGGED IN — MAIN APP
# ----------------------------------------------------------------
company = st.session_state.company
company_id = company["id"]

def show_center_popup(message):
    """
    Shows a centered, blue confirmation pop-up (like the ones used in
    Hylates) instead of Streamlit's default corner toast. It's rendered
    via a small piece of JavaScript that attaches directly to the main
    page (not just the small embedded frame this code runs in), so it
    appears centered on the whole screen, then fades out on its own.
    """
    html = f"""
    <script>
    (function() {{
        var popup = window.parent.document.createElement('div');
        popup.innerText = "✅ {message}";
        popup.style.position = "fixed";
        popup.style.top = "50%";
        popup.style.left = "50%";
        popup.style.transform = "translate(-50%, -50%)";
        popup.style.backgroundColor = "#1565C0";
        popup.style.color = "white";
        popup.style.padding = "16px 28px";
        popup.style.borderRadius = "10px";
        popup.style.fontSize = "16px";
        popup.style.fontWeight = "600";
        popup.style.fontFamily = "sans-serif";
        popup.style.boxShadow = "0 4px 20px rgba(0,0,0,0.3)";
        popup.style.zIndex = "999999";
        popup.style.opacity = "1";
        popup.style.transition = "opacity 0.5s ease";
        window.parent.document.body.appendChild(popup);
        setTimeout(function() {{ popup.style.opacity = "0"; }}, 1800);
        setTimeout(function() {{ popup.remove(); }}, 2300);
    }})();
    </script>
    """
    components.html(html, height=0, width=0)

# Show a brief pop-up confirmation for whatever action just happened
# (e.g. "Invoice created"), if one was queued right before this page load.
if st.session_state.get("toast_message"):
    show_center_popup(st.session_state["toast_message"])
    del st.session_state["toast_message"]

st.markdown(
    f"""
    <div style='display: flex; align-items: center; gap: 14px; padding: 6px 0 10px 0;'>
        <img src="data:image/png;base64,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" style="height: 46px;">
        <div style='height: 32px; width: 1px; background-color: #dddddd;'></div>
        <div style='font-size: 32px; font-weight: 700; color: #333333;'>{company['name']}</div>
    </div>
    """,
    unsafe_allow_html=True
)

if st.button("Log out"):
    logout()

tab_skips, tab_rentals, tab_new_rental, tab_clients, tab_invoices, tab_quotes, tab_history, tab_settings = st.tabs(
    ["Skips", "Active Rentals", "New Rental", "Clients", "Invoices", "Quotes", "Client History", "Settings"]
)

# ----------------------------------------------------------------
# TAB: SKIPS
# ----------------------------------------------------------------
with tab_skips:
    st.subheader("All Skips")
    skips = supabase.table("skips").select("*, skip_types(size_label, gross_price)").eq("company_id", company_id).execute().data
    skip_types = supabase.table("skip_types").select("*").eq("company_id", company_id).order("gross_price").execute().data

    if not skips:
        st.info("No skips added yet.")
    for skip in skips:
        status_emoji = "🟢" if skip["status"] == "available" else "🔴" if skip["status"] == "rented" else "🟡"
        size_label = skip["skip_types"]["size_label"] if skip.get("skip_types") else (skip.get("size") or "size not set")
        with st.container(border=True):
            st.write(f"{status_emoji} **Skip {skip['skip_number']}** — {size_label} — {skip['status']}")

    st.divider()
    st.subheader("Add a new skip")
    if not skip_types:
        st.warning("No skip sizes/prices set up yet for this company.")
    else:
        size_options = {f"{t['size_label']} (€{t['gross_price']:.2f})": t["id"] for t in skip_types}
        with st.form("add_skip", clear_on_submit=True):
            new_number = st.text_input("Skip number")
            chosen_size = st.selectbox("Size", options=list(size_options.keys()))
            if st.form_submit_button("Add Skip"):
                supabase.table("skips").insert({
                    "company_id": company_id,
                    "skip_number": new_number,
                    "skip_type_id": size_options[chosen_size],
                    "status": "available"
                }).execute()
                st.session_state.toast_message = "Skip added."
                st.rerun()

# ----------------------------------------------------------------
# TAB: ACTIVE RENTALS
# ----------------------------------------------------------------
with tab_rentals:
    st.subheader("Active Rentals")
    rentals = supabase.table("rentals").select(
        "*, clients(name, phone), skips(skip_number)"
    ).eq("company_id", company_id).is_("end_date", "null").execute().data

    available_skips_for_swap = supabase.table("skips").select("*, skip_types(size_label, gross_price)").eq("company_id", company_id).eq("status", "available").execute().data

    if not rentals:
        st.info("No active rentals.")
    free_days = int(company["settings"].get("free_days", 30))
    grace_days = int(company["settings"].get("grace_days", 3))
    for r in rentals:
        client_name = r["clients"]["name"] if r["clients"] else "Unknown client"
        skip_number = r["skips"]["skip_number"] if r["skips"] else "?"
        amounts = calculate_amount_due(r["start_date"], None, float(r["base_price"]), float(r["weekly_late_rate"]), free_days, grace_days)
        with st.container(border=True):
            st.markdown(f"**Skip {skip_number}** — {client_name} — started {fmt_date(r['start_date'])}")
            st.caption(f"{amounts['days_out']} days out. " + (
                f"⚠️ {amounts['weeks_late']} week(s) late — €{amounts['late_fee']:.2f} late fee added"
                if amounts["weeks_late"] > 0 else "Within free period."
            ) + f" **Total due: €{amounts['total_due']:.2f}**")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Mark Returned", key=f"return_{r['id']}"):
                    supabase.table("rentals").update({"end_date": str(date.today())}).eq("id", r["id"]).execute()
                    supabase.table("skips").update({"status": "available"}).eq("id", r["skip_id"]).execute()
                    st.session_state.toast_message = f"Skip {skip_number} marked as returned."
                    st.rerun()
            with col2:
                if r["payment_status"] != "Paid":
                    if st.button("Mark Paid", key=f"paid_{r['id']}"):
                        supabase.table("rentals").update({"payment_status": "Paid"}).eq("id", r["id"]).execute()
                        st.session_state.toast_message = "Marked as paid."
                        st.rerun()
                else:
                    st.write("✅ Paid")
            with col3:
                if st.button("🔄 Swap Skip", key=f"swap_toggle_{r['id']}"):
                    st.session_state[f"swapping_{r['id']}"] = not st.session_state.get(f"swapping_{r['id']}", False)

            if st.session_state.get(f"swapping_{r['id']}", False):
                st.caption("Closes this rental today and opens a new one with a different skip, for the same client.")
                if not available_skips_for_swap:
                    st.warning("No other available skips to swap to.")
                else:
                    swap_options = {
                        f"Skip {s['skip_number']} — {s['skip_types']['size_label'] if s.get('skip_types') else 'size not set'}": s["id"]
                        for s in available_skips_for_swap
                    }
                    chosen_swap = st.selectbox("New skip", options=list(swap_options.keys()), key=f"swap_select_{r['id']}")
                    if st.button("Confirm Swap", key=f"swap_confirm_{r['id']}", type="primary"):
                        old_skip_id = r["skip_id"]
                        new_skip_id = swap_options[chosen_swap]

                        supabase.table("rentals").update({"end_date": str(date.today())}).eq("id", r["id"]).execute()
                        supabase.table("skips").update({"status": "available"}).eq("id", old_skip_id).execute()

                        supabase.table("rentals").insert({
                            "company_id": company_id,
                            "client_id": r["client_id"],
                            "skip_id": new_skip_id,
                            "start_date": str(date.today()),
                            "base_price": r["base_price"],
                            "weekly_late_rate": r["weekly_late_rate"],
                            "payment_status": "Pending",
                            "created_at": "now()"
                        }).execute()
                        supabase.table("skips").update({"status": "rented"}).eq("id", new_skip_id).execute()

                        st.session_state[f"swapping_{r['id']}"] = False
                        st.session_state.toast_message = f"Swapped to {chosen_swap} for {client_name}."
                        st.rerun()

# ----------------------------------------------------------------
# TAB: NEW RENTAL
# ----------------------------------------------------------------
with tab_new_rental:
    st.subheader("Create a New Rental")

    clients = supabase.table("clients").select("*").eq("company_id", company_id).execute().data
    available_skips = supabase.table("skips").select("*, skip_types(size_label, gross_price, weekly_late_rate)").eq("company_id", company_id).eq("status", "available").execute().data

    if not clients:
        st.warning("Add a client first (see the Clients tab).")
    elif not available_skips:
        st.warning("No available skips — add one in the Skips tab.")
    else:
        client_options = {c["name"]: c["id"] for c in clients}
        skip_options = {s["skip_number"]: s for s in available_skips}
        free_days = int(company["settings"].get("free_days", 30))
        grace_days = int(company["settings"].get("grace_days", 3))

        form_key = st.session_state.get("rental_form_key", 0)

        chosen_client = st.selectbox("Client", options=list(client_options.keys()), key=f"client_{form_key}")
        chosen_skip_number = st.selectbox("Skip", options=list(skip_options.keys()), key=f"skip_{form_key}")
        chosen_skip = skip_options[chosen_skip_number]
        skip_type = chosen_skip.get("skip_types") or {}
        default_price = float(skip_type.get("gross_price", 0))
        default_weekly_rate = float(skip_type.get("weekly_late_rate", company["settings"].get("weekly_late_rate", 0)))

        delivery_date = st.date_input("Delivery date", value=date.today(), key=f"delivery_{form_key}", format="DD/MM/YYYY")
        estimated_pickup = st.date_input("Estimated pickup date (optional — for planning only)", value=None, key=f"pickup_{form_key}", format="DD/MM/YYYY")

        base_price = st.number_input("Base price (€)", min_value=0.0, value=default_price, step=5.0, key=f"price_{form_key}")
        weekly_rate = st.number_input("Weekly late rate (€)", min_value=0.0, value=default_weekly_rate, step=5.0, key=f"rate_{form_key}")

        if estimated_pickup:
            preview = calculate_amount_due(
                str(delivery_date), str(estimated_pickup), base_price, weekly_rate, free_days, grace_days
            )
            st.info(
                f"📋 **Preview based on estimated pickup ({fmt_date(estimated_pickup)}):**\n\n"
                f"{preview['days_out']} days total. " +
                (f"⚠️ {preview['weeks_late']} week(s) over the {free_days}-day free period — "
                 f"€{preview['late_fee']:.2f} late fee would apply.\n\n"
                 f"**Projected total: €{preview['total_due']:.2f}**"
                 if preview["weeks_late"] > 0 else
                 f"Within the {free_days}-day free period — no late fee.\n\n"
                 f"**Projected total: €{preview['total_due']:.2f}**")
            )
            st.caption("This is only a projection. The real invoice is always calculated from actual days, once the skip is returned or invoiced.")

        if st.button("Create Rental", type="primary"):
            selected_skip_id = skip_options[chosen_skip_number]["id"]
            supabase.table("rentals").insert({
                "company_id": company_id,
                "client_id": client_options[chosen_client],
                "skip_id": selected_skip_id,
                "start_date": str(delivery_date),
                "estimated_pickup_date": str(estimated_pickup) if estimated_pickup else None,
                "base_price": base_price,
                "weekly_late_rate": weekly_rate,
                "payment_status": "Pending",
                "created_at": "now()"
            }).execute()
            supabase.table("skips").update({"status": "rented"}).eq("id", selected_skip_id).execute()
            st.session_state.toast_message = f"Rental created — Skip {chosen_skip_number} for {chosen_client}."
            st.session_state.rental_form_key = form_key + 1
            st.rerun()

# ----------------------------------------------------------------
# TAB: CLIENTS
# ----------------------------------------------------------------
with tab_clients:
    st.subheader("Clients")
    clients = supabase.table("clients").select("*").eq("company_id", company_id).execute().data
    for c in clients:
        with st.container(border=True):
            st.write(f"**{c['name']}** — {c.get('phone') or 'no phone'}")

    st.divider()
    st.subheader("Add a new client")
    with st.form("add_client", clear_on_submit=True):
        name = st.text_input("Client name")
        phone = st.text_input("Phone")
        address = st.text_input("Address")
        if st.form_submit_button("Add Client"):
            if not name.strip():
                st.error("Client name can't be blank.")
            else:
                supabase.table("clients").insert({
                    "company_id": company_id,
                    "name": name,
                    "phone": phone,
                    "address": address
                }).execute()
                st.session_state.toast_message = "Client added."
                st.rerun()

# ----------------------------------------------------------------
# TAB: INVOICES
# ----------------------------------------------------------------
with tab_invoices:
    st.subheader("Generate an Invoice")

    free_days = int(company["settings"].get("free_days", 30))
    grace_days = int(company["settings"].get("grace_days", 3))

    all_rentals = supabase.table("rentals").select(
        "*, clients(name), skips(skip_number)"
    ).eq("company_id", company_id).execute().data
    invoiced_rental_ids = {
        inv["rental_id"] for inv in
        supabase.table("invoices").select("rental_id").eq("company_id", company_id).execute().data
        if inv["rental_id"]
    }
    uninvoiced = [r for r in all_rentals if r["id"] not in invoiced_rental_ids]

    if uninvoiced:
        st.warning(f"⚠️ {len(uninvoiced)} rental(s) are waiting to be invoiced.")
    else:
        st.success("✅ Every rental has been invoiced.")

    if uninvoiced:
        rental_labels = {
            f"Skip {r['skips']['skip_number']} — {r['clients']['name']} — started {fmt_date(r['start_date'])}": r
            for r in uninvoiced
        }
        chosen_label = st.selectbox("Choose a rental to invoice", options=list(rental_labels.keys()))
        rental = rental_labels[chosen_label]

        amounts = calculate_amount_due(
            rental["start_date"], rental["end_date"],
            float(rental["base_price"]), float(rental["weekly_late_rate"]), free_days, grace_days
        )
        st.write(f"Delivery date: {fmt_date(rental['start_date'])}")
        st.write(f"Days out so far: {amounts['days_out']}")
        st.write(f"Base price: €{rental['base_price']:.2f}")
        if amounts["weeks_late"] > 0:
            st.write(f"⚠️ Late fee ({amounts['weeks_late']} week(s) over {free_days}-day free period): €{amounts['late_fee']:.2f}")
        else:
            st.write(f"Within {free_days}-day free period — no late fee yet.")
        st.write(f"**Calculated total: €{amounts['total_due']:.2f}**")

        final_amount = st.number_input(
            "Final invoice amount (€) — edit here for any discount before issuing",
            min_value=0.0, value=amounts["total_due"], step=5.0
        )

        if st.button("Generate Invoice", type="primary"):
            vat_rate = 19.00
            net_amount = final_amount / (1 + vat_rate / 100)
            vat_amount = final_amount - net_amount

            invoice_number = supabase.rpc("get_next_invoice_number", {"p_company_id": company_id}).execute().data

            new_invoice = supabase.table("invoices").insert({
                "company_id": company_id,
                "invoice_number": invoice_number,
                "client_id": rental["client_id"],
                "rental_id": rental["id"],
                "issue_date": str(date.today()),
                "subtotal": round(net_amount, 2),
                "vat_rate": vat_rate,
                "vat_amount": round(vat_amount, 2),
                "total_amount": round(final_amount, 2),
                "calculated_total": round(amounts["total_due"], 2),
                "days_out": amounts["days_out"],
                "weeks_late": amounts["weeks_late"],
                "late_fee": round(amounts["late_fee"], 2),
                "status": "Pending"
            }).execute().data[0]

            supabase.table("invoice_line_items").insert({
                "invoice_id": new_invoice["id"],
                "description": f"Skip rental — {rental['skips']['skip_number']}",
                "quantity": 1,
                "unit_price": round(final_amount, 2),
                "line_total": round(final_amount, 2)
            }).execute()

            st.session_state.toast_message = f"Invoice #{invoice_number} created."
            st.rerun()

    st.divider()
    st.subheader("All Invoices")

    all_clients_for_filter = supabase.table("clients").select("id, name").eq("company_id", company_id).execute().data
    client_filter_options = {"All clients": None}
    client_filter_options.update({c["name"]: c["id"] for c in all_clients_for_filter})

    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        filter_date_from = st.date_input("From date", value=None, key="inv_filter_from", format="DD/MM/YYYY")
    with fcol2:
        filter_date_to = st.date_input("To date", value=None, key="inv_filter_to", format="DD/MM/YYYY")
    with fcol3:
        filter_client_label = st.selectbox("Client", options=list(client_filter_options.keys()), key="inv_filter_client")
    with fcol4:
        filter_status = st.selectbox("Status", ["All", "Pending", "Paid"], key="inv_filter_status")

    invoices_query = supabase.table("invoices").select(
        "*, clients(name, address, phone), rentals(start_date, end_date)"
    ).eq("company_id", company_id)
    if filter_date_from:
        invoices_query = invoices_query.gte("issue_date", str(filter_date_from))
    if filter_date_to:
        invoices_query = invoices_query.lte("issue_date", str(filter_date_to))
    if client_filter_options[filter_client_label] is not None:
        invoices_query = invoices_query.eq("client_id", client_filter_options[filter_client_label])
    if filter_status != "All":
        invoices_query = invoices_query.eq("status", filter_status)
    invoices = invoices_query.order("invoice_number", desc=True).execute().data

    filter_parts = []
    if filter_date_from or filter_date_to:
        filter_parts.append(f"Dates: {fmt_date(filter_date_from) if filter_date_from else 'any'} to {fmt_date(filter_date_to) if filter_date_to else 'any'}")
    if filter_client_label != "All clients":
        filter_parts.append(f"Client: {filter_client_label}")
    if filter_status != "All":
        filter_parts.append(f"Status: {filter_status}")
    filter_description = " | ".join(filter_parts) if filter_parts else "All invoices, no filters applied"

    st.caption(f"Showing {len(invoices)} invoice(s). {filter_description}")

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "📊 Download CSV",
            data=build_invoices_csv(invoices),
            file_name="invoices_report.csv",
            mime="text/csv",
            disabled=len(invoices) == 0
        )
    with dl_col2:
        if invoices:
            pdf_view_button("📄 Open PDF Report", generate_invoice_report_pdf(company, invoices, filter_description))
        else:
            st.button("📄 Open PDF Report", disabled=True)

    for inv in invoices:
        client = inv["clients"] or {"name": "Unknown client"}
        with st.expander(f"Invoice #{inv['invoice_number']} — {client['name']} — €{inv['total_amount']:.2f} — {inv['status']}"):
            st.markdown(f"""
**{company['name']}**
{company.get('address', '')}
VAT No: {company.get('vat_number') or 'Not set'}

**Invoice #{inv['invoice_number']}**
Date: {fmt_date(inv['issue_date'])}
Bill to: {client['name']}

---
Net amount: €{inv['subtotal']:.2f}
VAT ({inv['vat_rate']}%): €{inv['vat_amount']:.2f}
**Total: €{inv['total_amount']:.2f}**
---
            """)

            line_items = supabase.table("invoice_line_items").select("*").eq("invoice_id", inv["id"]).execute().data
            rental_info = inv.get("rentals")
            pdf_bytes = generate_invoice_pdf(company, inv, client, line_items, rental_info)
            pdf_view_button("📄 Open PDF", pdf_bytes)

            if inv["status"] != "Paid":
                if st.button("Mark Paid", key=f"inv_paid_{inv['id']}"):
                    supabase.table("invoices").update({"status": "Paid"}).eq("id", inv["id"]).execute()
                    st.session_state.toast_message = f"Invoice #{inv['invoice_number']} marked as paid."
                    st.rerun()

# ----------------------------------------------------------------
# TAB: QUOTES
# ----------------------------------------------------------------
with tab_quotes:
    st.subheader("Create a Quote")

    clients = supabase.table("clients").select("*").eq("company_id", company_id).execute().data
    skip_types = supabase.table("skip_types").select("*").eq("company_id", company_id).order("gross_price").execute().data

    if not clients or not skip_types:
        st.warning("Add at least one client and one skip size first.")
    else:
        client_options = {c["name"]: c["id"] for c in clients}
        type_options = {f"{t['size_label']} (€{t['gross_price']:.2f})": t for t in skip_types}

        chosen_client = st.selectbox("Client", options=list(client_options.keys()), key="quote_client")
        chosen_type_label = st.selectbox("Skip size", options=list(type_options.keys()), key="quote_type")
        chosen_type = type_options[chosen_type_label]

        quoted_price = st.number_input(
            "Quoted price (€) — edit for a special rate",
            min_value=0.0, value=float(chosen_type["gross_price"]), step=5.0
        )

        st.caption("These terms show on the quote so the client knows the rules up front. Pre-filled from your standard rules, but editable for this specific quote if needed.")
        qterm_col1, qterm_col2 = st.columns(2)
        with qterm_col1:
            quote_free_days = st.number_input(
                "Free days included", min_value=0,
                value=int(company["settings"].get("free_days", 30)), step=1, key="quote_free_days"
            )
        with qterm_col2:
            quote_weekly_rate = st.number_input(
                "Weekly late fee after that (€)", min_value=0.0,
                value=float(company["settings"].get("weekly_late_rate", 50.0)), step=5.0, key="quote_weekly_rate"
            )

        if st.button("Create Quote", type="primary"):
            quote_number = supabase.rpc("get_next_quote_number", {"p_company_id": company_id}).execute().data
            supabase.table("quotes").insert({
                "company_id": company_id,
                "quote_number": quote_number,
                "client_id": client_options[chosen_client],
                "skip_type_id": chosen_type["id"],
                "quoted_price": quoted_price,
                "free_days": quote_free_days,
                "weekly_late_rate": quote_weekly_rate,
                "status": "Pending"
            }).execute()
            st.session_state.toast_message = f"Quote #{quote_number} created."
            st.rerun()

    st.divider()
    st.subheader("All Quotes")

    q_client_filter_options = {"All clients": None}
    q_client_filter_options.update({c["name"]: c["id"] for c in clients})

    qfcol1, qfcol2, qfcol3 = st.columns(3)
    with qfcol1:
        q_filter_date_from = st.date_input("From date", value=None, key="quote_filter_from", format="DD/MM/YYYY")
    with qfcol2:
        q_filter_date_to = st.date_input("To date", value=None, key="quote_filter_to", format="DD/MM/YYYY")
    with qfcol3:
        q_filter_client_label = st.selectbox("Client", options=list(q_client_filter_options.keys()), key="quote_filter_client")

    quotes_query = supabase.table("quotes").select(
        "*, clients(name, address, phone), skip_types(size_label)"
    ).eq("company_id", company_id)
    if q_filter_date_from:
        quotes_query = quotes_query.gte("issue_date", str(q_filter_date_from))
    if q_filter_date_to:
        quotes_query = quotes_query.lte("issue_date", str(q_filter_date_to))
    if q_client_filter_options[q_filter_client_label] is not None:
        quotes_query = quotes_query.eq("client_id", q_client_filter_options[q_filter_client_label])
    quotes = quotes_query.order("quote_number", desc=True).execute().data

    q_filter_parts = []
    if q_filter_date_from or q_filter_date_to:
        q_filter_parts.append(f"Dates: {fmt_date(q_filter_date_from) if q_filter_date_from else 'any'} to {fmt_date(q_filter_date_to) if q_filter_date_to else 'any'}")
    if q_filter_client_label != "All clients":
        q_filter_parts.append(f"Client: {q_filter_client_label}")
    q_filter_description = " | ".join(q_filter_parts) if q_filter_parts else "All quotes, no filters applied"

    st.caption(f"Showing {len(quotes)} quote(s). {q_filter_description}")

    qdl_col1, qdl_col2 = st.columns(2)
    with qdl_col1:
        st.download_button(
            "📊 Download CSV",
            data=build_quotes_csv(quotes),
            file_name="quotes_report.csv",
            mime="text/csv",
            key="quotes_csv_dl",
            disabled=len(quotes) == 0
        )
    with qdl_col2:
        if quotes:
            pdf_view_button("📄 Open PDF Report", generate_quote_report_pdf(company, quotes, q_filter_description))
        else:
            st.button("📄 Open PDF Report", disabled=True, key="quotes_pdf_disabled")

    for q in quotes:
        client = q["clients"] or {"name": "Unknown client"}
        size_label = q["skip_types"]["size_label"] if q["skip_types"] else "?"
        with st.expander(f"Quote #{q['quote_number']} — {client['name']} — {size_label} — €{q['quoted_price']:.2f} — {q['status']}"):
            st.markdown(f"""
**{company['name']}**

**Quote #{q['quote_number']}**
Date: {fmt_date(q['issue_date'])}
For: {client['name']}
Skip size: {size_label}

**Quoted price: €{q['quoted_price']:.2f}** (VAT included)
{f"Includes up to {q['free_days']} days. After that: €{float(q['weekly_late_rate']):.2f}/week until returned." if q.get('free_days') is not None else ""}
{"Replacing this skip with a new one at any time is charged again at the full quoted price above." if q.get('free_days') is not None else ""}
            """)

            pdf_bytes = generate_quote_pdf(company, q, client, size_label)
            pdf_view_button("📄 Open PDF", pdf_bytes)

            if q["status"] == "Pending":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Mark Accepted", key=f"quote_accept_{q['id']}"):
                        supabase.table("quotes").update({"status": "Accepted"}).eq("id", q["id"]).execute()
                        st.session_state.toast_message = f"Quote #{q['quote_number']} marked as accepted."
                        st.rerun()
                with col2:
                    if st.button("Mark Expired", key=f"quote_expire_{q['id']}"):
                        supabase.table("quotes").update({"status": "Expired"}).eq("id", q["id"]).execute()
                        st.session_state.toast_message = f"Quote #{q['quote_number']} marked as expired."
                        st.rerun()

# ----------------------------------------------------------------
# TAB: CLIENT HISTORY
# ----------------------------------------------------------------
with tab_history:
    st.subheader("Client History & Statement")

    clients = supabase.table("clients").select("*").eq("company_id", company_id).execute().data
    if not clients:
        st.info("No clients yet.")
    else:
        client_options = {c["name"]: c["id"] for c in clients}
        chosen_name = st.selectbox("Select a client", options=list(client_options.keys()))
        client_id = client_options[chosen_name]

        st.markdown("### Rentals")
        rentals = supabase.table("rentals").select("*, skips(skip_number)").eq("company_id", company_id).eq("client_id", client_id).order("start_date", desc=True).execute().data
        for r in rentals:
            skip_number = r["skips"]["skip_number"] if r["skips"] else "?"
            status = "Returned" if r["end_date"] else "Active"
            st.write(f"Skip {skip_number} — {fmt_date(r['start_date'])} to {fmt_date(r['end_date']) if r['end_date'] else 'present'} — {status} — {r['payment_status']}")

        st.markdown("### Invoices & Balance")
        invoices = supabase.table("invoices").select("*").eq("company_id", company_id).eq("client_id", client_id).order("issue_date", desc=True).execute().data
        total_owed = 0.0
        for inv in invoices:
            st.write(f"Invoice #{inv['invoice_number']} — {fmt_date(inv['issue_date'])} — €{inv['total_amount']:.2f} — {inv['status']}")
            if inv["status"] != "Paid":
                total_owed += float(inv["total_amount"])

        st.divider()
        st.markdown(f"### Outstanding balance: €{total_owed:.2f}")

# ----------------------------------------------------------------
# TAB: SETTINGS
# ----------------------------------------------------------------
with tab_settings:
    st.subheader("Rental Rules")
    st.caption("These apply to every rental company-wide, unless a specific rental overrides the price manually.")

    current_settings = company.get("settings") or {}
    with st.form("company_rules"):
        free_days_input = st.number_input(
            "Free days before late fee starts",
            min_value=0, value=int(current_settings.get("free_days", 30)), step=1
        )
        grace_days_input = st.number_input(
            "Grace days after the free period (still no charge)",
            min_value=0, value=int(current_settings.get("grace_days", 3)), step=1
        )
        weekly_rate_input = st.number_input(
            "Default weekly late fee (€) — used for new skip types unless overridden below",
            min_value=0.0, value=float(current_settings.get("weekly_late_rate", 50.0)), step=5.0
        )
        if st.form_submit_button("Save Rules", type="primary"):
            new_settings = dict(current_settings)
            new_settings["free_days"] = int(free_days_input)
            new_settings["grace_days"] = int(grace_days_input)
            new_settings["weekly_late_rate"] = float(weekly_rate_input)
            supabase.table("companies").update({"settings": new_settings}).eq("id", company_id).execute()
            st.session_state.company["settings"] = new_settings
            st.session_state.toast_message = "Rules updated."
            st.rerun()

    st.divider()
    st.subheader("Skip Types & Pricing")
    st.caption("Change the label (e.g. switch from yards to cubic meters) or the starting price for each size.")

    skip_types_all = supabase.table("skip_types").select("*").eq("company_id", company_id).order("gross_price").execute().data
    for t in skip_types_all:
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_label = st.text_input("Size label", value=t["size_label"], key=f"label_{t['id']}")
            with col2:
                new_price = st.number_input("Price (€)", min_value=0.0, value=float(t["gross_price"]), step=5.0, key=f"price_{t['id']}")
            with col3:
                new_rate = st.number_input("Weekly late rate (€)", min_value=0.0, value=float(t.get("weekly_late_rate") or 0), step=5.0, key=f"rate_{t['id']}")
            if st.button("Save Changes", key=f"save_type_{t['id']}"):
                supabase.table("skip_types").update({
                    "size_label": new_label,
                    "gross_price": new_price,
                    "weekly_late_rate": new_rate
                }).eq("id", t["id"]).execute()
                st.session_state.toast_message = f"Updated {new_label}."
                st.rerun()

    st.divider()
    st.subheader("Add a New Skip Type")
    with st.form("add_skip_type", clear_on_submit=True):
        new_type_label = st.text_input("Size label (e.g. 6 m³)")
        new_type_price = st.number_input("Starting price (€)", min_value=0.0, value=160.0, step=5.0)
        new_type_rate = st.number_input("Weekly late rate (€)", min_value=0.0, value=50.0, step=5.0)
        if st.form_submit_button("Add Skip Type"):
            if not new_type_label.strip():
                st.error("Size label can't be blank.")
            else:
                supabase.table("skip_types").insert({
                    "company_id": company_id,
                    "size_label": new_type_label,
                    "gross_price": new_type_price,
                    "weekly_late_rate": new_type_rate
                }).execute()
                st.session_state.toast_message = "Skip type added."
                st.rerun()

# ----------------------------------------------------------------
# FOOTER — "Powered by CyCraftware" branding.
# This same block can be copy-pasted as-is into any future product
# (Hylates, etc.) to keep the branding consistent everywhere.
# ----------------------------------------------------------------
st.markdown(
    """
    <style>
    .cycraftware-footer {
        text-align: center;
        color: #999999;
        font-size: 12px;
        padding: 30px 0 10px 0;
        margin-top: 40px;
        border-top: 1px solid #eeeeee;
    }
    </style>
    <div class="cycraftware-footer">
        Powered by CyCraftware
    </div>
    """,
    unsafe_allow_html=True
)
