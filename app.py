import streamlit as st
import pandas as pd
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

# --- KONFIGURATION (Hier später deine Daten eintragen) ---
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
EMAIL_USER = "deine-mail@outlook.de"  # Deine Outlook Mail
EMAIL_PASS = "dein-passwort"          # Dein Passwort (oder App-Passwort)

# --- DATENBANK FUNKTIONEN ---
def init_db():
    conn = sqlite3.connect('rentals.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, name TEXT, gesamt INTEGER, preis REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY, kunde TEXT, email TEXT, item_id INTEGER, von TEXT, bis TEXT, menge INTEGER, status TEXT)''')
    conn.commit()
    conn.close()

def get_inventory():
    conn = sqlite3.connect('rentals.db')
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    return df

def add_booking(kunde, email, item_id, von, bis, menge):
    conn = sqlite3.connect('rentals.db')
    c = conn.cursor()
    c.execute("INSERT INTO bookings (kunde, email, item_id, von, bis, menge, status) VALUES (?,?,?,?,?,?,?)",
              (kunde, email, item_id, str(von), str(bis), menge, "Bestätigt"))
    conn.commit()
    conn.close()

# --- E-MAIL FUNKTION ---
def send_mail(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"E-Mail Fehler: {e}")
        return False

# --- APP START ---
init_db()
st.title("VT-Rental Manager Pro")

menu = ["Verfügbarkeit", "Neue Buchung", "Inventar & Admin"]
choice = st.sidebar.radio("Navigation", menu)

# --- INVENTAR & ADMIN ---
if choice == "Inventar & Admin":
    st.header("📦 Lagerverwaltung")
    inv = get_inventory()
    st.dataframe(inv, use_container_width=True)
    
    with st.expander("Neues Equipment hinzufügen"):
        name = st.text_input("Gerätename")
        anz = st.number_input("Anzahl im Lager", min_value=1)
        pr = st.number_input("Preis / Tag", min_value=0.0)
        if st.button("Hinzufügen"):
            conn = sqlite3.connect('rentals.db')
            conn.execute("INSERT INTO inventory (name, gesamt, preis) VALUES (?,?,?)", (name, anz, pr))
            conn.commit()
            conn.close()
            st.rerun()

# --- NEUE BUCHUNG MIT CHECK ---
elif choice == "Neue Buchung":
    st.header("📝 Neue Buchung & E-Mail")
    inv = get_inventory()
    
    with st.form("booking"):
        kunde = st.text_input("Kundenname")
        k_email = st.text_input("Kunden E-Mail")
        item_name = st.selectbox("Equipment", inv["name"].tolist())
        menge = st.number_input("Menge", min_value=1)
        von = st.date_input("Von", date.today())
        bis = st.date_input("Bis", date.today())
        
        if st.form_submit_button("Buchen & Mail senden"):
            item_id = inv[inv["name"] == item_name]["id"].iloc[0]
            
            # Verfügbarkeits-Logik
            conn = sqlite3.connect('rentals.db')
            res = pd.read_sql_query(f"SELECT SUM(menge) as gebucht FROM bookings WHERE item_id={item_id} AND status='Bestätigt' AND von <= '{bis}' AND bis >= '{von}'", conn)
            gebucht = res["gebucht"].iloc[0] or 0
            gesamt = inv[inv["id"] == item_id]["gesamt"].iloc[0]
            
            if (gesamt - gebucht) >= menge:
                add_booking(kunde, k_email, item_id, von, bis, menge)
                mail_text = f"Hallo {kunde},\ndanke für deine Buchung von {menge}x {item_name}.\nZeitraum: {von} bis {bis}.\n\nBeste Grüße!"
                if send_mail(k_email, "Buchungsbestätigung", mail_text):
                    st.success("Erfolgreich gebucht und Mail gesendet!")
            else:
                st.error(f"❌ Nicht verfügbar! Nur noch {gesamt - gebucht} Stück frei.")
