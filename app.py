import streamlit as st
import pandas as pd
import google.generativeai as genai
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

# --- ŁADOWANIE KLUCZY ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    SMSAPI_TOKEN = st.secrets.get("SMSAPI_TOKEN", "")
except KeyError as e:
    st.error(f"❌ Błąd: Brak klucza {e} w Streamlit Secrets!")
    st.stop()

# Inicjalizacja
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Błąd połączenia Supabase: {e}")
    st.stop()

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
except Exception as e:
    st.error(f"❌ Błąd konfiguracji Gemini: {e}")
    st.stop()

try:
    from smsapi.client import SmsApiPlClient
    from smsapi.exception import SmsApiException
except ImportError:
    pass

# --- 2. STAN SESJI ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'sms_preview' not in st.session_state: st.session_state['sms_preview'] = None
if 'preview_client' not in st.session_state: st.session_state['preview_client'] = None
if 'campaign_goal' not in st.session_state: st.session_state['campaign_goal'] = ""
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""

# --- 3. ZŁOTA ZASADA: FUNKCJE TECHNICZNE (PYTHON) ---

def usun_ogonki(tekst):
    """Techniczne czyszczenie znaków"""
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

def process_message(raw_text):
    """
    To jest Twój 'Redaktor Techniczny'.
    1. Usuwa ogonki.
    2. Pilnuje limitu 160 znaków (jeśli AI przesadzi).
    """
    # 1. Usuwamy ogonki
    clean_text = usun_ogonki(raw_text)
    
    # 2. Sprawdzamy długość
    if len(clean_text) <= 160:
        return clean_text
    else:
        # Jeśli za długie -> przytnij, ale nie w połowie słowa!
        # Ucinamy do 157 znaków i dodajemy "..."
        return clean_text[:157] + "..."

def parse_vcf(file_content):
    """Import kontaktów z telefonu"""
    try:
        content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        content = file_content.decode("latin-1")
        
    contacts = []
    current_contact = {}
    
    for line in content.splitlines():
        if line.startswith("BEGIN:VCARD"):
            current_contact = {}
        elif line.startswith("FN:") or line.startswith("N:"): 
            if "Imię" not in current_contact:
                parts = line.split(":", 1)[1]
                current_contact["Imię"] = parts.replace(";", " ").strip()
        elif line.startswith("TEL"): 
            if "Telefon" not in current_contact: 
                number = line.split(":", 1)[1]
                clean_number = ''.join(filter(str.isdigit, number))
                if len(clean_number) > 9 and clean_number.startswith("48"):
                    clean_number = clean_number 
                elif len(clean_number) == 9:
                    clean_number = "48" + clean_number 
                current_contact["Telefon"] = clean_number
        elif line.startswith("END:VCARD"):
            if "Imię" in current_contact and "Telefon" in current_contact:
                current_contact["Ostatni Zabieg"] = "Nieznany"
                contacts.append(current_contact)
    
    return pd.DataFrame(contacts)

# --- FUNKCJE LOGOWANIA ---
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

# --- INTELIGENTNA KAMPANIA SMS ---
def send_campaign_smart(target_df, campaign_goal, salon_name, is_test_mode):
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
    
    # Wyłączenie filtrów (AI ma być kreatywne)
    safety = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    count = len(target_df)
    
    for i, (index, row) in enumerate(target_df.iterrows()):
        
        # 1. AI: KREATYWNOŚĆ (Pisze ładnie po polsku)
        prompt = f"""
        Jesteś recepcjonistką w salonie: {salon_name}.
        Napisz SMS do klientki: {row['imie']}.
        Ostatni zabieg: {row['ostatni_zabieg']}.
        Cel: {campaign_goal}.

        WYTYCZNE DLA AI:
        1. Użyj zwrotu grzecznościowego z imieniem w wołaczu (np. "Cześć Kasiu", "Dzień dobry Aniu").
        2. Styl: Naturalny, miły, zachęcający.
        3. Pisz POPRAWNĄ POLSZCZYZNĄ (używaj ą, ę, ś, ć - nie martw się kodowaniem, my to naprawimy).
        4. Podpisz się: {salon_name}.
        5. Staraj się zmieścić w około 150 znakach.
        """
        
        try:
            res = model.generate_content(prompt, safety_settings=safety)
            raw_ai_text = res.text.strip()
            
            # 2. PYTHON: TECHNIKA (Czyści i pilnuje limitu)
            final_sms = process_message(raw_ai_text)
            
        except:
            # Awaryjny tekst (gdyby AI padło)
            final_sms = f"Czesc {row['imie']}! Zapraszamy do {salon_name}."

        # 3. WYSYŁKA
        if is_test_mode:
            st.code(f"DO: {row['imie']} ({row['telefon']})\nTREŚĆ: {final_sms}", language='text')
            st.success(f"🧪 [TEST] Symulacja")
        else:
            try:
                client.sms.send(to=str(row['telefon']), message=final_sms)
                st.toast(f"✅ Wysłano do: {row['imie']}")
            except Exception as e:
                st.error(f"Błąd bramki: {e}")
            
        time.sleep(1.5)
        progress_bar.progress((i + 1) / count)
    
    st.balloons()
    st.success("🎉 Kampania zakończona!")

# --- 4. EKRAN LOGOWANIA ---

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

# --- 5. APLIKACJA WŁAŚCIWA ---
CURRENT_USER = st.session_state['user']
SALON_ID = CURRENT_USER.id 
USER_EMAIL = CURRENT_USER.email

with st.sidebar:
    st.write(f"Zalogowano: **{USER_EMAIL}**")
    if st.button("Wyloguj"): logout_user()
    st.divider()

# Funkcje DB
def add_client(imie, telefon, zabieg, data):
    clean_tel = ''.join(filter(str.isdigit, str(telefon)))
    data_val = str(data) if data and str(data).strip() != "" else None
    try:
        supabase.table("klientki").insert({
            "salon_id": SALON_ID, "imie": str(imie), "telefon": clean_tel,
            "ostatni_zabieg": str(zabieg), "data_wizyty": data_val
        }).execute()
        return True, ""
    except Exception as e:
        return False, str(e)

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

    with st.expander("📥 IMPORT Z TELEFONU (Wgraj plik)", expanded=False):
        uploaded_file = st.file_uploader("Wybierz plik", type=['xlsx', 'csv', 'vcf'])
        
        if uploaded_file:
            try:
                df_import = None
                if uploaded_file.name.endswith('.vcf'):
                    df_import = parse_vcf(uploaded_file.getvalue())
                elif uploaded_file.name.endswith('.csv'):
                    df_import = pd.read_csv(uploaded_file)
                else:
                    df_import = pd.read_excel(uploaded_file)
                
                if df_import is not None and not df_import.empty:
                    df_import.columns = [c.lower() for c in df_import.columns]
                    col_imie = next((c for c in df_import.columns if 'imi' in c or 'name' in c or 'nazw' in c), None)
                    col_tel = next((c for c in df_import.columns if 'tel' in c or 'num' in c or 'pho' in c), None)

                    if col_imie and col_tel:
                        df_to_show = pd.DataFrame({
                            "Dodaj": True, 
                            "Imię": df_import[col_imie], 
                            "Telefon": df_import[col_tel], 
                            "Ostatni Zabieg": "Nieznany"
                        })
                        st.markdown("### 🕵️‍♀️ Wybierz kogo dodać:")
                        edited_df = st.data_editor(
                            df_to_show,
                            hide_index=True,
                            use_container_width=True,
                            column_config={"Dodaj": st.column_config.CheckboxColumn("Importuj?", default=True)}
                        )
                        
                        to_import = edited_df[edited_df["Dodaj"] == True]
                        count = len(to_import)
                        
                        if st.button(f"✅ ZAPISZ {count} KONTAKTÓW"):
                            if count > 0:
                                progress = st.progress(0.0)
                                added_real = 0
                                errors = []
                                
                                for i, (index, row) in enumerate(to_import.iterrows()):
                                    sukces, msg = add_client(str(row["Imię"]), str(row["Telefon"]), str(row["Ostatni Zabieg"]), None)
                                    if sukces: added_real += 1
                                    else: errors.append(f"{row['Imię']}: {msg}")
                                    
                                    current_prog = (i + 1) / count
                                    if current_prog > 1.0: current_prog = 1.0
                                    progress.progress(current_prog)
                                
                                if added_real > 0:
                                    st.success(f"✅ Sukces! Dodano: {added_real} osób.")
                                    time.sleep(1.5)
                                    st.rerun()
                                if errors:
                                    st.error("Błędy zapisu:")
                                    with st.expander("Szczegóły"):
                                        for e in errors: st.write(e)
                            else:
                                st.warning("Nikogo nie zaznaczono!")
                    else:
                        st.error("Nie znaleziono kolumn Imię/Telefon.")
            except Exception as e:
                st.error(f"Błąd pliku: {e}")

    with st.expander("➕ Dodaj pojedynczo"):
        c1, c2 = st.columns(2)
        imie = c1.text_input("Imię")
        tel = c1.text_input("Telefon (48...)")
        zabieg = c2.text_input("Zabieg", "Manicure")
        data = c2.date_input("Data")
        if st.button("Zapisz ręcznie"):
            sukces, msg = add_client(imie, tel, zabieg, data)
            if sukces: 
                st.success("Dodano!")
                st.rerun()
            else: st.error(f"Błąd: {msg}")

    df = get_clients()
    if not df.empty:
        st.dataframe(df[['imie', 'telefon', 'ostatni_zabieg']], use_container_width=True)
        opts = df.set_index('id')['imie'].to_dict()
        to_del = st.selectbox("Usuń klientkę:", options=opts.keys(), format_func=lambda x: opts[x])
        if st.button("Usuń wybraną"):
            delete_client(to_del)
            st.rerun()
    else:
        st.info("Baza pusta. Użyj importu powyżej!")

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
            
            st.info(f"Odbiorcy: {len(target_df)} osób. AI napisze indywidualną wiadomość dla każdej.")
            
            st.write("---")
            mode = st.radio("Wybierz tryb:", ["🧪 Tryb Testowy (Symulacja)", "💸 Tryb Produkcyjny (Płatny)"])
            is_test = (mode == "🧪 Tryb Testowy (Symulacja)")
            
            btn_text = "🚀 URUCHOM KAMPANIĘ" if not is_test else "🧪 URUCHOM SYMULACJĘ"
            
            if st.button(btn_text, type="primary"):
                send_campaign_smart(target_df, campaign_goal, salon_name, is_test)
