import streamlit as st
import pandas as pd
import time
from supabase import create_client, Client

# Import naszych modułów
import database as db
import utils

# --- KONFIGURACJA ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .element-container { margin-bottom: 0.5rem; }
    /* Ładniejszy wygląd logów */
    .stCode { font-family: 'Courier New', monospace; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# Import SMSAPI
try:
    from smsapi.client import SmsApiPlClient
except ImportError:
    pass

# --- STAN SESJI ---
if 'user' not in st.session_state: st.session_state['user'] = None
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

# 📂 BAZA KLIENTEK (IMPORT)
if page == "📂 Baza Klientek":
    st.header("Baza Klientek")
    with st.expander("📥 Import z telefonu"):
        f = st.file_uploader("Plik (VCF/Excel)", type=['xlsx','csv','vcf'])
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

# 🤖 AUTOMAT SMS (RELACYJNY)
elif page == "🤖 Automat SMS":
    st.header("Generator SMS AI (Personalizowany)")
    data = db.get_clients(SALON_ID)
    
    if not data:
        st.warning("Brak klientek.")
    else:
        df = pd.DataFrame(data)
        
        c1, c2 = st.columns(2)
        salon = c1.text_input("Nazwa Salonu:", value=st.session_state.get('salon_name', ''))
        st.session_state['salon_name'] = salon
        cel = c2.text_input("Co chcesz przekazać? (np. Zaproszenie na kawę):")
        
        wyb = st.multiselect("Do kogo?", df['imie'].tolist(), default=df['imie'].tolist())
        target = df[df['imie'].isin(wyb)]
        
        if salon and cel and not target.empty:
            st.info(f"Wybrano {len(target)} osób. AI wygeneruje UNIKALNĄ treść dla każdej z nich.")
            
            mode = st.radio("Tryb:", ["🧪 Test (Symulacja)", "💸 Produkcja (Płatny SMSAPI)"])
            is_test = (mode == "🧪 Test (Symulacja)")
            
            if st.button("🚀 GENERUJ I WYŚLIJ (LIVE)", type="primary"):
                
                # SMSAPI
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
                
                st.write("---")
                st.subheader("📨 Podgląd wysyłki na żywo:")
                
                bar = st.progress(0.0)
                log_box = st.container() # Tu będą wpadać wiadomości
                
                for i, (idx, row) in enumerate(target.iterrows()):
                    
                    # 1. GENEROWANIE (Tu dzieje się magia różnorodności)
                    with st.spinner(f"AI pisze do: {row['imie']}..."):
                        msg = utils.generate_single_message(salon, cel, row['imie'], row['ostatni_zabieg'])
                    
                    # 2. WYSYŁKA I WYŚWIETLENIE
                    with log_box:
                        with st.chat_message("assistant"):
                            st.write(f"**Do: {row['imie']}** ({row['telefon']})")
                            st.code(msg, language='text')
                            
                            if is_test:
                                st.caption("✅ Symulacja OK")
                            else:
                                try:
                                    client.sms.send(to=str(row['telefon']), message=msg)
                                    st.caption("✅ Wysłano SMS")
                                except Exception as e:
                                    st.error(f"Błąd wysyłki: {e}")
                    
                    # Czekamy, żeby AI mogło pomyśleć przy następnym i żeby Google nie zablokowało
                    time.sleep(3) 
                    bar.progress((i+1)/len(target))
                
                st.balloons()
                st.success("Zakończono!")



