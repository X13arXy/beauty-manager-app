import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import sqlite3
import time
from dotenv import load_dotenv

# Import biblioteki SMSAPI
try:
    from smsapi.client import SmsApiPlClient
    from smsapi.exception import SmsApiException
except ImportError:
    st.error("Brakuje biblioteki! Wpisz w terminalu: pip install smsapi-client")
    st.stop()

# --- 1. KONFIGURACJA ---
load_dotenv()

# Konfiguracja Google AI
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("❌ Brak klucza GOOGLE_API_KEY w pliku .env!")
    st.stop()

genai.configure(api_key=api_key)
# Model Flash (szybki i tani)
model = genai.GenerativeModel('models/gemini-flash-latest')

# Nazwa bazy danych
DB_NAME = "baza_beauty.db"

# --- 2. FUNKCJE POMOCNICZE ---

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS klientki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imie TEXT NOT NULL,
            telefon TEXT NOT NULL,
            ostatni_zabieg TEXT,
            data_wizyty TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_client(imie, telefon, zabieg, data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO klientki (imie, telefon, ostatni_zabieg, data_wizyty) VALUES (?, ?, ?, ?)',
              (imie, telefon, zabieg, data))
    conn.commit()
    conn.close()

def get_clients():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM klientki", conn)
    conn.close()
    return df

def delete_client(client_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM klientki WHERE id = ?', (client_id,))
    conn.commit()
    conn.close()

def usun_ogonki(tekst):
    """Zamienia polskie znaki na łacińskie dla SMSAPI"""
    mapa = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

init_db()

# --- 3. INTERFEJS APLIKACJI ---
st.set_page_config(page_title="Beauty Manager AI", page_icon="💅", layout="wide")
st.title("💅 Beauty Manager & AI Agent")

page = st.sidebar.radio("Nawigacja", ["📂 Baza Klientek", "🤖 Automat SMS"])

# ==========================================
# ZAKŁADKA 1: BAZA DANYCH
# ==========================================
if page == "📂 Baza Klientek":
    st.header("Zarządzaj swoją bazą")
    
    with st.expander("➕ Dodaj nową klientkę", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            new_imie = st.text_input("Imię")
            new_tel = st.text_input("Telefon (np. 48123456789)")
        with col2:
            new_zabieg = st.text_input("Ostatni Zabieg", value="Manicure")
            new_data = st.date_input("Data Ostatniej Wizyty").strftime("%Y-%m-%d")
        
        if st.button("Zapisz w bazie"):
            if new_imie and new_tel:
                add_client(new_imie, new_tel, new_zabieg, new_data)
                st.success(f"✅ Dodano {new_imie} do bazy!")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("⚠️ Podaj Imię i Telefon.")

    st.subheader("Twoje Klientki:")
    df = get_clients()
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        col_del1, col_del2 = st.columns([1, 3])
        with col_del1:
            id_to_del = st.number_input("ID do usunięcia", min_value=1, step=1)
        with col_del2:
            st.write("") 
            st.write("") 
            if st.button("🗑️ Usuń wpis"):
                delete_client(id_to_del)
                st.warning(f"Usunięto ID: {id_to_del}")
                time.sleep(1)
                st.rerun()
    else:
        st.info("Baza jest pusta.")

# ==========================================
# ZAKŁADKA 2: AUTOMAT SMS
# ==========================================
elif page == "🤖 Automat SMS":
    st.header("✨ Automat SMS (Powered by SMSAPI)")
    
    df = get_clients()
    
    if df.empty:
        st.error("❌ Baza jest pusta! Najpierw dodaj klientki.")
    else:
        client_names = df['imie'].tolist()
        selected_names = st.multiselect("Do kogo wysłać?", client_names, default=client_names)
        target_df = df[df['imie'].isin(selected_names)]
        
        st.info(f"Wybrano: {len(target_df)} osób.")
        
        with st.container(border=True):
            st.subheader("⚙️ Konfiguracja Kampanii")
            salon_name = st.text_input("Nazwa Salonu", value="Glow Studio")
            
            cele = [
                "Przypomnienie o wizycie (Standard)", 
                "🔥 LAST MINUTE (Zwolnił się termin jutro!)",
                "🎂 Urodziny (-20%)",
                "⭐ Prośba o opinię Google",
                "✏️ Własny cel..."
            ]
            wybor_celu = st.selectbox("Cel wiadomości:", cele)
            
            if wybor_celu == "✏️ Własny cel...":
                campaign_goal = st.text_input("Wpisz swój cel:")
            else:
                campaign_goal = wybor_celu
            
            test_mode = st.checkbox("🛠️ TRYB TESTOWY (Bezpieczny - nie wysyła naprawdę)", value=True)

        btn_text = "🚀 WYŚLIJ SYMULACJĘ" if test_mode else "💸 WYŚLIJ NAPRAWDĘ (PŁATNE)"
        btn_type = "secondary" if test_mode else "primary"
        
        if st.button(btn_text, type=btn_type):
            
            sms_token = os.getenv("SMSAPI_TOKEN")
            if not test_mode and not sms_token:
                st.error("❌ Brak tokenu SMSAPI w pliku .env!")
                st.stop()
            
            client = None
            if not test_mode:
                try:
                    client = SmsApiPlClient(access_token=sms_token)
                except Exception as e:
                    st.error(f"Błąd logowania SMSAPI: {e}")
                    st.stop()

            st.write("---")
            progress_bar = st.progress(0)
            
            # --- KONFIGURACJA BEZPIECZEŃSTWA (Wyłączamy filtry) ---
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            for index, row in target_df.iterrows():
                
                prompt = f"""
                Jesteś recepcjonistką w salonie beauty "{salon_name}". 
                Napisz krótkiego SMS-a (max 160 znaków).
                
                KLIENTKA: {row['imie']} (Ostatni zabieg: {row['ostatni_zabieg']})
                CEL: {campaign_goal}
                
                ZASADY:
                1. Pisz naturalnie, ładną polszczyzną (my to potem oczyścimy z ogonków).
                2. Używaj języka korzyści.
                3. Dodaj 1 emoji.
                4. Podpisz się nazwą salonu.
                """
                
                try:
                    # Generowanie z wyłączonymi filtrami
                    response = model.generate_content(prompt, safety_settings=safety_settings)
                    
                    # Sprawdzenie czy odpowiedź nie jest pusta
                    if not response.parts:
                        st.warning(f"⚠️ AI nie zwróciło treści dla {row['imie']}. Może być problem z połączeniem.")
                        continue

                    raw_text = response.text.strip()
                    clean_text = usun_ogonki(raw_text)
                    
                    if test_mode:
                        st.success(f"🧪 [TEST] Do: {row['imie']} ({row['telefon']})")
                        st.code(clean_text)
                    else:
                        try:
                            client.sms.send(to=row['telefon'], message=clean_text)
                            st.success(f"✅ Wysłano do: {row['imie']}")
                        except SmsApiException as e:
                            st.error(f"Błąd bramki SMS dla {row['imie']}: {e}")
                            
                except Exception as e:
                    st.error(f"Błąd przy {row['imie']}: {e}")
                
                time.sleep(5) 
                progress_bar.progress((index + 1) / len(target_df))
            
            st.balloons()
            st.success("🎉 Kampania zakończona!")