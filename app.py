import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import time
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
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    SMSAPI_TOKEN = st.secrets.get("SMSAPI_TOKEN", "") # Opcjonalne

except KeyError as e:
    st.error(f"❌ Błąd: Brak klucza {e} w Streamlit Secrets! Sprawdź format TOML.")
    st.stop()

if not all([SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY]):
    st.error("❌ Błąd wartości! Jeden z kluczy jest pusty.")
    st.stop()

# Inicjalizacja klientów
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Błąd połączenia Supabase: {e}. Sprawdź URL i KEY.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
# Używamy modelu 1.5 Flash (najbezpieczniejszy dla limitów)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

try:
    from smsapi.client import SmsApiPlClient
    from smsapi.exception import SmsApiException
except ImportError:
    st.warning("Brak biblioteki smsapi-client na serwerze.")

# --- 2. ZARZĄDZANIE SESJĄ (LOGOWANIE/STAN) ---

if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'sms_preview' not in st.session_state:
    st.session_state['sms_preview'] = None
if 'preview_client' not in st.session_state:
    st.session_state['preview_client'] = None
if 'campaign_goal' not in st.session_state:
    st.session_state['campaign_goal'] = ""
if 'salon_name' not in st.session_state:
    st.session_state['salon_name'] = ""


# --- FUNKCJE AUTORYZACJI (LOGOWANIE) ---
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
    
    st.stop()

# =========================================================
#  TUTAJ ZACZYNA SIĘ APLIKACJA DLA ZALOGOWANEGO UŻYTKOWNIKA
# =========================================================

CURRENT_USER = st.session_state['user']
SALON_ID = CURRENT_USER.id 
USER_EMAIL = CURRENT_USER.email

with st.sidebar:
    st.write(f"Zalogowano jako: **{USER_EMAIL}**")
    if st.button("Wyloguj"):
        logout_user()
    st.divider()

# --- 4. FUNKCJE BAZODANOWE ---

def usun_ogonki(tekst):
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

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
        
# --- FUNKCJA WYSYŁAJĄCA KAMPANIĘ SMS ---
def send_campaign_sms(target_df, campaign_goal, generated_text, is_test_mode):
    
    sms_token = st.secrets.get("SMSAPI_TOKEN", "")
    
    client = None
    if not is_test_mode:
        if not sms_token:
             st.error("❌ Brak tokenu SMSAPI!")
             return
        try:
            client = SmsApiPlClient(access_token=sms_token)
        except Exception as e:
            st.error(f"Błąd logowania SMSAPI: {e}")
            return

    st.write("---")
    progress_bar = st.progress(0)
    
    for index, row in target_df.iterrows():
        # Personalizacja
        if st.session_state['preview_client'] in generated_text:
             final_text = generated_text.replace(st.session_state['preview_client'], row['imie'])
        else:
             final_text = generated_text
        
        clean_text = usun_ogonki(final_text)

        if is_test_mode:
            # --- TRYB SYMULACJI ---
            st.code(f"SYMULACJA SMS DO: {row['imie']} ({row['telefon']})\nTREŚĆ: {clean_text}", language='text')
            st.success(f"🧪 [TEST] Symulacja wysyłki do: {row['imie']}")
        else:
            # --- TRYB PRODUKCYJNY ---
            try:
                client.sms.send(to=row['telefon'], message=clean_text)
                st.success(f"✅ Wysłano do: {row['imie']}")
            except SmsApiException as e:
                st.error(f"Błąd bramki SMS dla {row['imie']}: {e}")
            
        time.sleep(1)
        progress_bar.progress((index + 1) / len(target_df))
    
    st.balloons()
    st.success("🎉 Kampania zakończona!")


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
        st.write("### ⚙️ Konfiguracja")
        salon_name = st.text_input("1. Wpisz nazwę swojego salonu (do podpisu):", 
                                   value=st.session_state['salon_name'],
                                   placeholder="np. Kox Beauty")
        st.session_state['salon_name'] = salon_name

        campaign_goal = st.text_input("2. Wpisz CEL KAMPANII:", 
                                      value=st.session_state['campaign_goal'])
        st.session_state['campaign_goal'] = campaign_goal 

        wybrane = st.multiselect("3. Wybierz Odbiorców:", df['imie'].tolist(), default=df['imie'].tolist())
        target_df = df[df['imie'].isin(wybrane)]
        
        if not salon_name:
            st.warning("⚠️ Proszę wpisać nazwę salonu powyżej.")
        else:
            if not target_df.empty:
                sample_client = target_df.iloc[0]
                st.info(f"Wybrano: {len(target_df)} osób. Wzór wiadomości dla: {sample_client['imie']}.")
            else:
                st.warning("Wybierz przynajmniej jedną osobę.")
                st.stop()
            
            # --- PRZYCISK GENEROWANIA (TU BYŁ BŁĄD) ---
            if st.button("🔍 1. Wygeneruj Podgląd", type="secondary"):
                
                st.session_state['sms_preview'] = None
                
                # POPRAWIONY PROMPT (zamknięte cudzysłowy!)
                prompt = f"""
                Jesteś recepcjonistką w salonie: {salon_name}.
                Twoim zadaniem jest napisanie krótkiego SMS-a.

                KLIENTKA: {sample_client['imie']}
                CEL: {campaign_goal}

                ZASADY:
                1. MAX 160 ZNAKÓW.
                2. Zwróć się do klientki po imieniu.
                3. Pisz miło i zachęcająco.
                4. PODPIS: Podpisz się DOKŁADNIE taką nazwą: "{salon_name}".
                ""
                
                try:
                    response = model.generate_content(prompt)
                    raw_text = response.text.strip()
                    clean_text = usun_ogonki(raw_text)
                    
                    st.session_state['sms_preview'] = clean_text
                    st.session_state['preview_client'] = sample_client['imie']
                
                except Exception as e:
                     st.error(f"Błąd generacji AI: {e}")
                     st.session_state['sms_preview'] = "BŁĄD GENERACJI"
                
                st.rerun() 

            # --- PODGLĄD I WYSYŁKA ---
            if st.session_state['sms_preview']:
                st.subheader("Podgląd:")
                st.code(st.session_state['sms_preview'], language='text')
                st.warning(f"Treść zostanie wysłana do {len(target_df)} osób.")
                
                st.write("---")
                mode = st.radio("Wybierz tryb:", 
                                ["🧪 Tryb Testowy (Symulacja)", "💸 Tryb Produkcyjny (Płatny)"],
                                key="sms_mode_select")
                
                is_test_mode = (mode == "🧪 Tryb Testowy (Symulacja)")
                btn_label = "🚀 2. Zatwierdź i Wyślij" if not is_test_mode else "🧪 2. Symuluj Wysyłkę"
                btn_type = "primary" if not is_test_mode else "secondary"

                if st.button(btn_label, type=btn_type):
                    send_campaign_sms(target_df, campaign_goal, st.session_state['sms_preview'], is_test_mode)
                    st.session_state['sms_preview'] = None
                    st.session_state['preview_client'] = None
