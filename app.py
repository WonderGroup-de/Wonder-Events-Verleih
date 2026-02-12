import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, date, timedelta
from fpdf import FPDF
import os

# --- KONFIGURATION ---
LOGO_URL = "https://raw.githubusercontent.com/WonderGroup-de/Wonder-Events-Verleih/main/1000070172.jpg"
LOGO_FILE = "1000070172.jpg"

def init_db():
    conn = sqlite3.connect('wonder_events_final_v5.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user TEXT PRIMARY KEY, password TEXT, role TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, name TEXT, typ TEXT, beschreibung TEXT, 
                  preis_stunde REAL, preis_tag REAL, bestand INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS fixed_services 
                 (id INTEGER PRIMARY KEY, name TEXT, preis_stunde REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS discounts (code TEXT PRIMARY KEY, wert REAL, typ TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY, kunde TEXT, email TEXT, details TEXT, 
                  von TEXT, bis TEXT, umsatz REAL, rechnungs_nr TEXT, 
                  personal TEXT, status TEXT, vorfaelle TEXT, zusatz_infos TEXT)''')
    c.execute('INSERT OR IGNORE INTO users VALUES ("admin", "Wonder2026!", "Admin")')
    conn.commit()
    return conn

db = init_db()

# --- PDF GENERATOR ---
def create_pdf(b_data):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists(LOGO_FILE): pdf.image(LOGO_FILE, 10, 8, 33)
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RECHNUNG / BESTAETIGUNG', 0, 1, 'R')
    pdf.ln(20)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 10, f'Kunde: {b_data["kunde"]}', 0, 0)
    pdf.cell(0, 10, f'Nr: {b_data["rechnungs_nr"]}', 0, 1, 'R')
    pdf.ln(10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(140, 10, 'Position', 1, 0, 'L', True)
    pdf.cell(50, 10, 'Betrag', 1, 1, 'C', True)
    pdf.set_font('Arial', '', 9)
    for line in b_data["details"].split('\n'):
        if line.strip(): pdf.multi_cell(190, 8, line, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(140, 10, 'GESAMTBETRAG:', 0, 0, 'R')
    pdf.cell(50, 10, f'{b_data["umsatz"]:.2f} EUR', 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.markdown(f'<style>.stApp {{background: linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.5)), url("{LOGO_URL}"); background-size: cover;}}</style>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown('<div style="background:white; padding:2rem; border-radius:15px; text-align:center;">', unsafe_allow_html=True)
        st.image(LOGO_URL, width=150)
        u, p = st.text_input("Nutzer"), st.text_input("Passwort", type="password")
        if st.button("Anmelden", use_container_width=True):
            res = db.execute("SELECT role FROM users WHERE user=? AND password=?", (u, p)).fetchone()
            if res:
                st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res[0]
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- NAVIGATION ---
st.sidebar.image(LOGO_URL)
choice = st.sidebar.radio("Menü", ["📊 Dashboard", "📅 Verzeichnis", "📝 Neue Buchung", "📦 Lager & Pakete", "🛠️ Services & Rabatte", "👥 Team"])

# --- DASHBOARD ---
if choice == "📊 Dashboard":
    st.header("Geschäftsübersicht")
    df = pd.read_sql_query("SELECT * FROM bookings", db)
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Umsatz", f"{df['umsatz'].sum():,.2f} €")
        c2.metric("Buchungen", len(df))
        csv = df.to_csv(index=False).encode('utf-8')
        c3.download_button("📥 Finanzexport (CSV)", csv, f"Finanzen_{date.today()}.csv", "text/csv")
        st.plotly_chart(px.bar(df, x="von", y="umsatz", title="Umsatz-Verlauf"))

# --- LAGER (JETZT MIT BEARBEITEN-FUNKTION) ---
elif choice == "📦 Lager & Pakete":
    st.header("Inventar-Verwaltung")
    
    with st.expander("➕ Neues Equipment/Paket hinzufügen"):
        typ = st.radio("Typ", ["Gerät", "Paket"])
        n = st.text_input("Name")
        bes = st.text_area("Beschreibung")
        bst = st.number_input("Bestand (Stück)", min_value=1, value=1)
        c1, c2 = st.columns(2)
        ps, pt = c1.number_input("Std-Preis"), c2.number_input("Tag-Preis")
        if st.button("Speichern"):
            db.execute("INSERT INTO inventory (name, typ, beschreibung, preis_stunde, preis_tag, bestand) VALUES (?,?,?,?,?,?)", (n, typ, bes, ps, pt, bst))
            db.commit(); st.rerun()
    
    st.subheader("Aktueller Bestand & Bearbeitung")
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    
    for idx, row in inv_df.iterrows():
        with st.expander(f"📝 {row['name']} bearbeiten"):
            with st.form(f"edit_form_{row['id']}"):
                new_n = st.text_input("Name", value=row['name'])
                new_bes = st.text_area("Beschreibung", value=row['beschreibung'])
                new_bst = st.number_input("Bestand", value=row['bestand'], min_value=1)
                cc1, cc2 = st.columns(2)
                new_ps = cc1.number_input("Std-Preis", value=row['preis_stunde'])
                new_pt = cc2.number_input("Tag-Preis", value=row['preis_tag'])
                
                c_del, c_save = st.columns([1,1])
                if c_save.form_submit_button("✅ Änderungen speichern"):
                    db.execute("UPDATE inventory SET name=?, beschreibung=?, bestand=?, preis_stunde=?, preis_tag=? WHERE id=?", 
                               (new_n, new_bes, new_bst, new_ps, new_pt, row['id']))
                    db.commit(); st.rerun()
                if c_del.form_submit_button("🗑️ Löschen", type="secondary"):
                    db.execute("DELETE FROM inventory WHERE id=?", (row['id'],))
                    db.commit(); st.rerun()

# --- SERVICES & RABATTE ---
elif choice == "🛠️ Services & Rabatte":
    st.header("Zusatzleistungen & Rabatte")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Services")
        with st.form("srv"):
            sn, sp = st.text_input("Service Name"), st.number_input("Preis/Std")
            if st.form_submit_button("Hinzufügen"):
                db.execute("INSERT INTO fixed_services (name, preis_stunde) VALUES (?,?)", (sn, sp))
                db.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT name, preis_stunde FROM fixed_services", db))
    with c2:
        st.subheader("Rabattcodes")
        with st.form("dsc"):
            dc, dw = st.text_input("Code"), st.number_input("Wert")
            dt = st.selectbox("Typ", ["prozent", "euro"])
            if st.form_submit_button("Hinzufügen"):
                db.execute("INSERT INTO discounts VALUES (?,?,?)", (dc, dw, dt))
                db.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM discounts", db))

# --- NEUE BUCHUNG ---
elif choice == "📝 Neue Buchung":
    st.header("Projekt-Kalkulator")
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    srv_df = pd.read_sql_query("SELECT * FROM fixed_services", db)
    dsc_df = pd.read_sql_query("SELECT * FROM discounts", db)
    if 'cart' not in st.session_state: st.session_state.cart = []
    
    with st.container():
        st.subheader("🛒 Warenkorb")
        col1, col2 = st.columns(2)
        if not inv_df.empty:
            sel_item = col1.selectbox("Equipment/Paket", inv_df["name"].tolist())
            qty = col2.number_input("Menge", min_value=1, value=1)
            if st.button("➕ Hinzufügen"):
                st.session_state.cart.append({"typ": "item", "name": sel_item, "qty": qty})
        if not srv_df.empty:
            sel_srv = col1.selectbox("Service", srv_df["name"].tolist())
            hours = col2.number_input("Stunden/Einheiten", min_value=1, value=1)
            if st.button("🛠️ Service hinzufügen"):
                st.session_state.cart.append({"typ": "service", "name": sel_srv, "qty": hours})
        if st.session_state.cart:
            for i, c in enumerate(st.session_state.cart): st.write(f"✅ {c['qty']}x {c['name']}")
            if st.button("Warenkorb leeren"): st.session_state.cart = []; st.rerun()

    with st.form("booking_final", clear_on_submit=True):
        k_name, k_mail = st.columns(2)[0].text_input("Kunde"), st.columns(2)[1].text_input("E-Mail")
        v_dt, v_tm = st.columns(2)[0].date_input("Start"), st.columns(2)[1].time_input("Startzeit")
        b_dt, b_tm = st.columns(2)[0].date_input("Ende"), st.columns(2)[1].time_input("Endzeit")
        rabatt_code = st.text_input("Rabatt-Code")
        infos = st.text_area("Hinweise")
        if st.form_submit_button("🚀 JETZT BUCHEN"):
            start, ende = datetime.combine(v_dt, v_tm), datetime.combine(b_dt, b_tm)
            std_total = max(1, (ende - start).total_seconds() / 3600)
            tg_total = max(1, (ende - start).days)
            umsatz, lines = 0, []
            for c in st.session_state.cart:
                if c["typ"] == "item":
                    row = inv_df[inv_df["name"] == c["name"]].iloc[0]
                    p = row["preis_stunde"] * c["qty"] * int(std_total) if std_total < 24 else row["preis_tag"] * c["qty"] * tg_total
                    umsatz += p; lines.append(f"{c['qty']}x {c['name']}: {p:.2f} EUR")
                else:
                    row = srv_df[srv_df["name"] == c["name"]].iloc[0]
                    p = row["preis_stunde"] * c["qty"]; umsatz += p; lines.append(f"Service: {c['name']} ({c['qty']} Std): {p:.2f} EUR")
            if rabatt_code in dsc_df["code"].values:
                r_row = dsc_df[dsc_df["code"] == rabatt_code].iloc[0]
                abzug = (umsatz * (r_row["wert"]/100)) if r_row["typ"] == "prozent" else r_row["wert"]
                umsatz -= abzug; lines.append(f"Rabatt ({rabatt_code}): -{abzug:.2f} EUR")
            r_nr = f"WE-{date.today().strftime('%y%m%d')}-{k_name[:3].upper()}"
            db.execute("INSERT INTO bookings (kunde, email, details, von, bis, umsatz, rechnungs_nr, status, zusatz_infos) VALUES (?,?,?,?,?,?,?,?,?)",
                       (k_name, k_mail, "\n".join(lines), str(start), str(ende), umsatz, r_nr, "Offen", infos))
            db.commit(); st.session_state.cart = []; st.success(f"Gebucht! Summe: {umsatz:.2f}€"); st.balloons()

# --- VERZEICHNIS & TEAM ---
elif choice == "📅 Verzeichnis":
    df = pd.read_sql_query("SELECT * FROM bookings", db)
    if not df.empty:
        st.dataframe(df[['rechnungs_nr', 'kunde', 'von', 'umsatz']], use_container_width=True)
        target = st.selectbox("Aktion:", ["-- Wählen --"] + df['rechnungs_nr'].tolist())
        if target != "-- Wählen --":
            b = df[df['rechnungs_nr'] == target].iloc[0]
            st.download_button("📄 PDF Rechnung", data=create_pdf(b), file_name=f"Rechnung_{target}.pdf")
            if st.button("✅ Abschließen"):
                db.execute("UPDATE bookings SET status='Abgeschlossen' WHERE rechnungs_nr=?", (target,))
                db.commit(); st.rerun()

elif choice == "👥 Team":
    st.header("Personal")
    with st.form("t"):
        nu, np, nr = st.text_input("Name"), st.text_input("PW"), st.selectbox("Rolle", ["User", "Admin"])
        if st.form_submit_button("Anlegen"):
            db.execute("INSERT INTO users VALUES (?,?,?)", (nu, np, nr)); db.commit(); st.rerun()
    st.table(pd.read_sql_query("SELECT user, role FROM users", db))
