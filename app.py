import streamlit as st
from supabase import create_client
from datetime import date

# ----------------------------------------------------------------
# CONNECTION SETUP
# These values come from Streamlit's "secrets" — never hard-coded
# directly in this file, so they're safe even if this code is shared.
# ----------------------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_client()

st.set_page_config(page_title="SkipGO", page_icon="🗑️", layout="centered")

# ----------------------------------------------------------------
# LOGIN
# ----------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.company = None

def login(email, password):
    try:
        result = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = result.user

        # Look up which company this user belongs to
        profile = supabase.table("app_users").select("*").eq("id", result.user.id).single().execute()
        company_id = profile.data["company_id"]

        company = supabase.table("companies").select("*").eq("id", company_id).single().execute()
        st.session_state.company = company.data

        st.rerun()
    except Exception as e:
        st.error(f"Login failed: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.company = None
    st.rerun()

if not st.session_state.user:
    st.title("🗑️ SkipGO Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Log in", type="primary"):
        login(email, password)
    st.stop()

# ----------------------------------------------------------------
# LOGGED IN — MAIN APP
# ----------------------------------------------------------------
company = st.session_state.company
company_id = company["id"]

st.title(f"🗑️ {company['name']}")
if st.button("Log out"):
    logout()

tab_skips, tab_rentals, tab_new_rental, tab_clients = st.tabs(
    ["Skips", "Active Rentals", "New Rental", "Clients"]
)

# ----------------------------------------------------------------
# TAB: SKIPS
# ----------------------------------------------------------------
with tab_skips:
    st.subheader("All Skips")
    skips = supabase.table("skips").select("*").eq("company_id", company_id).execute().data
    if not skips:
        st.info("No skips added yet.")
    for skip in skips:
        status_emoji = "🟢" if skip["status"] == "available" else "🔴" if skip["status"] == "rented" else "🟡"
        st.write(f"{status_emoji} **Skip {skip['skip_number']}** — {skip.get('size') or 'size not set'} — {skip['status']}")

    st.divider()
    st.subheader("Add a new skip")
    with st.form("add_skip", clear_on_submit=True):
        new_number = st.text_input("Skip number")
        new_size = st.text_input("Size (e.g. 6 yard)")
        if st.form_submit_button("Add Skip"):
            supabase.table("skips").insert({
                "company_id": company_id,
                "skip_number": new_number,
                "size": new_size,
                "status": "available"
            }).execute()
            st.success("Skip added.")
            st.rerun()

# ----------------------------------------------------------------
# TAB: ACTIVE RENTALS
# ----------------------------------------------------------------
with tab_rentals:
    st.subheader("Active Rentals")
    rentals = supabase.table("rentals").select(
        "*, clients(name, phone), skips(skip_number)"
    ).eq("company_id", company_id).is_("end_date", "null").execute().data

    if not rentals:
        st.info("No active rentals.")
    for r in rentals:
        client_name = r["clients"]["name"] if r["clients"] else "Unknown client"
        skip_number = r["skips"]["skip_number"] if r["skips"] else "?"
        st.markdown(f"**Skip {skip_number}** — {client_name} — started {r['start_date']}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Mark Returned", key=f"return_{r['id']}"):
                supabase.table("rentals").update({"end_date": str(date.today())}).eq("id", r["id"]).execute()
                supabase.table("skips").update({"status": "available"}).eq("id", r["skip_id"]).execute()
                st.rerun()
        with col2:
            if r["payment_status"] != "Paid":
                if st.button("Mark Paid", key=f"paid_{r['id']}"):
                    supabase.table("rentals").update({"payment_status": "Paid"}).eq("id", r["id"]).execute()
                    st.rerun()
            else:
                st.write("✅ Paid")
        st.divider()

# ----------------------------------------------------------------
# TAB: NEW RENTAL
# ----------------------------------------------------------------
with tab_new_rental:
    st.subheader("Create a New Rental")

    clients = supabase.table("clients").select("*").eq("company_id", company_id).execute().data
    available_skips = supabase.table("skips").select("*").eq("company_id", company_id).eq("status", "available").execute().data

    if not clients:
        st.warning("Add a client first (see the Clients tab).")
    elif not available_skips:
        st.warning("No available skips — add one in the Skips tab.")
    else:
        client_options = {c["name"]: c["id"] for c in clients}
        skip_options = {s["skip_number"]: s["id"] for s in available_skips}

        with st.form("new_rental"):
            chosen_client = st.selectbox("Client", options=list(client_options.keys()))
            chosen_skip = st.selectbox("Skip", options=list(skip_options.keys()))
            base_price = st.number_input("Base price (€)", min_value=0.0, step=5.0)
            weekly_rate = st.number_input(
                "Weekly late rate (€)",
                min_value=0.0,
                value=float(company["settings"].get("weekly_late_rate", 0)),
                step=5.0
            )
            if st.form_submit_button("Create Rental", type="primary"):
                supabase.table("rentals").insert({
                    "company_id": company_id,
                    "client_id": client_options[chosen_client],
                    "skip_id": skip_options[chosen_skip],
                    "start_date": str(date.today()),
                    "base_price": base_price,
                    "weekly_late_rate": weekly_rate,
                    "payment_status": "Pending"
                }).execute()
                supabase.table("skips").update({"status": "rented"}).eq("id", skip_options[chosen_skip]).execute()
                st.success("Rental created.")
                st.rerun()

# ----------------------------------------------------------------
# TAB: CLIENTS
# ----------------------------------------------------------------
with tab_clients:
    st.subheader("Clients")
    clients = supabase.table("clients").select("*").eq("company_id", company_id).execute().data
    for c in clients:
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
                st.success("Client added.")
                st.rerun()
