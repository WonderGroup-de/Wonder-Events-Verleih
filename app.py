import streamlit as st
import pandas as pd
import sqlite3
import smtplib
import plotly.express as px
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

# --- KONFIGURATION & BRANDING ---
# Ersetze diesen Link mit der 'Raw'-URL deines Logos auf GitHub
LOGO_URL = "https://raw.githubusercontent.com/WonderGroup-de/Wonder-Events-Verleih/main/1000070172.jpg"

# --- DATENBANK FUNKTIONEN ---
def init_db():
    conn = sqlite3.connect('wonder_events_pro.db', check_same_thread=False)
    c = conn.cursor()
    # Tabellen für Nutzer, Inventar und Buchungen
    c.execute('CREATE TABLE IF NOT EXISTS users (user TEXT PRIMARY KEY, password TEXT, role TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, name TEXT, gesamt INTEGER, preis REAL)')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY, kunde TEXT, email TEXT, tel TEXT, item_id INTEGER, 
                  von TEXT, bis TEXT, menge INTEGER, services TEXT, status TEXT, umsatz REAL, rechnungs_nr TEXT)''')
    # Standard-Admin (Passwort bitte nach erstem Login ändern!)
    c.execute('INSERT OR IGNORE INTO users VALUES ("admin", "Wonder2026!", "Admin")')
    conn.commit()
    return conn

db = init_db()

# --- HILFSFUNKTIONEN (Mail & Verfügbarkeit) ---
def send_wonder_mail(to_email, subject, html_content):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["EMAIL_USER"]
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP("smtp.office365.com", 587)
        server.starttls()
        server.login(st.secrets["EMAIL_USER"], st.secrets["EMAIL_PASS"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Mail-Fehler: {e}")
        return False

# --- UI LOGIK: LOGIN ---
def login_screen():
    st.markdown(f"""
        <style>
        .stApp {{
            background: linear_gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), url("{LOGO_URL}");
            background-size: cover;
        }}
        .login-card {{
            background-color: rgba(255, 255, 255, 0.95);
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            text-align: center;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.image(LOGO_URL, width=250)
        st.subheader("Mitarbeiter Login")
        user = st.text_input("Nutzername")
        pw = st.text_input("Passwort", type="password")
        if st.button("Anmelden"):
            res = db.execute("SELECT role FROM users WHERE user=? AND password=?", (user, pw)).fetchone()
            if res:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.session_state.role = res[0]
                st.rerun()
            else:
                st.error("Zugangsdaten ungültig.")
        st.markdown('</div>', unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_screen()
    st.stop()

# --- HAUPTMENÜ ---
st.sidebar.image(LOGO_URL)
st.sidebar.title("Wonder-Events")
st.sidebar.write(f"Nutzer: **{st.session_state.user}** ({st.session_state.role})")

menu = ["📊 Dashboard", "📅 Buchungsverzeichnis", "📝 Neue Buchung", "📦 Inventar"]
if st.session_state.role == "Admin":
    menu.append("👥 Team-Verwaltung")

choice = st.sidebar.radio("Navigation", menu)

# --- 1. DASHBOARD (Grafiken & Umsatz) ---
if choice == "📊 Dashboard":
    st.header("Geschäftsentwicklung & Analyse")
    df_b = pd.read_sql_query("SELECT b.*, i.name as tech FROM bookings b JOIN inventory i ON b.item_id = i.id", db)
    
    if not df_b.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Meistgebuchte Artikel")
            fig1 = px.bar(df_b.groupby('tech').size().reset_index(name='Anzahl'), x='tech', y='Anzahl', color='tech')
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            st.subheader("Umsatz-Verteilung")
            fig2 = px.pie(df_b, values='umsatz', names='tech', hole=0.3)
            st.plotly_chart(fig2, use_container_width=True)
        
        st.metric("Gesamtumsatz 2026", f"{df_b['umsatz'].sum():,.2f} €")
    else:
        st.info("Noch keine Buchungen vorhanden.")

# --- 2. NEUE BUCHUNG (Mit Zusatz-Services) ---
elif choice == "📝 Neue Buchung":
    st.header("Neue Buchung erfassen")
    inv_df = pd.read_sql_query("SELECT * FROM inventory", db)
    
    with st.form("booking_form"):
        col1, col2 = st.columns(2)
        k_name = col1.text_input("Kundenname")
        k_mail = col2.text_input("E-Mail")
        k_tel = col1.text_input("Telefonnummer")
        
        item_name = st.selectbox("Equipment", inv_df["name"].tolist() if not inv_df.empty else ["Bitte Inventar anlegen"])
        menge = st.number_input("Menge", min_value=1, value=1)
        
        d1 = st.date_input("Von", date.today())
        d2 = st.date_input("Bis (Rückgabe)", date.today() + timedelta(days=1))
        
        services = st.multiselect("Zusatz-Services", ["Aufbau", "Lieferung", "Selbstabholung", "Selbstaufbau"])
        
        if st.form_submit_button("Buchung abschließen & Bestätigung senden"):
            item_row = inv_df[inv_df["name"] == item_name].iloc[0]
            tage = (d2 - d1).days
            if tage <= 0: tage = 1
            gesamt_preis = (item_row["preis"] * menge) * tage
            r_nr = f"WE-{datetime.now().strftime('%Y%m%d')}-{k_name[:3].upper()}"
            
            db.execute("INSERT INTO bookings (kunde, email, tel, item_id, von, bis, menge, services, status, umsatz, rechnungs_nr) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (k_name, k_mail, k_tel, int(item_row["id"]), str(d1), str(d2), menge, ", ".join(services), "Bestätigt", gesamt_preis, r_nr))
            db.commit()
            
            # E-Mail Inhalt
            html = f"""
            <div style="font-family: Arial; border: 1px solid #ddd; padding: 20px;">
                <img src="{LOGO_URL}" width="150"><br>
                <h2>Buchungsbestätigung {r_nr}</h2>
                <p>Hallo <b>{k_name}</b>, vielen Dank für deine Buchung bei Wonder-Events.</p>
                <p><b>Equipment:</b> {menge}x {item_name}<br>
                <b>Zeitraum:</b> {d1} bis {d2}<br>
                <b>Services:</b> {", ".join(services)}</p>
                <hr>
                <p style="color: red; font-weight: bold;">Zahlungsziel: Der Betrag von {gesamt_preis:.2f} € ist spätestens bei Rückgabe am {d2} fällig.</p>
                <p>Beste Grüße,<br>Dein Team von Wonder-Events (Wonder-Group Malsch)</p>
            </div>
            """
            if send_wonder_mail(k_mail, f"Deine Buchung bei Wonder-Events ({r_nr})", html):
                st.success(f"Buchung gespeichert und Bestätigung an {k_mail} gesendet!")

# --- 3. BUCHUNGSVERZEICHNIS ---
elif choice == "📅 Buchungsverzeichnis":
    st.header("Alle Vorgänge")
    v_df = pd.read_sql_query("SELECT b.rechnungs_nr, b.kunde, i.name as Equipment, b.von, b.bis, b.umsatz, b.status FROM bookings b JOIN inventory i ON b.item_id = i.id", db)
    st.dataframe(v_df, use_container_width=True)

# --- 4. INVENTAR ---
elif choice == "📦 Inventar":
    st.header("Lagerbestand")
    if st.session_state.role == "Admin":
        with st.expander("Neues Gerät hinzufügen"):
            n = st.text_input("Gerätename")
            a = st.number_input("Anzahl", min_value=1)
            p = st.number_input("Preis pro Tag (€)", min_value=0.0)
            if st.button("Hinzufügen"):
                db.execute("INSERT INTO inventory (name, gesamt, preis) VALUES (?,?,?)", (n, a, p))
                db.commit()
                st.rerun()
    
    st.table(pd.read_sql_query("SELECT * FROM inventory", db))

# --- 5. TEAM (Nur Admin) ---
elif choice == "👥 Team-Verwaltung":
    st.header("Nutzerrechte & Team")
    with st.form("new_user"):
        nu = st.text_input("Neuer Nutzername")
        np = st.text_input("Passwort")
        nr = st.selectbox("Rolle", ["User", "Admin"])
        if st.form_submit_button("Nutzer anlegen"):
            db.execute("INSERT INTO users VALUES (?,?,?)", (nu, np, nr))
            db.commit()
            st.rerun()
    st.table(pd.read_sql_query("SELECT user, role FROM users", db))
