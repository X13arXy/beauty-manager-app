import streamlit as st
import pandas as pd
import google.generativeai as genai
import time
from supabase import create_client, Client

import database as db
import utils

# --- KONFIGURACJA ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .element-container { margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# Ładowanie kluczy
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    SMSAPI_TOKEN = st.secrets.get("SMSAPI_TOKEN", "")
except KeyError as e:
    st.error(f"❌ Brak klucza {e} w Secrets!")
    st.stop()

# Inicjalizacja
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Błąd Supabase: {e}")
    st.stop()

try:
    from smsapi.client import SmsApiPlClient
except ImportError:
    pass

# Stan sesji
if 'user' not in st.session_state: st.session_state['user'] = None
if 'preview_msg' not in st.session_state: st.session_state['preview_msg'] = None
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""

# --- LOGOWANIE ---
if not st.session_state['user']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("💅 Beauty SaaS")
        t1, t2 = st.tabs(["Logowanie", "Rejestracja"])
        with t1:
            e = st.text_input("Email", key="l1")
            p = st.text_input("Hasło", type="password", key="l2")
            if st.button("Zaloguj", type="primary"): db.login_user(e, p)
        with t2:
            e = st.text_input("Email", key="r1")
            p = st.text_input("Hasło", type="password", key="r2")
            if st.button("Załóż konto"): db.register_user(e, p)
    st.stop()

# --- APLIKACJA ---
USER = st.session_state['user']
SALON_ID = USER.id 
USER_EMAIL = USER.email

with st.sidebar:
    st.write(f"Zalogowano: {USER_EMAIL}")
    if st.button("Wyloguj"): db.logout_user()
    st.divider()

st.title("Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

# 📂 BAZA KLIENTEK
if page == "📂 Baza Klientek":
    st.header("Baza Klientek")
    with st.expander("📥 Import z telefonu"):
        f = st.file_uploader("Plik", type=['xlsx','csv','vcf'])
        if f:
            try:
                df = None
                if f.name.endswith('.vcf'): df = utils.parse_vcf(f.getvalue())
                elif f.name.endswith('.csv'): df = pd.read_csv(f)
                else: df = pd.read_excel(f)
                
                if df is not None and not df.empty:
                    df.columns = [c.lower() for c in df.columns]
                    ci = next((c for c in df.columns if 'imi' in c or 'name' in c), None)
                    ct = next((c for c in df.columns if 'tel' in c or 'num' in c), None)
                    if ci and ct:
                        sh = pd.DataFrame({"Dodaj": True, "Imię": df[ci], "Telefon": df[ct], "Ostatni Zabieg": "Nieznany"})
                        ed = st.data_editor(sh, hide_index=True, use_container_width=True, column_config={"Dodaj": st.column_config.CheckboxColumn("Import?", default=True)})
                        to_add = ed[ed["Dodaj"]==True]
                        cnt = len(to_add)
                        if st.button(f"✅ ZAPISZ {cnt}"):
                            bar = st.progress(0.0)
                            ok = 0
                            for i, (idx, r) in enumerate(to_add.iterrows()):
                                s, m = db.add_client(SALON_ID, r["Imię"], r["Telefon"], r["Ostatni Zabieg"], None)
                                if s: ok += 1
                                bar.progress(min((i+1)/cnt, 1.0))
                            st.success(f"Zapisano {ok}!")
                            time.sleep(1)
                            st.rerun()
            except: st.error("Błąd pliku")

    data = db.get_clients(SALON_ID)
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df[['imie','telefon','ostatni_zabieg']], use_container_width=True)
        d = df.set_index('id')['imie'].to_dict()
        dd = st.selectbox("Usuń:", options=d.keys(), format_func=lambda x: d[x])
        if st.button("Usuń"): db.delete_client(dd, SALON_ID); st.rerun()
    else: st.info("Pusto.")

# 🤖 AUTOMAT SMS
elif page == "🤖 Automat SMS":
    st.header("Kampania SMS")
    data = db.get_clients(SALON_ID)
    
    if not data:
        st.warning("Brak klientek.")
    else:
        df = pd.DataFrame(data)
        st.write("### Konfiguracja")
        salon = st.text_input("Nazwa Salonu:", value=st.session_state.get('salon_name', ''))
        st.session_state['salon_name'] = salon
        cel = st.text_input("Cel (np. Promocja Noworoczna -20%):")
        
        wyb = st.multiselect("Do kogo?", df['imie'].tolist(), default=df['imie'].tolist())
        target = df[df['imie'].isin(wyb)]
        
        # --- PRÓBKA (JEDEN SMS) ---
        if st.button("👁️ Sprawdź Próbkę"):
            if not salon or not cel or target.empty:
                st.error("Uzupełnij dane!")
            else:
                sample = target.iloc[0]
                with st.spinner("AI myśli..."):
                    # Generujemy próbkę
                    msg = utils.generate_single_message(salon, cel, sample['imie'], sample['ostatni_zabieg'])
                    st.session_state['preview_msg'] = msg
        
        # --- WIDOK I WYSYŁKA ---
        if st.session_state['preview_msg']:
            st.info("👇 Przykładowy SMS (Styl i Treść):")
            st.code(st.session_state['preview_msg'], language='text')
            
            st.write("---")
            mode = st.radio("Tryb:", ["🧪 Test (Symulacja)", "💸 Produkcja (Płatny SMSAPI)"])
            is_test = (mode == "🧪 Test (Symulacja)")
            
            if st.button(f"🚀 WYŚLIJ DO {len(target)} OSÓB", type="primary"):
                # Inicjalizacja klienta
                client = None
                if not is_test:
                    token = st.secrets.get("SMSAPI_TOKEN", "")
                    if not token:
                        st.error("Brak tokenu SMSAPI!")
                        st.stop()
                    try:
                        client = SmsApiPlClient(access_token=token)
                    except:
                        st.error("Błąd SMSAPI")
                        st.stop()
                
                st.subheader("📨 Raport na żywo:")
                bar = st.progress(0.0)
                log_container = st.container()
                report_data = []
                
                total = len(target)
                for i, (idx, row) in enumerate(target.iterrows()):
                    
                    # Generowanie (MÓZG)
                    msg = utils.generate_single_message(salon, cel, row['imie'], row['ostatni_zabieg'])
                    
                    # Wysyłka
                    status = "OK"
                    with log_container:
                        if is_test:
                            st.success(f"✅ [TEST] {row['imie']}")
                            st.caption(msg)
                        else:
                            try:
                                client.sms.send(to=str(row['telefon']), message=msg)
                                st.success(f"✅ [WYSŁANO] {row['imie']}")
                                st.caption(msg)
                            except Exception as e:
                                st.error(f"❌ Błąd: {e}")
                                status = "BŁĄD"
                    
                    # Dodajemy do tabeli końcowej
                    report_data.append({"Imię": row['imie'], "Treść": msg, "Status": status})
                    
                    # WAŻNE: Opóźnienie 2.5s żeby AI zdążyło pomyśleć nad odmianą imienia
                    time.sleep(2.5) 
                    bar.progress((i+1)/total)
                
                st.balloons()
                st.success("Zakończono!")
                
                # Tabela Raportu Końcowego
                if report_data:
                    st.write("---")
                    st.write("### 📜 Pełny Raport:")
                    st.dataframe(pd.DataFrame(report_data), use_container_width=True)
                
                st.session_state['preview_msg'] = None
