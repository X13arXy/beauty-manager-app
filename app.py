import streamlit as st
import pandas as pd
import time

# IMPORTUJEMY NASZE MODUŁY (To jest kluczowe)
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

# Import SMSAPI (opcjonalny, tylko do obsługi wyjątków tutaj)
try:
    from smsapi.client import SmsApiPlClient
except ImportError:
    pass

# --- STAN SESJI ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'preview_msg' not in st.session_state: st.session_state['preview_msg'] = None
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""

# --- EKRAN LOGOWANIA ---
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

# --- APLIKACJA WŁAŚCIWA ---
USER = st.session_state['user']
SALON_ID = USER.id
USER_EMAIL = USER.email

with st.sidebar:
    st.write(f"Zalogowano: {USER_EMAIL}")
    if st.button("Wyloguj"): db.logout_user()
    st.divider()

st.title("Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

# ========================================================
# 📂 ZAKŁADKA 1: BAZA KLIENTEK (KORZYSTA Z UTILS I DB)
# ========================================================
if page == "📂 Baza Klientek":
    st.header("Baza Klientek")
    
    # IMPORT Z TELEFONU
    with st.expander("📥 Import z telefonu"):
        f = st.file_uploader("Plik (VCF/Excel)", type=['xlsx','csv','vcf'])
        if f:
            try:
                df = None
                # Tu korzystamy z utils.py do czytania plików
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
                                # Tu korzystamy z database.py do zapisu
                                s, m = db.add_client(SALON_ID, r["Imię"], r["Telefon"], r["Ostatni Zabieg"], None)
                                if s: ok += 1
                                bar.progress(min((i+1)/cnt, 1.0))
                            st.success(f"Zapisano {ok}!")
                            time.sleep(1)
                            st.rerun()
            except: st.error("Błąd pliku")

    # TABELA
    data = db.get_clients(SALON_ID)
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df[['imie','telefon','ostatni_zabieg']], use_container_width=True)
        d = df.set_index('id')['imie'].to_dict()
        dd = st.selectbox("Usuń:", options=d.keys(), format_func=lambda x: d[x])
        if st.button("Usuń"): db.delete_client(dd, SALON_ID); st.rerun()
    else: st.info("Pusto.")

# ========================================================
# 🤖 ZAKŁADKA 2: AUTOMAT SMS (LIVE RAPORT + UNIKALNE TREŚCI)
# ========================================================
elif page == "🤖 Automat SMS":
    st.header("Generator SMS AI (Personalizowany)")
    data = db.get_clients(SALON_ID)
    
    if not data:
        st.warning("Brak klientek.")
    else:
        df = pd.DataFrame(data)
        
        c1, c2 = st.columns(2)
        salon = c1.text_input("Nazwa Salonu:", value=st.session_state.get('salon_name', 'Glow Studio'))
        st.session_state['salon_name'] = salon
        cel = c2.text_input("Co chcesz przekazać? (np. Zaproszenie na kawę):")
        
        wyb = st.multiselect("Do kogo?", df['imie'].tolist(), default=df['imie'].tolist())
        target = df[df['imie'].isin(wyb)]
        
        # --- KROK 1: PRÓBKA ---
        if st.button("👁️ Pokaż Próbkę (Styl)"):
            if not salon or not cel or target.empty:
                st.error("Uzupełnij dane!")
            else:
                sample = target.iloc[0]
                with st.spinner("AI wymyśla coś miłego..."):
                    # Korzystamy z utils.py do generowania
                    msg = utils.generate_single_message(salon, cel, sample['imie'], sample['ostatni_zabieg'])
                    st.session_state['preview_msg'] = msg
        
        # --- KROK 2: WYSYŁKA Z PODGLĄDEM LIVE ---
        if st.session_state['preview_msg']:
            st.info("👇 Przykładowy styl wiadomości:")
            st.code(st.session_state['preview_msg'], language='text')
            st.caption("AI wygeneruje unikalną, ciepłą wiadomość dla każdej osoby z listy, zachowując ten styl.")
            
            st.write("---")
            mode = st.radio("Tryb:", ["🧪 Test (Symulacja)", "💸 Produkcja (Płatny SMSAPI)"])
            is_test = (mode == "🧪 Test (Symulacja)")
            
            if st.button(f"🚀 WYŚLIJ DO {len(target)} OSÓB", type="primary"):
                
                # Inicjalizacja SMSAPI (tylko w app.py, bo tu jest potrzebna)
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
                
                st.subheader("📨 Raport wysyłki na żywo:")
                bar = st.progress(0.0)
                
                # Kontener na logi - tu będą wpadać wiadomości
                log_box = st.container()
                
                for i, (idx, row) in enumerate(target.iterrows()):
                    
                    # 1. GENEROWANIE (Tu wołamy MÓZG z utils.py)
                    # Dzięki temu każda wiadomość jest inna!
                    with st.spinner(f"AI pisze do: {row['imie']}..."):
                        msg = utils.generate_single_message(salon, cel, row['imie'], row['ostatni_zabieg'])
                    
                    # 2. WYSYŁKA I WYŚWIETLENIE
                    with log_box:
                        if is_test:
                            st.success(f"✅ [TEST] Do: **{row['imie']}**")
                            st.code(msg, language='text')
                        else:
                            try:
                                client.sms.send(to=str(row['telefon']), message=msg)
                                st.success(f"✅ [WYSŁANO] Do: **{row['imie']}**")
                                st.code(msg, language='text')
                            except Exception as e:
                                st.error(f"❌ Błąd: {e}")
                    
                    # Odpoczynek dla AI (żeby nie było error 429)
                    time.sleep(3) 
                    bar.progress((i+1)/len(target))
                
                st.balloons()
                st.success("Zakończono!")
                st.session_state['preview_msg'] = None
