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
    conn = sqlite3.connect('wonder_events_ultimate.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user TEXT PRIMARY KEY, password TEXT, role TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, name TEXT, gesamt INTEGER, preis REAL, einheit TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY, kunde TEXT, email TEXT, details TEXT, 
                  von TEXT, bis TEXT, umsatz REAL, rechnungs_nr TEXT, 
                  personal TEXT, status TEXT, vorfaelle TEXT, zusatz_infos TEXT)''')
    c.execute('INSERT OR IGNORE INTO users VALUES ("admin", "Wonder2026!", "Admin")')
    conn.commit()
    return conn

db = init_db()

# --- HELPER: LIVE STATUS ---
def get_live_status(von_str, bis_str, status):
    if status == "Abgeschlossen": return "✅ Zurückerhalten"
    try:
        now = datetime.now()
        von = datetime.strptime(von_str, '%Y-%m-%d %H:%M:%S')
        bis = datetime.strptime(bis_str, '%Y-%m-%d %H:%M:%S')
        if von <= now <= bis: return "🔴 AUẞER HAUS"
        if now > bis: return "⚠️ ÜBERFÄLLIG"
        return "📅 Geplant"
    except: return status

# --- PDF GENERATOR ---
def create_pdf(b_data):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists(LOGO_FILE): pdf.image(LOGO_FILE, 10, 8, 33)
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RECHNUNG / BESTÄTIGUNG', 0, 1, 'R')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, 'Wonder-Events | Wonder-Group Malsch', 0, 1, 'R')
    pdf.ln(20)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 10, f'Kunde: {b_data["kunde"]}', 0, 0)
    pdf.cell(0, 10, f'Nr: {b_data["rechnungs_nr"]}', 0, 1, 'R')
    pdf.ln(10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(140, 10, 'Leistung', 1, 0, 'L', True)
    pdf.cell(50, 10, 'Betrag', 1, 1, 'C', True)
    pdf.set_font('Arial', '', 11)
    pdf.cell(140, 10, b_data["details"], 1)
    pdf.cell(50, 10, f'{b_data["umsatz"]:.2f} EUR', 1, 1, 'R')
    if b_data["zusatz_infos"]:
        pdf.ln(5)
        pdf.set_font('Arial', 'I', 10)
        pdf.multi_cell(0, 6, f'Hinweise: {b_data["zusatz_infos"]}')
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'GESAMTBETRAG: {b_data["umsatz"]:.2f} EUR', 0, 1, 'R')
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 10, f'Zahlbar bis zur Rückgabe am {b_data["bis"]}', 0, 1, 'C')
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
choice = st.sidebar.radio("Menü", ["📊 Dashboard", "📅 Verzeichnis & Rückgabe", "📝 Neue Buchung", "📦 Lager & Preise", "👥 Team"])

# --- DASHBOARD ---
if choice == "📊 Dashboard":
    st.header("Geschäftsübersicht")
    df = pd.read_sql_query("SELECT umsatz, von FROM bookings", db)
    if not df.empty:
        c1, c2 = st.columns(2)
        c1.metric("Gesamtumsatz", f"{df['umsatz'].sum():,.2f} €")
        c2.metric("Anzahl Buchungen", len(df))
        fig = px.bar(df, x="von", y="umsatz", title="Umsatz nach Datum")
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("Noch keine Daten.")

# --- LAGER ---
elif choice == "📦 Lager & Preise":
    st.header("Lagerverwaltung")
    with st.expander("➕ Neues Gerät anlegen"):
        n = st.text_input("Name")
        pr = st.number_input("Preis (€)", min_value=0.0)
        ein = st.selectbox("Einheit", ["pro Tag", "pro Stunde"])
        if st.button("Hinzufügen"):
            db.execute("INSERT INTO inventory (name, gesamt, preis, einheit) VALUES (?,1,?,?)", (n, pr, ein))
            db.commit()
            st.rerun()
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    for idx, row in inv_df.iterrows():
        with st.expander(f"⚙️ {row['name']} ({row['preis']}€ {row['einheit']})"):
            c1, c2 = st.columns(2)
            new_p = c1.number_input("Preis ändern", value=float(row['preis']), key=f"p_{row['id']}")
            new_e = c2.selectbox("Einheit ändern", ["pro Tag", "pro Stunde"], index=0 if row['einheit'] == "pro Tag" else 1, key=f"e_{row['id']}")
            if st.button("Update", key=f"upd_{row['id']}"):
                db.execute("UPDATE inventory SET preis=?, einheit=? WHERE id=?", (new_p, new_e, row['id']))
                db.commit()
                st.rerun()

# --- NEUE BUCHUNG ---
elif choice == "📝 Neue Buchung":
    st.header("Neue Projekt-Buchung")
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    users_df = pd.read_sql_query("SELECT user FROM users", db)
    with st.form("booking_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        k_name, k_mail = c1.text_input("Kunde"), c2.text_input("E-Mail")
        item = st.selectbox("Equipment", inv_df["name"].tolist() if not inv_df.empty else ["Leer"])
        menge = st.number_input("Menge", min_value=1)
        v_dt = st.date_input("Start", date.today()); v_tm = st.time_input("Zeit Start", datetime.now().time())
        b_dt = st.date_input("Ende", date.today() + timedelta(days=1)); b_tm = st.time_input("Zeit Ende", datetime.now().time())
        pers = st.multiselect("Personal zuweisen", users_df["user"].tolist())
        s_name = st.text_input("Zusatz-Service (z.B. Lieferung)"); s_preis = st.number_input("Service-Preis (€)", min_value=0.0)
        infos = st.text_area("Spezialauftrag / Hinweise")
        if st.form_submit_button("🚀 BUCHUNG SPEICHERN"):
            row = inv_df[inv_df["name"] == item].iloc[0]
            start, ende = datetime.combine(v_dt, v_tm), datetime.combine(b_dt, b_tm)
            diff = ende - start
            faktor = max(1, diff.days if row["einheit"] == "pro Tag" else int(diff.total_seconds() / 3600))
            umsatz = (row["preis"] * menge * faktor) + s_preis
            details = f"{menge}x {item}" + (f" + {s_name}" if s_name else "")
            r_nr = f"WE-{date.today().strftime('%y%m%d')}-{k_name[:3].upper()}"
            db.execute("INSERT INTO bookings (kunde, email, details, von, bis, umsatz, rechnungs_nr, personal, status, zusatz_infos) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (k_name, k_mail, details, str(start), str(ende), umsatz, r_nr, ", ".join(pers), "Offen", infos))
            db.commit(); st.success("Gespeichert!"); st.balloons()

# --- VERZEICHNIS & RÜCKGABE ---
elif choice == "📅 Verzeichnis & Rückgabe":
    st.header("Auftragsverwaltung")
    df = pd.read_sql_query("SELECT * FROM bookings", db)
    if not df.empty:
        df['Status'] = df.apply(lambda x: get_live_status(x['von'], x['bis'], x['status']), axis=1)
        st.dataframe(df[['rechnungs_nr', 'kunde', 'Status', 'umsatz']], use_container_width=True)
        target = st.selectbox("Buchung wählen für Details/Rückgabe/PDF:", ["-- Wählen --"] + df['rechnungs_nr'].tolist())
        if target != "-- Wählen --":
            b = df[df['rechnungs_nr'] == target].iloc[0]
            st.info(f"**Details:** {b['details']} | **Personal:** {b['personal']} | **Notizen:** {b['zusatz_infos']}")
            c1, c2 = st.columns(2)
            with c1:
                pdf_bytes = create_pdf(b)
                st.download_button("📄 PDF Rechnung", data=pdf_bytes, file_name=f"Rechnung_{target}.pdf")
            with c2:
                if b['status'] != "Abgeschlossen":
                    with st.expander("📥 Rückgabe protokollieren"):
                        v = st.text_area("Vorfälle/Schäden:", value="Keine")
                        if st.button("Projekt abschließen"):
                            db.execute("UPDATE bookings SET status='Abgeschlossen', vorfaelle=? WHERE rechnungs_nr=?", (v, target))
                            db.commit(); st.rerun()
                else: st.success(f"Abgeschlossen. Vorfälle: {b['vorfaelle']}")

# --- TEAM ---
elif choice == "👥 Team":
    st.header("Personalverwaltung")
    with st.form("team"):
        nu, np, nr = st.text_input("Name"), st.text_input("Passwort"), st.selectbox("Rolle", ["User", "Admin"])
        if st.form_submit_button("Anlegen"):
            db.execute("INSERT INTO users VALUES (?,?,?)", (nu, np, nr))
            db.commit(); st.rerun()
    st.table(pd.read_sql_query("SELECT user, role FROM users", db))



