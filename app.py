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
    # Inventar mit Bestand
    c.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, name TEXT, typ TEXT, beschreibung TEXT, 
                  preis_stunde REAL, preis_tag REAL, bestand INTEGER)''')
    # Neue Tabelle für feste Services
    c.execute('''CREATE TABLE IF NOT EXISTS fixed_services 
                 (id INTEGER PRIMARY KEY, name TEXT, preis_stunde REAL)''')
    # Neue Tabelle für Rabattcodes
    c.execute('''CREATE TABLE IF NOT EXISTS discounts 
                 (code TEXT PRIMARY KEY, wert REAL, typ TEXT)''') # typ: 'prozent' oder 'euro'
    
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY, kunde TEXT, email TEXT, details TEXT, 
                  von TEXT, bis TEXT, umsatz REAL, rechnungs_nr TEXT, 
                  personal TEXT, status TEXT, vorfaelle TEXT, zusatz_infos TEXT)''')
    c.execute('INSERT OR IGNORE INTO users VALUES ("admin", "Wonder2026!", "Admin")')
    conn.commit()
    return conn

db = init_db()

# --- PDF GENERATOR (Detaillierte Auflistung) ---
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
    
    # Tabellenkopf
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(140, 10, 'Position / Beschreibung', 1, 0, 'L', True)
    pdf.cell(50, 10, 'Einzelpreis/Gesamt', 1, 1, 'C', True)
    
    pdf.set_font('Arial', '', 9)
    # Zeilenweise Auflistung der Details
    lines = b_data["details"].split('\n')
    for line in lines:
        if line.strip():
            pdf.multi_cell(140, 8, line, 1, 'L')
            # Hier müsste man für absolute Präzision die Preise parsen, 
            # wir nutzen der Einfachheit halber das Text-Format
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(140, 10, 'GESAMTBETRAG:', 0, 0, 'R')
    pdf.cell(50, 10, f'{b_data["umsatz"]:.2f} EUR', 0, 1, 'R')
    
    if b_data["zusatz_infos"]:
        pdf.ln(5)
        pdf.set_font('Arial', 'I', 9)
        pdf.multi_cell(0, 5, f'Hinweise: {b_data["zusatz_infos"]}')
        
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 10, f'Zahlbar bis zur Rückgabe am {b_data["bis"]}', 0, 1, 'C')
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- LOGIN & NAVI ---
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

st.sidebar.image(LOGO_URL)
choice = st.sidebar.radio("Menü", ["📊 Dashboard", "📅 Verzeichnis", "📝 Neue Buchung", "📦 Lager & Pakete", "🛠️ Services & Rabatte", "👥 Team"])

# --- 1. DASHBOARD & EXPORT ---
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
    else: st.info("Keine Daten.")

# --- 2. LAGER & BESTAND ---
elif choice == "📦 Lager & Pakete":
    st.header("Inventar-Verwaltung")
    with st.expander("➕ Equipment/Paket hinzufügen"):
        typ = st.radio("Typ", ["Gerät", "Paket"])
        n = st.text_input("Name")
        bes = st.text_area("Beschreibung")
        bst = st.number_input("Bestand (Stück)", min_value=1, value=1)
        c1, c2 = st.columns(2)
        ps, pt = c1.number_input("Std-Preis"), c2.number_input("Tag-Preis")
        if st.button("Speichern"):
            db.execute("INSERT INTO inventory (name, typ, beschreibung, preis_stunde, preis_tag, bestand) VALUES (?,?,?,?,?,?)", (n, typ, bes, ps, pt, bst))
            db.commit(); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT name, typ, bestand, preis_tag FROM inventory", db), use_container_width=True)

# --- 3. SERVICES & RABATTE ---
elif choice == "🛠️ Services & Rabatte":
    st.header("Zusatzleistungen & Ermäßigungen")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Services")
        with st.form("srv"):
            sn = st.text_input("Service Name (z.B. Aufbau)")
            sp = st.number_input("Preis pro Std")
            if st.form_submit_button("Service anlegen"):
                db.execute("INSERT INTO fixed_services (name, preis_stunde) VALUES (?,?)", (sn, sp))
                db.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT name, preis_stunde FROM fixed_services", db))
    with c2:
        st.subheader("Rabattcodes")
        with st.form("dsc"):
            dc = st.text_input("Code (z.B. TEAM10)")
            dw = st.number_input("Wert")
            dt = st.selectbox("Typ", ["prozent", "euro"])
            if st.form_submit_button("Code speichern"):
                db.execute("INSERT INTO discounts VALUES (?,?,?)", (dc, dw, dt))
                db.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM discounts", db))

# --- 4. NEUE BUCHUNG (DAS WARENKORB-PRO-SYSTEM) ---
elif choice == "📝 Neue Buchung":
    st.header("Projekt-Kalkulator")
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    srv_df = pd.read_sql_query("SELECT * FROM fixed_services", db)
    dsc_df = pd.read_sql_query("SELECT * FROM discounts", db)
    
    if 'cart' not in st.session_state: st.session_state.cart = []
    
    # Auswahl-Bereich
    with st.container():
        st.subheader("🛒 Auswahl")
        col1, col2 = st.columns(2)
        sel_item = col1.selectbox("Equipment/Paket", inv_df["name"].tolist())
        qty = col2.number_input("Menge", min_value=1, value=1)
        if st.button("➕ Zum Warenkorb"):
            st.session_state.cart.append({"typ": "item", "name": sel_item, "qty": qty})
        
        sel_srv = col1.selectbox("Zusatz-Service", srv_df["name"].tolist())
        hours = col2.number_input("Stunden", min_value=1, value=1)
        if st.button("🛠️ Service hinzufügen"):
            st.session_state.cart.append({"typ": "service", "name": sel_srv, "qty": hours})

    # Warenkorb Anzeige
    if st.session_state.cart:
        st.write("### Aktuelle Liste")
        for i, c in enumerate(st.session_state.cart):
            st.write(f"{c['qty']}x {c['name']} ({c['typ']})")
        if st.button("Warenkorb leeren"): st.session_state.cart = []; st.rerun()

    with st.form("booking_final", clear_on_submit=True):
        st.subheader("Projektdaten")
        k_name, k_mail = st.columns(2)[0].text_input("Kunde"), st.columns(2)[1].text_input("E-Mail")
        v_dt, v_tm = st.columns(2)[0].date_input("Start"), st.columns(2)[1].time_input("Startzeit")
        b_dt, b_tm = st.columns(2)[0].date_input("Ende"), st.columns(2)[1].time_input("Endzeit")
        
        rabatt_code = st.text_input("Rabatt- oder Mitarbeiter-Code")
        infos = st.text_area("Hinweise (nicht preisrelevant)")
        
        if st.form_submit_button("🚀 JETZT BUCHEN"):
            start, ende = datetime.combine(v_dt, v_tm), datetime.combine(b_dt, b_tm)
            std_total = (ende - start).total_seconds() / 3600
            tg_total = max(1, (ende - start).days)
            
            umsatz = 0
            detail_lines = []
            
            for c in st.session_state.cart:
                if c["typ"] == "item":
                    row = inv_df[inv_df["name"] == c["name"]].iloc[0]
                    p = row["preis_stunde"] * c["qty"] * int(std_total) if std_total < 24 else row["preis_tag"] * c["qty"] * tg_total
                    umsatz += p
                    detail_lines.append(f"{c['qty']}x {c['name']}: {p:.2f} EUR")
                else:
                    row = srv_df[srv_df["name"] == c["name"]].iloc[0]
                    p = row["preis_stunde"] * c["qty"]
                    umsatz += p
                    detail_lines.append(f"Service: {c['name']} ({c['qty']} Std): {p:.2f} EUR")
            
            # Rabatt-Check
            if rabatt_code in dsc_df["code"].values:
                r_row = dsc_df[dsc_df["code"] == rabatt_code].iloc[0]
                abzug = (umsatz * (r_row["wert"]/100)) if r_row["typ"] == "prozent" else r_row["wert"]
                umsatz -= abzug
                detail_lines.append(f"Rabatt ({rabatt_code}): -{abzug:.2f} EUR")
            
            r_nr = f"WE-{date.today().strftime('%y%m%d')}-{k_name[:3].upper()}"
            db.execute("INSERT INTO bookings (kunde, email, details, von, bis, umsatz, rechnungs_nr, status, zusatz_infos) VALUES (?,?,?,?,?,?,?,?,?)",
                       (k_name, k_mail, "\n".join(detail_lines), str(start), str(ende), umsatz, r_nr, "Offen", infos))
            db.commit(); st.session_state.cart = []; st.success(f"Gebucht! Summe: {umsatz:.2f}€"); st.balloons()

# --- 5. VERZEICHNIS & TEAM (IDENTISCH) ---
elif choice == "📅 Verzeichnis":
    df = pd.read_sql_query("SELECT * FROM bookings", db)
    if not df.empty:
        st.dataframe(df[['rechnungs_nr', 'kunde', 'von', 'umsatz']], use_container_width=True)
        target = st.selectbox("Aktion für:", ["-- Wählen --"] + df['rechnungs_nr'].tolist())
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
