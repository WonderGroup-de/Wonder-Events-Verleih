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
    conn = sqlite3.connect('wonder_events_final_v4.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user TEXT PRIMARY KEY, password TEXT, role TEXT)')
    # Erweitertes Inventar für Pakete und beide Preistypen
    c.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, name TEXT, typ TEXT, beschreibung TEXT, 
                  preis_stunde REAL, preis_tag REAL)''')
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
    pdf.cell(140, 10, 'Leistungen / Artikel', 1, 0, 'L', True)
    pdf.cell(50, 10, 'Gesamtbetrag', 1, 1, 'C', True)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(140, 10, b_data["details"], 1)
    pdf.set_xy(150, pdf.get_y() - 10) # Position korrigieren für Betrag-Spalte
    pdf.cell(50, 10, f'{b_data["umsatz"]:.2f} EUR', 1, 1, 'R')
    if b_data["zusatz_infos"]:
        pdf.ln(5)
        pdf.set_font('Arial', 'I', 10)
        pdf.multi_cell(0, 6, f'Hinweise: {b_data["zusatz_infos"]}')
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 14)
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
choice = st.sidebar.radio("Menü", ["📊 Dashboard", "📅 Verzeichnis & Rückgabe", "📝 Neue Buchung", "📦 Lager & Pakete", "👥 Team"])

# --- DASHBOARD & TEAM (IDENTISCH ZU VORHER) ---
if choice == "📊 Dashboard":
    st.header("Geschäftsübersicht")
    df = pd.read_sql_query("SELECT umsatz, von FROM bookings", db)
    if not df.empty:
        c1, c2 = st.columns(2); c1.metric("Gesamtumsatz", f"{df['umsatz'].sum():,.2f} €"); c2.metric("Buchungen", len(df))
        st.plotly_chart(px.bar(df, x="von", y="umsatz", title="Umsatzverlauf"), use_container_width=True)
    else: st.info("Noch keine Daten.")

elif choice == "👥 Team":
    st.header("Personal")
    with st.form("t"):
        nu, np, nr = st.text_input("Name"), st.text_input("PW"), st.selectbox("Rolle", ["User", "Admin"])
        if st.form_submit_button("Anlegen"):
            db.execute("INSERT INTO users VALUES (?,?,?)", (nu, np, nr)); db.commit(); st.rerun()
    st.table(pd.read_sql_query("SELECT user, role FROM users", db))

# --- LAGER & PAKETE ---
elif choice == "📦 Lager & Pakete":
    st.header("Inventar & Partypakete")
    with st.expander("➕ Neues Equipment / Paket anlegen"):
        typ = st.radio("Typ", ["Einzelgerät", "Paket"])
        n = st.text_input("Name (z.B. Partypaket 'Geile Flotte')")
        bes = st.text_area("Beschreibung / Inhalt (für Paket wichtig)")
        c1, c2 = st.columns(2)
        p_st = c1.number_input("Stundenpreis (€)", min_value=0.0)
        p_tg = c2.number_input("Tagespreis (€)", min_value=0.0)
        if st.button("Speichern"):
            db.execute("INSERT INTO inventory (name, typ, beschreibung, preis_stunde, preis_tag) VALUES (?,?,?,?,?)", (n, typ, bes, p_st, p_tg))
            db.commit(); st.rerun()
    
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    st.dataframe(inv_df, use_container_width=True)

# --- NEUE BUCHUNG (DAS WARENKORB-SYSTEM) ---
elif choice == "📝 Neue Buchung":
    st.header("Projekt-Kalkulator")
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    users_df = pd.read_sql_query("SELECT user FROM users", db)
    
    if 'cart' not in st.session_state: st.session_state.cart = []
    
    with st.container():
        st.subheader("🛒 Warenkorb")
        c1, c2, c3 = st.columns([3,1,1])
        item_select = c1.selectbox("Artikel/Paket wählen", inv_df["name"].tolist() if not inv_df.empty else ["Leer"])
        item_qty = c2.number_input("Anzahl", min_value=1, value=1)
        if c3.button("Hinzufügen"):
            st.session_state.cart.append({"name": item_select, "qty": item_qty})
            st.toast(f"{item_select} hinzugefügt!")

        if st.session_state.cart:
            for i, c in enumerate(st.session_state.cart):
                st.write(f"✅ {c['qty']}x {c['name']}")
            if st.button("Warenkorb leeren"): st.session_state.cart = []; st.rerun()

    st.divider()
    with st.form("booking_final", clear_on_submit=True):
        col1, col2 = st.columns(2)
        k_name, k_mail = col1.text_input("Kunde"), col2.text_input("E-Mail")
        v_dt = st.date_input("Start"); v_tm = st.time_input("Zeit Start")
        b_dt = st.date_input("Ende"); b_tm = st.time_input("Zeit Ende")
        pers = st.multiselect("Personal", users_df["user"].tolist())
        infos = st.text_area("Spezialauftrag / Hinweise")
        
        if st.form_submit_button("🚀 JETZT VERBINDLICH BUCHEN"):
            if not st.session_state.cart:
                st.error("Warenkorb ist leer!")
            else:
                start, ende = datetime.combine(v_dt, v_tm), datetime.combine(b_dt, b_tm)
                dauer = ende - start
                stunden = dauer.total_seconds() / 3600
                tage = dauer.days
                
                gesamt_umsatz = 0
                detail_text = ""
                
                for c in st.session_state.cart:
                    row = inv_df[inv_df["name"] == c["name"]].iloc[0]
                    # Logik: Wenn < 24h, rechne Stunden, sonst Tage
                    if stunden < 24:
                        preis = row["preis_stunde"] * c["qty"] * max(1, int(stunden))
                        detail_text += f"{c['qty']}x {c['name']} (Std-Tarif)\n"
                    else:
                        preis = row["preis_tag"] * c["qty"] * max(1, tage)
                        detail_text += f"{c['qty']}x {c['name']} (Tag-Tarif)\n"
                    gesamt_umsatz += preis
                
                r_nr = f"WE-{date.today().strftime('%y%m%d')}-{k_name[:3].upper()}"
                db.execute("""INSERT INTO bookings (kunde, email, details, von, bis, umsatz, rechnungs_nr, personal, status, zusatz_infos) 
                              VALUES (?,?,?,?,?,?,?,?,?,?)""", 
                           (k_name, k_mail, detail_text, str(start), str(ende), gesamt_umsatz, r_nr, ", ".join(pers), "Offen", infos))
                db.commit()
                st.session_state.cart = []
                st.success(f"Gebucht! Gesamt: {gesamt_umsatz:.2f}€"); st.balloons()

# --- VERZEICHNIS & RÜCKGABE ---
elif choice == "📅 Verzeichnis & Rückgabe":
    st.header("Auftragsverwaltung")
    df = pd.read_sql_query("SELECT * FROM bookings", db)
    if not df.empty:
        df['Status'] = df.apply(lambda x: get_live_status(x['von'], x['bis'], x['status']), axis=1)
        st.dataframe(df[['rechnungs_nr', 'kunde', 'Status', 'umsatz']], use_container_width=True)
        target = st.selectbox("Aktion für:", ["-- Wählen --"] + df['rechnungs_nr'].tolist())
        if target != "-- Wählen --":
            b = df[df['rechnungs_nr'] == target].iloc[0]
            st.text_area("Inhalt & Notizen", value=f"{b['details']}\n\nPersonal: {b['personal']}\n\nInfos: {b['zusatz_infos']}", height=150)
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 PDF Rechnung", data=create_pdf(b), file_name=f"Rechnung_{target}.pdf")
            with c2:
                if b['status'] != "Abgeschlossen":
                    if st.button("✅ Rückgabe & Projekt schließen"):
                        db.execute("UPDATE bookings SET status='Abgeschlossen' WHERE rechnungs_nr=?", (target,))
                        db.commit(); st.rerun()
    else: st.info("Keine Buchungen vorhanden.")
