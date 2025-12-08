import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import time
# Usunęliśmy: from dotenv import load_dotenv
from supabase import create_client, Client


# --- 1. KONFIGURACJA I CSS ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")

# Style CSS dla ładniejszego wyglądu logowania
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .auth-container { max-width: 400px; margin: auto; padding: 20px; }
</style>
""", unsafe_allow_html=True)

# --- ŁADOWANIE KLUCZY Z CHMURY (TYLKO st.secrets) ---

# Używamy st.secrets do pobrania kluczy z [secrets]
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    SMSAPI_TOKEN = st.secrets["SMSAPI_TOKEN"]

except KeyError as e:
    # Ten błąd wystąpi, jeśli klucz jest źle nazwany lub brakuje nagłówka [secrets]
    st.error(f"❌ Błąd: Brak klucza {e} w Streamlit Secrets!")
    st.info("Sprawdź, czy w sekcji Secrets wkleiłeś klucze w formacie TOML, np. [secrets] i czy nazwy są poprawne.")
    st.stop()


# Sprawdzamy, czy klucze nie są puste (co oznacza, że TOML się wczytał, ale wartość jest pusta)
if not all([SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY]):
    st.error("❌ Błąd wartości! Jeden z kluczy (Supabase URL/Key, Google API Key) jest pusty.")
    st.stop()

# Inicjalizacja klientów
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    # Catching 'Invalid URL' z Supabase
    st.error(f"❌ Błąd połączenia Supabase: {e}. Sprawdź, czy SUPABASE_URL jest poprawny i nie zawiera spacji.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-flash-latest')

try:
    from smsapi.client import SmsApiPlClient
    from smsapi.exception import SmsApiException
except ImportError:
    st.warning("Brak biblioteki smsapi-client na serwerze. Automat SMS może nie działać.")

# --- 2. ZARZĄDZANIE SESJĄ (LOGOWANIE) ---

if 'user' not in st.session_state:
    st.session_state['user'] = None

def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state['user'] = response.user
        st.success("✅ Zalogowano pomyślnie!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Błąd logowania: {e}")

def register_user(email, password):
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user:
            st.session_state['user'] = response.user
            st.success("✅ Konto utworzone! Zalogowano.")
            time.sleep(1)
            st.rerun()
    except Exception as e:
        st.error(f"Błąd rejestracji: {e}")

def logout_user():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- 3. EKRAN LOGOWANIA ---

if not st.session_state['user']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("💅 Beauty SaaS")
        st.subheader("Zaloguj się do swojego salonu")
        
        tab1, tab2 = st.tabs(["Logowanie", "Rejestracja"])
        
        with tab1:
            l_email = st.text_input("Email", key="l_email")
            l_pass = st.text_input("Hasło", type="password", key="l_pass")
            if st.button("Zaloguj się", type="primary"):
                login_user(l_email, l_pass)
                
        with tab2:
            st.info("Załóż konto, aby otrzymać własną, bezpieczną bazę danych.")
            r_email = st.text_input("Email", key="r_email")
            r_pass = st.text_input("Hasło", type="password", key="r_pass")
            if st.button("Załóż konto"):
                register_user(r_email, r_pass)
    
    st.stop()  # ZATRZYMUJEMY KOD TUTAJ JEŚLI NIE ZALOGOWANY

# =========================================================
#  TUTAJ ZACZYNA SIĘ APLIKACJA DLA ZALOGOWANEGO UŻYTKOWNIKA
# =========================================================

# Pobieramy ID użytkownika z Supabase - to jest teraz nasz SALON_ID!
CURRENT_USER = st.session_state['user']
SALON_ID = CURRENT_USER.id 
USER_EMAIL = CURRENT_USER.email

# Sidebar z informacjami o koncie
with st.sidebar:
    st.write(f"Zalogowano jako: **{USER_EMAIL}**")
    if st.button("Wyloguj"):
        logout_user()
    st.divider()

# --- 4. FUNKCJE BAZODANOWE (SaaS) ---

def add_client(imie, telefon, zabieg, data):
    payload = {
        "salon_id": SALON_ID, 
        "imie": imie,
        "telefon": telefon,
        "ostatni_zabieg": zabieg,
        "data_wizyty": str(data)
    }
    try:
        supabase.table("klientki").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")
        return False

def get_clients():
    try:
        response = supabase.table("klientki").select("*").eq("salon_id", SALON_ID).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        return pd.DataFrame()

def delete_client(client_id):
    try:
        supabase.table("klientki").delete().eq("id", client_id).eq("salon_id", SALON_ID).execute()
    except Exception as e:
        st.error(f"Błąd usuwania: {e}")

def usun_ogonki(tekst):
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

# --- 5. INTERFEJS GŁÓWNY ---

st.title(f"Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

if page == "📂 Baza Klientek":
    st.header("Twoja Baza")
    
    with st.expander("➕ Dodaj klientkę", expanded=False):
        c1, c2 = st.columns(2)
        imie = c1.text_input("Imię i Nazwisko")
        tel = c1.text_input("Telefon")
        zabieg = c2.text_input("Zabieg", "Manicure")
        data = c2.date_input("Data wizyty")
        
        if st.button("Zapisz"):
            if imie and tel:
                add_client(imie, tel, zabieg, data)
                st.success("Dodano!")
                time.sleep(0.5)
                st.rerun()

    df = get_clients()
    if not df.empty:
        st.dataframe(df[['imie', 'telefon', 'ostatni_zabieg', 'data_wizyty']], use_container_width=True)
        
        cl_list = df.set_index('id')['imie'].to_dict()
        if cl_list:
            to_del = st.selectbox("Usuń klientkę:", options=cl_list.keys(), format_func=lambda x: cl_list[x])
            if st.button("Usuń wybraną"):
                delete_client(to_del)
                st.rerun()
    else:
        st.info("Twoja baza jest pusta. Dodaj pierwszą klientkę!")

elif page == "🤖 Automat SMS":
    st.header("Generator SMS AI")
    df = get_clients()
    
    if df.empty:
        st.warning("Najpierw dodaj klientki w bazie!")
    else:
        wybrane = st.multiselect("Odbiorcy:", df['imie'].tolist(), default=df['imie'].tolist())
        target = df[df['imie'].isin(wybrane)]
        
        cel = st.selectbox("Cel:", ["Przypomnienie", "Promocja -20%", "Wolny termin jutro", "Inny..."])
        if cel == "Inny...":
            cel = st.text_input("Wpisz cel:")
            
        if st.button("Generuj i Wyślij (Test)"):
            st.write("Generowanie wiadomości dla:", ", ".join(wybrane))
            
            progress = st.progress(0)
            for i, (_, row) in enumerate(target.iterrows()):
                prompt = f"""
                Jesteś recepcjonistką w salonie beauty {USER_EMAIL}. 
                Napisz krótkiego SMS-a (max 160 znaków).
                KLIENTKA: {row['imie']} (Ostatni zabieg: {row['ostatni_zabieg']})
                CEL: {cel}
                ZASADY: 1. Pisz naturalnie. 2. Używaj języka korzyści. 3. Dodaj 1 emoji. 4. Podpisz się nazwą salonu (np. Glow Studio).
                """
                
                try:
                    res = model.generate_content(prompt)
                    clean = usun_ogonki(res.text)
                    st.info(f"Do {row['imie']}: {clean}")
                except Exception as e:
                    st.error(f"Błąd AI dla {row['imie']}: {e}")
                    
                time.sleep(1)
                progress.progress((i+1)/len(target))
            st.success("Gotowe!")
