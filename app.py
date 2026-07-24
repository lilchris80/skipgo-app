import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import streamlit.components.v1 as components

# --- Database Setup & Helper Functions ---
def init_db():
    conn = sqlite3.connect('skipgo.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, address TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS skips (id INTEGER PRIMARY KEY AUTOINCREMENT, skip_number TEXT UNIQUE NOT NULL, size TEXT DEFAULT 'Medium Skip (6 Cubic Meters) - €160', status TEXT DEFAULT 'Available')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS rentals (id INTEGER PRIMARY KEY AUTOINCREMENT, client_name TEXT, skip_number TEXT, start_date TEXT, expected_pickup_date TEXT, actual_pickup_date TEXT, monthly_rate REAL DEFAULT 160.0, weekly_rate REAL DEFAULT 50.0, discount REAL DEFAULT 0.0, total_cost REAL DEFAULT 0.0, payment_status TEXT DEFAULT 'Pending Payment', status TEXT DEFAULT 'Active')''')
    conn.commit()
    conn.close()

init_db()

def run_query(query, params=()):
    conn = sqlite3.connect('skipgo.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def fetch_data(query, params=()):
    conn = sqlite3.connect('skipgo.db')
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# --- Date Formatting Helper (DD/MM/YYYY) ---
def fmt_date(date_str):
    if not date_str: return ""
    try:
        if isinstance(date_str, str):
            return datetime.strptime(date_str.split(" ")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
        elif isinstance(date_str, (date, datetime)):
            return date_str.strftime("%d/%m/%Y")
    except Exception:
        return date_str
    return date_str

# --- Cost Calculation (>30 Days = Weekly Charge) ---
def calculate_cost(start_date, end_date, monthly_rate, weekly_rate, discount):
    delta = (end_date - start_date).days
    if delta <= 0: delta = 1
    
    extra_weeks = 0
    if delta <= 30:
        total_cost = monthly_rate
    else:
        extra_days = delta - 30
        extra_weeks = (extra_days + 6) // 7
        total_cost = monthly_rate + (extra_weeks * weekly_rate)
        
    final_price = total_cost - discount
    return max(0.0, final_price), delta, extra_weeks

# --- Clean Document Generator (Quotes & Invoices) ---
def render_document(doc_type, client, skip_num, skip_size, start, end, m_rate, w_rate, discount, final_price, total_days, extra_weeks):
    st.session_state['showing_doc'] = True
    
    if st.button("❌ Close Document Preview / Go Back"):
        st.session_state['showing_doc'] = False
        st.rerun()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; color: #333; background: #fff; }}
            .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
            .title {{ font-size: 32px; font-weight: bold; }}
            .doc-type {{ font-size: 24px; color: #555; margin-top: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #f8f9fa; }}
            .totals {{ text-align: right; font-size: 18px; }}
            .totals td {{ border: none; }}
            .grand-total {{ font-weight: bold; font-size: 24px; color: #000; border-top: 2px solid #000 !important; }}
            .print-btn {{ display: block; width: 100%; max-width: 300px; margin: 30px auto; padding: 15px; background: #28a745; color: white; text-align: center; text-decoration: none; font-size: 18px; font-weight: bold; border-radius: 8px; cursor: pointer; border: none; }}
            .print-btn:hover {{ background: #218838; }}
            @media print {{ .print-btn {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">🚛 skipGO Services</div>
            <div class="doc-type">{doc_type}</div>
            <p>Date Generated: {date.today().strftime('%d/%m/%Y')}</p>
        </div>
        
        <table>
            <tr><th>Client Name:</th><td>{client}</td><th>Skip Number & Size:</th><td>{skip_num} ({skip_size})</td></tr>
            <tr><th>Start Date:</th><td>{fmt_date(start)}</td><th>Billing / Target Date:</th><td>{fmt_date(end)}</td></tr>
            <tr><th>Billed Duration:</th><td colspan="3">{total_days} Days Total</td></tr>
        </table>
        
        <table>
            <tr>
                <th>Description</th>
                <th>Qty / Details</th>
                <th>Rate</th>
                <th>Total</th>
            </tr>
            <tr>
                <td>Base Skip Rental (First 30 Days)</td>
                <td>1</td>
                <td>€{m_rate:.2f}</td>
                <td>€{m_rate:.2f}</td>
            </tr>
            <tr>
                <td>Extra Weekly Charge (>30 Days)</td>
                <td>{extra_weeks} Weeks</td>
                <td>€{w_rate:.2f} / wk</td>
                <td>€{(extra_weeks * w_rate):.2f}</td>
            </tr>
            <tr>
                <td>Discount Applied</td>
                <td>-</td>
                <td>-</td>
                <td>- €{discount:.2f}</td>
            </tr>
        </table>
        
        <table class="totals">
            <tr>
                <td width="70%"></td>
                <td><strong>Final Total:</strong></td>
                <td class="grand-total">€{final_price:.2f}</td>
            </tr>
        </table>
        
        <button class="print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
    </body>
    </html>
    """
    components.html(html, height=650, scrolling=True)


# --- Main App Interface ---
st.set_page_config(page_title="skipGO Dashboard", layout="wide")
st.title("🚛 skipGO - Rental & Invoicing Manager")

if 'showing_doc' not in st.session_state:
    st.session_state['showing_doc'] = False

# --- LIVE REPORT SUMMARY ---
try:
    total_skips = fetch_data("SELECT COUNT(*) FROM skips WHERE status != 'Scrapped' AND status != 'Sold'")['COUNT(*)'][0]
    rented_skips = fetch_data("SELECT COUNT(*) FROM skips WHERE status='Rented'")['COUNT(*)'][0]
    avail_skips = fetch_data("SELECT COUNT(*) FROM skips WHERE status='Available'")['COUNT(*)'][0]
    
    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("📦 Total Active Skips", total_skips)
    col_r2.metric("🔴 Skips Rented Out", rented_skips)
    col_r3.metric("🟢 Skips Available", avail_skips)
except Exception:
    pass 
st.divider()

# --- TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔴 Active Rentals", "💰 Pending Payments", "📜 History Log", "➕ New Rental", "📁 Inventory & Clients"])

# --- TAB 1: ACTIVE RENTALS ---
with tab1:
    st.header("Active Rentals")
    active_rentals = fetch_data("SELECT * FROM rentals WHERE status='Active'")
    
    if not active_rentals.empty:
        for index, row in active_rentals.iterrows():
            r_id = row['id']
            s_date_obj = datetime.strptime(row['start_date'], "%Y-%m-%d").date()
            e_date_obj = datetime.strptime(row['expected_pickup_date'], "%Y-%m-%d").date()
            
            skip_info = fetch_data("SELECT size FROM skips WHERE skip_number=?", (row['skip_number'],))
            skip_sz = skip_info.iloc[0]['size'] if not skip_info.empty else "Standard"
            
            with st.expander(f"🚛 Skip: {row['skip_number']} ({skip_sz}) | Client: {row['client_name']} | Started: {fmt_date(row['start_date'])}"):
                
                st.markdown("### 📝 Edit Details & Pricing")
                col_d1, col_d2, col_d3 = st.columns(3)
                with col_d1:
                    new_start = st.date_input("Start Date", s_date_obj, key=f"s_{r_id}")
                with col_d2:
                    new_expected = st.date_input("Expected Pickup", e_date_obj, key=f"e_{r_id}")
                with col_d3:
                    actual_pickup = st.date_input("Billing Date / Today's Calculation", date.today(), key=f"act_{r_id}")
                    
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    new_m_rate = st.number_input("Flat Rate €", value=float(row['monthly_rate']), key=f"m_{r_id}")
                with col_r2:
                    new_w_rate = st.number_input("Weekly Rate €", value=float(row['weekly_rate']), key=f"w_{r_id}")
                with col_r3:
                    new_disc = st.number_input("Discount €", value=float(row['discount']), key=f"d_{r_id}")
                
                # --- LIVE CALCULATIONS ---
                est_price, est_days, est_weeks = calculate_cost(new_start, new_expected, new_m_rate, new_w_rate, new_disc)
                final_price, total_days, final_weeks = calculate_cost(new_start, actual_pickup, new_m_rate, new_w_rate, new_disc)
                
                st.markdown("### 📊 Calculations")
                st.info(f"**Expected Duration:** {est_days} Days (Extra Weeks: {est_weeks}) ➔ **Estimated Cost:** €{est_price:.2f}")
                st.success(f"**Billing Date Total (Calculated Up To Selected Date):** {total_days} Days (Extra Weeks: {final_weeks}) ➔ **Total:** €{final_price:.2f}")

                st.divider()
                
                st.markdown("### ⚙️ Actions")
                col_act1, col_act2 = st.columns(2)
                
                with col_act1:
                    pay_status = st.selectbox("Payment Status on Finish", ["Pending Payment", "Paid"], key=f"pay_{r_id}")
                    
                    if st.button("💾 Save Changes", key=f"save_{r_id}", use_container_width=True):
                        run_query("UPDATE rentals SET start_date=?, expected_pickup_date=?, monthly_rate=?, weekly_rate=?, discount=? WHERE id=?", 
                                  (str(new_start), str(new_expected), new_m_rate, new_w_rate, new_disc, r_id))
                        st.success("Changes saved!")
                        st.rerun()
                        
                    if st.button("✅ Confirm Pickup & Finish Job", key=f"finish_{r_id}", type="primary", use_container_width=True):
                        run_query("""
                            UPDATE rentals 
                            SET status='Completed', actual_pickup_date=?, monthly_rate=?, weekly_rate=?, discount=?, total_cost=?, payment_status=? 
                            WHERE id=?
                        """, (str(actual_pickup), new_m_rate, new_w_rate, new_disc, final_price, pay_status, r_id))
                        run_query("UPDATE skips SET status='Available' WHERE skip_number=?", (row['skip_number'],))
                        st.rerun()

                with col_act2:
                    if st.button("📄 Print Quote", key=f"q_{r_id}", use_container_width=True):
                        render_document("OFFICIAL QUOTE", row['client_name'], row['skip_number'], skip_sz, new_start, new_expected, new_m_rate, new_w_rate, new_disc, est_price, est_days, est_weeks)
                        
                    # This guarantees the live screen calculations (including 30+ day weekly charges) go onto the printed invoice instantly
                    if st.button("🧾 Print Invoice", key=f"inv_{r_id}", use_container_width=True):
                        render_document("TAX INVOICE", row['client_name'], row['skip_number'], skip_sz, new_start, actual_pickup, new_m_rate, new_w_rate, new_disc, final_price, total_days, final_weeks)
                    
                    st.write("---")
                    if st.button("🗑️ Delete this Record (Mistake)", key=f"del_{r_id}", use_container_width=True):
                        run_query("DELETE FROM rentals WHERE id=?", (r_id,))
                        run_query("UPDATE skips SET status='Available' WHERE skip_number=?", (row['skip_number'],))
                        st.rerun()
    else:
        st.info("No active rentals right now. Go to the 'New Rental' tab to start one!")

# --- TAB 2: PENDING PAYMENTS (Visible Directly Outside with Print Option) ---
with tab2:
    st.header("💰 Pending Payments")
    
    pending_jobs = fetch_data("SELECT * FROM rentals WHERE status='Completed' AND payment_status='Pending Payment'")
    
    if not pending_jobs.empty:
        st.warning(f"⚠️ You have {len(pending_jobs)} completed job(s) waiting to be paid!")
        st.write("You can print an invoice at any time or mark them as paid to clear them:")
        st.divider()
        
        for idx, p_row in pending_jobs.iterrows():
            p_id = p_row['id']
            p_start = datetime.strptime(p_row['start_date'], "%Y-%m-%d").date()
            p_actual = datetime.strptime(p_row['actual_pickup_date'], "%Y-%m-%d").date()
            
            skip_info = fetch_data("SELECT size FROM skips WHERE skip_number=?", (p_row['skip_number'],))
            skip_sz = skip_info.iloc[0]['size'] if not skip_info.empty else "Standard"
            
            # Recalculate cost accurately for the pending invoice
            p_price, p_days, p_weeks = calculate_cost(p_start, p_actual, float(p_row['monthly_rate']), float(p_row['weekly_rate']), float(p_row['discount']))
            
            col_p1, col_p2, col_p3 = st.columns([3, 2, 2])
            with col_p1:
                st.write(f"**Job ID:** {p_id} | **Client:** {p_row['client_name']} | **Skip:** {p_row['skip_number']} ({skip_sz})")
                st.write(f"**Owed:** €{p_price:.2f} | **Picked Up:** {fmt_date(p_row['actual_pickup_date'])}")
            with col_p2:
                if st.button("🧾 Print Invoice", key=f"print_pending_{p_id}"):
                    render_document("TAX INVOICE", p_row['client_name'], p_row['skip_number'], skip_sz, p_start, p_actual, float(p_row['monthly_rate']), float(p_row['weekly_rate']), float(p_row['discount']), p_price, p_days, p_weeks)
            with col_p3:
                if st.button("✅ Mark as Paid", key=f"mark_paid_{p_id}"):
                    run_query("UPDATE rentals SET payment_status='Paid' WHERE id=?", (p_id,))
                    st.success(f"Job {p_id} marked as Paid!")
                    st.rerun()
            st.write("---")
    else:
        st.success("🎉 All caught up! There are zero pending payments right now.")

# --- TAB 3: HISTORY LOG (With Print Capability) ---
with tab3:
    st.header("📜 Full Completed Jobs & Paid History")
    st.write("You can also reprint invoices for any completed job from history if needed.")
    
    history = fetch_data("SELECT * FROM rentals WHERE status='Completed' ORDER BY id DESC")
    if not history.empty:
        for idx, h_row in history.iterrows():
            h_id = h_row['id']
            h_start = datetime.strptime(h_row['start_date'], "%Y-%m-%d").date()
            h_actual = datetime.strptime(h_row['actual_pickup_date'], "%Y-%m-%d").date()
            
            skip_info = fetch_data("SELECT size FROM skips WHERE skip_number=?", (h_row['skip_number'],))
            skip_sz = skip_info.iloc[0]['size'] if not skip_info.empty else "Standard"
            
            h_price, h_days, h_weeks = calculate_cost(h_start, h_actual, float(h_row['monthly_rate']), float(h_row['weekly_rate']), float(h_row['discount']))
            
            with st.expander(f"Job #{h_id} | Client: {h_row['client_name']} | Skip: {h_row['skip_number']} | Status: {h_row['payment_status']} | Total: €{h_price:.2f}"):
                st.write(f"**Start Date:** {fmt_date(h_row['start_date'])} | **Pickup Date:** {fmt_date(h_row['actual_pickup_date'])}")
                st.write(f"**Total Days:** {h_days} | **Payment Status:** {h_row['payment_status']}")
                
                if st.button("🧾 Print Invoice for this Completed Job", key=f"print_history_{h_id}"):
                    render_document("TAX INVOICE", h_row['client_name'], h_row['skip_number'], skip_sz, h_start, h_actual, float(h_row['monthly_rate']), float(h_row['weekly_rate']), float(h_row['discount']), h_price, h_days, h_weeks)
    else:
        st.write("No completed jobs in history yet.")

# --- TAB 4: NEW RENTAL (Quote) ---
with tab4:
    st.header("Rent out a Skip & Generate Quote")
    
    available_skips = fetch_data("SELECT skip_number, size FROM skips WHERE status='Available'")
    clients_df = fetch_data("SELECT name FROM clients")
    
    if available_skips.empty:
        st.warning("⚠️ No skips available! All skips are either rented, scrapped, or sold.")
    elif clients_df.empty:
        st.warning("⚠️ No clients found! Please go to the 'Inventory & Clients' tab to add your clients first.")
    else:
        client_name = st.selectbox("Search & Select Client", clients_df['name'])
        
        skip_options = [f"{row['skip_number']} ({row['size']})" for idx, row in available_skips.iterrows()]
        selected_skip_str = st.selectbox("Assign Skip Number", skip_options)
        skip_num = selected_skip_str.split(" ")[0]
        
        default_m = 160.0
        if "140" in selected_skip_str: default_m = 140.0
        elif "160" in selected_skip_str: default_m = 160.0
        elif "190" in selected_skip_str: default_m = 190.0

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date (DD/MM/YYYY)", date.today())
        with col2:
            expected_date = st.date_input("Expected Pickup Date (DD/MM/YYYY)", date.today())
        
        st.write("**Setup Pricing (Auto-set by skip size, or customize):**")
        col3, col4, col5 = st.columns(3)
        with col3:
            monthly_rate = st.number_input("Flat Rate (First 30 Days) - €", value=default_m)
        with col4:
            weekly_rate = st.number_input("Extra Weekly Rate (After 30 Days) - €", value=50.0)
        with col5:
            discount = st.number_input("Discount - €", value=0.0)
            
        est_price, est_days, est_weeks = calculate_cost(start_date, expected_date, monthly_rate, weekly_rate, discount)
        st.info(f"**Estimated Days:** {est_days} days (Extra Weeks: {est_weeks}) | **Estimated Total:** €{est_price:.2f}")
            
        col_q, col_s = st.columns(2)
        with col_q:
            if st.button("📝 Open & Print Quote", use_container_width=True):
                skip_sz_val = selected_skip_str.split("(")[1].replace(")", "")
                render_document("OFFICIAL QUOTE", client_name, skip_num, skip_sz_val, start_date, expected_date, monthly_rate, weekly_rate, discount, est_price, est_days, est_weeks)
                
        with col_s:
            if st.button("🚀 Start Rental Job", use_container_width=True):
                run_query("""
                    INSERT INTO rentals (client_name, skip_number, start_date, expected_pickup_date, monthly_rate, weekly_rate, discount, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')
                """, (client_name, skip_num, str(start_date), str(expected_date), monthly_rate, weekly_rate, discount))
                
                run_query("UPDATE skips SET status='Rented' WHERE skip_number=?", (skip_num,))
                st.success(f"Skip {skip_num} rented to {client_name}!")
                st.rerun()

# --- TAB 5: INVENTORY & CLIENTS ---
with tab5:
    col_client, col_skip = st.columns(2)
    
    with col_client:
        st.header("Manage Clients")
        with st.form("add_client_form", clear_on_submit=True):
            c_name = st.text_input("Client Name / Company *")
            c_phone = st.text_input("Phone Number")
            c_address = st.text_input("Address")
            if st.form_submit_button("Add New Client"):
                if c_name:
                    run_query("INSERT INTO clients (name, phone, address) VALUES (?, ?, ?)", (c_name, c_phone, c_address))
                    st.success(f"Client '{c_name}' saved!")
                    st.rerun()
                else:
                    st.error("Client Name is required.")
        
        saved_clients = fetch_data("SELECT * FROM clients")
        if not saved_clients.empty:
            st.dataframe(saved_clients[['id', 'name', 'phone']])
            
    with col_skip:
        st.header("Manage Skips")
        with st.form("add_skip_form", clear_on_submit=True):
            new_skip = st.text_input("New Skip Number / ID")
            skip_size_choice = st.selectbox("Skip Size / Capacity", [
                "Small Skip (~4 Cubic Meters) - €140",
                "Medium Skip (~6 Cubic Meters) - €160",
                "Large Skip (~8 Cubic Meters) - €190"
            ])
            
            if st.form_submit_button("Add Skip"):
                try:
                    run_query("INSERT INTO skips (skip_number, size) VALUES (?, ?)", (new_skip, skip_size_choice))
                    st.success(f"Skip {new_skip} added to inventory!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("This skip number already exists.")
        
        st.divider()
        st.subheader("Update Skip Status (Scrap / Sell)")
        skips_df = fetch_data("SELECT * FROM skips")
        if not skips_df.empty:
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                skip_to_update = st.selectbox("Select Skip", skips_df['skip_number'])
            with col_sel2:
                new_status = st.selectbox("Change Status To:", ["Available", "Rented", "Scrapped", "Sold"])
            
            if st.button("Update Status"):
                run_query("UPDATE skips SET status=? WHERE skip_number=?", (new_status, skip_to_update))
                st.success(f"{skip_to_update} is now marked as {new_status}!")
                st.rerun()
                
            st.write("**Current Inventory List:**")
            
            def style_status(val):
                if val == 'Rented': return 'background-color: #ffcccc; color: black;'
                if val == 'Scrapped' or val == 'Sold': return 'background-color: #d3d3d3; color: black;'
                return 'background-color: #ccffcc; color: black;'
            
            skips_df_styled = skips_df.style.map(style_status, subset=['status'])
            st.dataframe(skips_df_styled, use_container_width=True)