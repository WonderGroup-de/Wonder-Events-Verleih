import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
from fpdf import FPDF
import os

# --- BRANDING ---
LOGO_URL = "https://raw.githubusercontent.com/WonderGroup-de/Wonder-Events-Verleih/main/1000070172.jpg"

def init_db():
    conn = sqlite3.connect('wonder_events_final_v6.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user TEXT PRIMARY KEY, password TEXT, role TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, name TEXT, gesamt INTEGER, preis REAL, einheit TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY, kunde TEXT, email TEXT, details TEXT, 
                  von TEXT, bis TEXT, umsatz REAL, rechnungs_nr TEXT, 
                  personal TEXT, status TEXT, zusatz_infos TEXT)''')
    c.execute('INSERT OR IGNORE INTO users VALUES ("admin", "Wonder2026!", "Admin")')
    conn.commit()
    return conn

db = init_db()

# --- PDF GENERATOR ---
def create_pdf(b_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'WONDER-EVENTS RECHNUNG', 0, 1, 'C')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, 'Wonder-Group Malsch', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'Rechnungsnummer: {b_data["rechnungs_nr"]}', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f'Kunde: {b_data["kunde"]}', 0, 1)
    pdf.cell(0, 10, f'Zeitraum: {b_data["von"]} bis {b_data["bis"]}', 0, 1)
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Positionen:', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 7, b_data["details"])
    
    if b_data["zusatz_infos"]:
        pdf.ln(5)
        pdf.set_font('Arial', 'I', 10)
        pdf.multi_cell(0, 6, f'Hinweise: {b_data["zusatz_infos"]}')
    
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f'GESAMTBETRAG: {b_data["umsatz"]:.2f} EUR', 0, 1)
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.image(LOGO_URL, width=200)
    u = st.text_input("Nutzer")
    p = st.text_input("Passwort", type="password")
    if st.button("Einloggen"):
        res = db.execute("SELECT role FROM users WHERE user=? AND password=?", (u, p)).fetchone()
        if res:
            st.session_state.logged_in, st.session_state.role, st.session_state.user = True, res[0], u
            st.rerun()
    st.stop()

# --- NAVIGATION ---
choice = st.sidebar.radio("Menü", ["📅 Verzeichnis & Bearbeiten", "📝 Neue Buchung", "📦 Inventar", "👥 Team"])

# --- NEUE BUCHUNG ---
if choice == "📝 Neue Buchung":
    st.header("Neue Buchung")
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    with st.form("booking_form", clear_on_submit=True):
        k_name = st.text_input("Kunde")
        k_mail = st.text_input("E-Mail")
        item = st.selectbox("Equipment", inv_df["name"].tolist() if not inv_df.empty else ["Leer"])
        v_dt = st.date_input("Von", date.today())
        b_dt = st.date_input("Bis", date.today() + timedelta(days=1))
        # NEU: Zusatzinfos direkt beim Erstellen
        infos = st.text_area("Spezialaufträge / Zusatz-Infos", placeholder="Z.B. Anfahrt über Hinterhof, Ansprechpartner vor Ort...")
        
        if st.form_submit_button("Speichern"):
            r_nr = f"WE-{date.today().strftime('%y%m%d')}-{k_name[:3].upper()}"
            db.execute("INSERT INTO bookings (kunde, email, details, von, bis, umsatz, rechnungs_nr, status, zusatz_infos) VALUES (?,?,?,?,?,?,?,?,?)",
                       (k_name, k_mail, item, str(v_dt), str(b_dt), 0.0, r_nr, "Offen", infos))
            db.commit()
            st.success("Erfolgreich gespeichert!")

# --- VERZEICHNIS & NACHTRÄGLICH BEARBEITEN ---
elif choice == "📅 Verzeichnis & Bearbeiten":
    st.header("Buchungsverzeichnis")
    df = pd.read_sql_query("SELECT * FROM bookings", db)
    st.dataframe(df[['rechnungs_nr', 'kunde', 'von', 'bis']], use_container_width=True)
    
    st.divider()
    st.subheader("Details & Änderungen")
    target = st.selectbox("Buchung auswählen:", ["-- Bitte wählen --"] + df['rechnungs_nr'].tolist())
    
    if target != "-- Bitte wählen --":
        b_data = df[df['rechnungs_nr'] == target].iloc[0]
        
        # Bearbeitungs-Modus
        with st.expander("📝 Infos einsehen / Spezialaufträge bearbeiten", expanded=True):
            new_infos = st.text_area("Aktuelle Zusatz-Infos:", value=b_data['zusatz_infos'] if b_data['zusatz_infos'] else "")
            new_status = st.selectbox("Status:", ["Offen", "In Arbeit", "Abgeschlossen"], index=["Offen", "In Arbeit", "Abgeschlossen"].index(b_data['status']))
            
            if st.button("Änderungen speichern"):
                db.execute("UPDATE bookings SET zusatz_infos=?, status=? WHERE rechnungs_nr=?", (new_infos, new_status, target))
                db.commit()
                st.success("Infos wurden aktualisiert!")
                st.rerun()
        
        # PDF Button
        pdf_bytes = create_pdf(b_data)
        st.download_button("📄 PDF Rechnung laden", data=pdf_bytes, file_name=f"Rechnung_{target}.pdf", mime="application/pdf")

elif choice == "📦 Inventar":
    st.header("Lager")
    with st.expander("Neu"):
        n = st.text_input("Name")
        if st.button("Speichern"):
            db.execute("INSERT INTO inventory (name, gesamt, preis, einheit) VALUES (?,1,0,'Tag')", (n,))
            db.commit()
            st.rerun()
    st.table(pd.read_sql_query("SELECT name FROM inventory", db))

