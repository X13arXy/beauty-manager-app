import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import time
from supabase import create_client, Client

# --- 1. KONFIGURACJA I CSS ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .auth-container { max-width: 400px; margin: auto; padding: 20px; }
</style>
""", unsafe_allow_html=True)

# --- ŁADOWANIE KLUCZY Z CHMURY ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    SMSAPI_TOKEN = st.secrets["SMSAPI_TOKEN"]
except KeyError as e:
    st.error(f"❌ Błąd: Brak klucza {e} w Streamlit Secrets!")
    st.stop()

if not all([SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY]):
    st.error("❌ Błąd wartości! Jeden z kluczy jest pusty.")
    st.stop()

# Inicjalizacja klientów
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Błąd połączenia Supabase: {e}")
    st.stop()

# Używamy stabilnego modelu 1.5 Flash
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('models/gemini-flash-latest')
except Exception as e:
    st.error(f"❌ Błąd konfiguracji Gemini: {e}")
    st.stop()

try:
    from smsapi.client import SmsApiPlClient
    from smsapi.exception import SmsApiException
except ImportError:
    st.warning("Brak biblioteki smsapi-client.")

# --- 2. STAN SESJI ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'sms_preview' not in st.session_state: st.session_state['sms_preview'] = None
if 'preview_client' not in st.session_state: st.session_state['preview_client'] = None
if 'campaign_goal' not in st.session_state: st.session_state['campaign_goal'] = ""
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""

# --- 3. FUNKCJE POMOCNICZE ---

def usun_ogonki(tekst):
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state['user'] = response.user
        st.success("✅ Zalogowano!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Błąd logowania: {e}")

def register_user(email, password):
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user:
            st.session_state['user'] = response.user
            st.success("✅ Konto utworzone!")
            time.sleep(1)
            st.rerun()
    except Exception as e:
        st.error(f"Błąd rejestracji: {e}")

def logout_user():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- FUNKCJA WYSYŁAJĄCA SMS (NAPRAWIONA) ---
def send_campaign_sms(target_df, campaign_goal, generated_text, is_test_mode):
    
    sms_token = st.secrets["SMSAPI_TOKEN"]
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
    
    # Pobieramy imię wzorcowe bezpiecznie
    preview_name = st.session_state.get('preview_client')

    for index, row in target_df.iterrows():
        # Personalizacja - ZABEZPIECZONA PRZED BŁĘDEM
        final_text = generated_text
        
        # Tylko jeśli mamy imię wzorcowe i jest ono w tekście, to zamieniamy
        if preview_name and preview_name in generated_text:
             final_text = generated_text.replace(preview_name, row['imie'])
        
        clean_text = usun_ogonki(final_text)

        if is_test_mode:
            st.code(f"DO: {row['imie']} ({row['telefon']})\nTREŚĆ: {clean_text}", language='text')
            st.success(f"🧪 [TEST] Symulacja dla: {row['imie']}")
        else:
            try:
                client.sms.send(to=row['telefon'], message=clean_text)
                st.success(f"✅ Wysłano do: {row['imie']}")
            except SmsApiException as e:
                st.error(f"Błąd bramki SMS dla {row['imie']}: {e}")
            
        time.sleep(1)
        progress_bar.progress((index + 1) / len(target_df))
    
    st.balloons()
    st.success("🎉 Kampania zakończona!")


# --- 4. INTERFEJS ---

if not st.session_state['user']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("💅 Beauty SaaS")
        tab1, tab2 = st.tabs(["Logowanie", "Rejestracja"])
        with tab1:
            l_email = st.text_input("Email", key="l1")
            l_pass = st.text_input("Hasło", type="password", key="l2")
            if st.button("Zaloguj się", type="primary"): login_user(l_email, l_pass)
        with tab2:
            r_email = st.text_input("Email", key="r1")
            r_pass = st.text_input("Hasło", type="password", key="r2")
            if st.button("Załóż konto"): register_user(r_email, r_pass)
    st.stop()

# --- APLIKACJA ---
CURRENT_USER = st.session_state['user']
SALON_ID = CURRENT_USER.id 
USER_EMAIL = CURRENT_USER.email

with st.sidebar:
    st.write(f"Zalogowano: **{USER_EMAIL}**")
    if st.button("Wyloguj"): logout_user()
    st.divider()

# Funkcje DB wewnątrz, żeby widziały SALON_ID
def add_client(imie, telefon, zabieg, data):
    try:
        supabase.table("klientki").insert({
            "salon_id": SALON_ID, "imie": imie, "telefon": telefon,
            "ostatni_zabieg": zabieg, "data_wizyty": str(data)
        }).execute()
        return True
    except: return False

def get_clients():
    try:
        res = supabase.table("klientki").select("*").eq("salon_id", SALON_ID).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def delete_client(cid):
    try: supabase.table("klientki").delete().eq("id", cid).eq("salon_id", SALON_ID).execute()
    except: pass

st.title("Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

if page == "📂 Baza Klientek":
    st.header("Twoja Baza")
    with st.expander("➕ Dodaj klientkę"):
        c1, c2 = st.columns(2)
        imie = c1.text_input("Imię")
        tel = c1.text_input("Telefon (48...)")
        zabieg = c2.text_input("Zabieg", "Manicure")
        data = c2.date_input("Data")
        if st.button("Zapisz"):
            add_client(imie, tel, zabieg, data)
            st.rerun()

    df = get_clients()
    if not df.empty:
        st.dataframe(df[['imie', 'telefon', 'ostatni_zabieg']], use_container_width=True)
        opts = df.set_index('id')['imie'].to_dict()
        to_del = st.selectbox("Usuń:", options=opts.keys(), format_func=lambda x: opts[x])
        if st.button("Usuń wybraną"):
            delete_client(to_del)
            st.rerun()
    else:
        st.info("Baza pusta.")

elif page == "🤖 Automat SMS":
    st.header("Generator SMS AI")
    df = get_clients()
    
    if df.empty:
        st.warning("Baza pusta!")
    else:
        st.write("### ⚙️ Konfiguracja")
        salon_name = st.text_input("1. Nazwa salonu:", value=st.session_state['salon_name'])
        st.session_state['salon_name'] = salon_name

        campaign_goal = st.text_input("2. Cel Kampanii:", value=st.session_state['campaign_goal'])
        st.session_state['campaign_goal'] = campaign_goal 

        wybrane = st.multiselect("3. Odbiorcy:", df['imie'].tolist(), default=df['imie'].tolist())
        target_df = df[df['imie'].isin(wybrane)]
        
        if salon_name and not target_df.empty:
            sample_client = target_df.iloc[0]
            
            if st.button("🔍 1. Wygeneruj Podgląd", type="secondary"):
                prompt = f"""
                Jesteś recepcjonistką w salonie: {salon_name}.
                Napisz SMS do klientki {sample_client['imie']}.
                Cel: {campaign_goal}.
                NSTRUKCJE:
                
                Zacznij od imienia.
                Styl: Ciepły, miły, relacyjny (jak koleżanka do koleżanki, ale z szacunkiem).
                Użyj języka korzyści (np. "poczuj się piękna", "zadbaj o siebie").
                Podpisz się nazwą salonu.
                Pisz poprawną polszczyzną (używaj ą, ę - my to potem zmienimy)."""
              
                try:
                    res = model.generate_content(prompt)
                    if res.text:
                        clean = usun_ogonki(res.text.strip())
                        st.session_state['sms_preview'] = clean
                        st.session_state['preview_client'] = sample_client['imie']
                except Exception as e:
                    st.error(f"Błąd AI: {e}")
                st.rerun()

            if st.session_state['sms_preview']:
                st.subheader("Podgląd:")
                st.code(st.session_state['sms_preview'], language='text')
                st.warning(f"Wysyłka do {len(target_df)} osób.")
                
                mode = st.radio("Tryb:", ["🧪 Test", "💸 Produkcja (Płatny)"])
                is_test = (mode == "🧪 Test")
                
                if st.button("🚀 2. Wyślij", type="primary" if not is_test else "secondary"):
                    send_campaign_sms(target_df, campaign_goal, st.session_state['sms_preview'], is_test)
                    st.session_state['sms_preview'] = None




