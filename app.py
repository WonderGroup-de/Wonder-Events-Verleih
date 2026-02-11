import streamlit as st
import pandas as pd
import sqlite3
import smtplib
import plotly.express as px
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
import os

# --- BRANDING & KONFIGURATION ---
LOGO_URL = "https://raw.githubusercontent.com/WonderGroup-de/Wonder-Events-Verleih/main/1000070172.jpg"
LOGO_FILE = "1000070172.jpg"

def init_db():
    conn = sqlite3.connect('wonder_events_final_v3.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user TEXT PRIMARY KEY, password TEXT, role TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, name TEXT, gesamt INTEGER, preis REAL, einheit TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY, kunde TEXT, email TEXT, tel TEXT, details TEXT, 
                  von TEXT, bis TEXT, umsatz REAL, rechnungs_nr TEXT)''')
    c.execute('INSERT OR IGNORE INTO users VALUES ("admin", "Wonder2026!", "Admin")')
    conn.commit()
    return conn

db = init_db()

# --- MAIL FUNKTION ---
def send_confirmation(k_mail, k_name, r_nr, positionen, gesamt, bis_datum):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["EMAIL_USER"]
        msg['To'] = k_mail
        msg['Subject'] = f"Buchungsbestätigung {r_nr} - Wonder-Events"
        
        pos_html = "".join([f"<li>{p}</li>" for p in positionen])
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="text-align: center;"><img src="{LOGO_URL}" width="200"></div>
            <h2>Hallo {k_name},</h2>
            <p>vielen Dank für deine Buchung bei <b>Wonder-Events</b>. Hier ist die Übersicht deiner Reservierung:</p>
            <ul>{pos_html}</ul>
            <p><b>Gesamtbetrag: {gesamt:.2f} €</b></p>
            <hr>
            <p style="color: #e67e22; font-weight: bold;">Zahlungsinformation: 
            Der Betrag ist spätestens zur Rückgabe am {bis_datum} fällig.</p>
            <p>Beste Grüße,<br>Dein Team von Wonder-Events<br><em>Zugehörig zur Wonder-Group Malsch</em></p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))
        server = smtplib.SMTP("smtp.office365.com", 587)
        server.starttls()
        server.login(st.secrets["EMAIL_USER"], st.secrets["EMAIL_PASS"])
        server.send_message(msg)
        server.quit()
        return True
    except:
        return False

# --- UI LOGIN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.markdown(f'<style>.stApp {{background: linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.5)), url("{LOGO_URL}"); background-size: cover;}}</style>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown('<div style="background:white; padding:2rem; border-radius:15px; text-align:center;">', unsafe_allow_html=True)
        st.image(LOGO_URL, width=150)
        st.title("Wonder-Events")
        u = st.text_input("Nutzername")
        p = st.text_input("Passwort", type="password")
        if st.button("Anmelden", use_container_width=True):
            res = db.execute("SELECT role FROM users WHERE user=? AND password=?", (u, p)).fetchone()
            if res:
                st.session_state.logged_in = True
                st.session_state.user, st.session_state.role = u, res[0]
                st.rerun()
            else: st.error("Login fehlgeschlagen.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- MAIN APP ---
st.sidebar.image(LOGO_URL)
choice = st.sidebar.radio("Menü", ["📊 Dashboard", "📝 Neue Buchung", "📅 Buchungsverzeichnis", "📦 Inventar", "👥 Team"])

# --- INVENTAR ---
if choice == "📦 Inventar":
    st.header("Lagerbestand & Preise")
    with st.expander("➕ Neues Equipment anlegen"):
        n = st.text_input("Gerätename")
        anz = st.number_input("Bestand", min_value=1)
        pr = st.number_input("Preis (€)", min_value=0.0)
        ein = st.selectbox("Einheit", ["pro Tag", "pro Stunde"])
        if st.button("Speichern"):
            db.execute("INSERT INTO inventory (name, gesamt, preis, einheit) VALUES (?,?,?,?)", (n, anz, pr, ein))
            db.commit()
            st.rerun()
    st.dataframe(pd.read_sql_query("SELECT * FROM inventory", db), use_container_width=True)

# --- NEUE BUCHUNG ---
elif choice == "📝 Neue Buchung":
    st.header("Projekt-Kalkulator")
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    
    if inv_df.empty:
        st.warning("Bitte erst Inventar anlegen!")
    else:
        with st.container():
            c1, c2 = st.columns(2)
            k_name = c1.text_input("Kundenname")
            k_mail = c2.text_input("E-Mail")
            k_tel = c1.text_input("Telefon")
            
            item = st.selectbox("Technik wählen", inv_df["name"].tolist())
            menge = st.number_input("Menge", min_value=1)
            
            st.markdown("### ⏱️ Zeitraum")
            col_v, col_b = st.columns(2)
            v_dt = col_v.date_input("Start", date.today())
            v_tm = col_v.time_input("Zeit Start", datetime.now().time())
            b_dt = col_b.date_input("Ende (Rückgabe)", date.today() + timedelta(days=1))
            b_tm = col_b.time_input("Zeit Ende", datetime.now().time())
            
            st.markdown("### 🛠️ Individuelle Zusatz-Services")
            if 'services' not in st.session_state: st.session_state.services = []
            
            for i, s in enumerate(st.session_state.services):
                sc1, sc2 = st.columns([3, 1])
                st.session_state.services[i]['name'] = sc1.text_input(f"Service {i+1}", value=s['name'], key=f"sn_{i}")
                st.session_state.services[i]['preis'] = sc2.number_input(f"Preis €", value=s['preis'], key=f"sp_{i}")
            
            if st.button("➕ Weiteren Service hinzufügen"):
                st.session_state.services.append({"name": "", "preis": 0.0})
                st.rerun()

            if st.button("🚀 JETZT BUCHEN & BESTÄTIGUNG SENDEN", type="primary", use_container_width=True):
                # Kalkulation
                row = inv_df[inv_df["name"] == item].iloc[0]
                start, ende = datetime.combine(v_dt, v_tm), datetime.combine(b_dt, b_tm)
                dauer = ende - start
                einheiten = max(1, dauer.days if row["einheit"] == "pro Tag" else int(dauer.total_seconds() / 3600))
                
                eq_preis = row["preis"] * menge * einheiten
                serv_sum = sum([s['preis'] for s in st.session_state.services])
                gesamt = eq_preis + serv_sum
                
                r_nr = f"WE-{date.today().strftime('%y%m%d')}-{k_name[:3].upper()}"
                
                # Positions-Liste für Mail
                pos = [f"{menge}x {item} ({row['einheit']}): {eq_preis:.2f} €"]
                for s in st.session_state.services:
                    if s['name']: pos.append(f"{s['name']}: {s['preis']:.2f} €")
                
                db.execute("INSERT INTO bookings (kunde, email, tel, details, von, bis, umsatz, rechnungs_nr) VALUES (?,?,?,?,?,?,?,?)",
                           (k_name, k_mail, k_tel, " | ".join(pos), str(start), str(ende), gesamt, r_nr))
                db.commit()
                
                send_confirmation(k_mail, k_name, r_nr, pos, gesamt, b_dt)
                st.session_state.services = []
                st.balloons()
                st.success(f"Erfolgreich! Rechnungsbetrag: {gesamt:.2f} €")

# --- VERZEICHNIS & DASHBOARD ---
elif choice == "📅 Buchungsverzeichnis":
    st.header("Alle Aufträge")
    st.dataframe(pd.read_sql_query("SELECT rechnungs_nr, kunde, details, von, bis, umsatz FROM bookings", db), use_container_width=True)

elif choice == "📊 Dashboard":
    st.header("Wonder-Events Analytics")
    df = pd.read_sql_query("SELECT umsatz, von FROM bookings", db)
    if not df.empty:
        st.plotly_chart(px.line(df, x="von", y="umsatz", title="Umsatzverlauf"), use_container_width=True)
        st.metric("Gesamtumsatz", f"{df['umsatz'].sum():,.2f} €")
    else: st.info("Noch keine Daten.")

elif choice == "👥 Team":
    st.header("Teamverwaltung")
    if st.session_state.role == "Admin":
        with st.form("user"):
            nu, np, nr = st.text_input("Nutzer"), st.text_input("Passwort"), st.selectbox("Rolle", ["User", "Admin"])
            if st.form_submit_button("Anlegen"):
                db.execute("INSERT INTO users VALUES (?,?,?)", (nu, np, nr))
                db.commit()
                st.rerun()
    st.table(pd.read_sql_query("SELECT user, role FROM users", db))
