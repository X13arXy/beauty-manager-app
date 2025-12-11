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

# Inicjalizacja klientów
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Błąd połączenia Supabase: {e}")
    st.stop()

# AI
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
    pass

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
    preview_name = st.session_state.get('preview_client')

    for index, row in target_df.iterrows():
        final_text = generated_text
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
            except Exception as e:
                st.error(f"Błąd bramki SMS dla {row['imie']}: {e}")
            
        time.sleep(1)
       # Oblicz postęp
        progress_value = (index + 1) / len(target_df)

        # Zabezpiecz, aby nie przekroczyło 1.0
        progress_value = min(progress_value, 1.0)

        # Aktualizuj pasek
        progress_bar.progress(progress_value)
    
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

# ========================================================
# 📂 ZAKŁADKA 1: BAZA KLIENTEK (Z OBSŁUGĄ VCF Z TELEFONU!)
# ========================================================
if page == "📂 Baza Klientek":
    st.header("Twoja Baza")

    # --- FUNKCJA DO CZYTANIA PLIKÓW VCF (Z TELEFONU) ---
    def parse_vcf(file_content):
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

    # --- SEKCJA IMPORTU ---
    with st.expander("📥 IMPORT Z TELEFONU (Wgraj plik)", expanded=False):
        st.info("💡 Tu wgraj plik 'Kontakty.vcf' wysłany z telefonu lub Excela.")
        
        uploaded_file = st.file_uploader("Wybierz plik", type=['xlsx', 'csv', 'vcf'])
        
        if uploaded_file:
            try:
                df_import = None
                
                # 1. ROZPOZNAWANIE FORMATU
                if uploaded_file.name.endswith('.vcf'):
                    df_import = parse_vcf(uploaded_file.getvalue())
                    if df_import.empty:
                        st.warning("Plik VCF pusty lub błędny format.")
                
                elif uploaded_file.name.endswith('.csv'):
                    df_import = pd.read_csv(uploaded_file)
                else:
                    df_import = pd.read_excel(uploaded_file)
                
                if df_import is not None and not df_import.empty:
                    # Standaryzacja kolumn
                    df_import.columns = [c.lower() for c in df_import.columns]
                    
                    col_imie = next((c for c in df_import.columns if 'imi' in c or 'name' in c or 'nazw' in c), None)
                    col_tel = next((c for c in df_import.columns if 'tel' in c or 'num' in c or 'pho' in c), None)

                    if col_imie and col_tel:
                        # Tabela podglądu z checkboxami
                        df_to_show = pd.DataFrame({
                            "Dodaj": True, 
                            "Imię": df_import[col_imie],
                            "Telefon": df_import[col_tel],
                            "Ostatni Zabieg": "Nieznany"
                        })

                        st.markdown("### 🕵️‍♀️ Odznacz osoby prywatne:")
                        
                        edited_df = st.data_editor(
                            df_to_show,
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "Dodaj": st.column_config.CheckboxColumn(
                                    "Importuj?", default=True
                                )
                            }
                        )
                        
                        # Zapisywanie
                        to_import = edited_df[edited_df["Dodaj"] == True]
                        count = len(to_import)
                        
                        if st.button(f"✅ ZAPISZ {count} KONTAKTÓW"):
                            if count > 0:
                                progress = st.progress(0)
                                added = 0
                                for idx, row in to_import.iterrows():
                                    add_client(
                                        str(row["Imię"]), str(row["Telefon"]), 
                                        str(row["Ostatni Zabieg"]), "" 
                                    )
                                    added += 1
                                    progress.progress(added / count)
                                
                                st.success(f"Sukces! Dodano {added} klientek.")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.warning("Nikogo nie zaznaczono!")
                    else:
                        st.error("Nie znaleziono kolumn Imię/Telefon.")
            
            except Exception as e:
                st.error(f"Błąd pliku: {e}")

    # --- RĘCZNE DODAWANIE ---
    with st.expander("➕ Dodaj pojedynczo (Ręcznie)"):
        c1, c2 = st.columns(2)
        imie = c1.text_input("Imię")
        tel = c1.text_input("Telefon (48...)")
        zabieg = c2.text_input("Zabieg", "Manicure")
        data = c2.date_input("Data")
        if st.button("Zapisz ręcznie"):
            add_client(imie, tel, zabieg, data)
            st.rerun()

    # --- LISTA KLIENTEK ---
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

# ========================================================
# 🤖 ZAKŁADKA 2: AUTOMAT SMS (BEZ ZMIAN)
# ========================================================
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
                INSTRUKCJE:
                Zacznij od imienia.
                Styl: Ciepły, miły, relacyjny.
                Użyj języka korzyści.
                Podpisz się nazwą salonu.
                Pisz poprawną polszczyzną (używaj ą, ę - my to potem zmienimy).
                LIMIT ZNAKÓW TO 160.
                Odmieniaj imiona.
                """
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


