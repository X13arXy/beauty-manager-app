import streamlit as st
import pandas as pd
import time

# IMPORTUJEMY NASZE MODUŁY
import database as db
import utils

# --- KONFIGURACJA ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")

# CSS dla przycisków
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# Import SMSAPI (opcjonalny)
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
        st.title("💅 Beauty Manager")
        tab1, tab2 = st.tabs(["Logowanie", "Rejestracja"])
        with tab1:
            e = st.text_input("Email", key="l1")
            p = st.text_input("Hasło", type="password", key="l2")
            if st.button("Zaloguj", type="primary"): db.login_user(e, p)
        with tab2:
            e = st.text_input("Email", key="r1")
            p = st.text_input("Hasło", type="password", key="r2")
            if st.button("Załóż konto"): db.register_user(e, p)
    st.stop()

# --- APLIKACJA WŁAŚCIWA ---
USER = st.session_state['user']
SALON_ID = USER.id

with st.sidebar:
    st.success(f"Zalogowano: {USER.email}")
    if st.button("Wyloguj"): db.logout_user()

st.title("Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Kampania SMS"])

# ========================================================
# ZAKŁADKA 1: BAZA (Z IMPORTEM)
# ========================================================
if page == "📂 Baza Klientek":
    st.header("Zarządzaj Bazą")
    
    # 1. IMPORT
    with st.expander("📥 Import z telefonu (VCF/Excel)"):
        f = st.file_uploader("Wybierz plik", type=['xlsx', 'csv', 'vcf'])
        if f:
            df_imp = None
            try:
                if f.name.endswith('.vcf'): df_imp = utils.parse_vcf(f.getvalue())
                elif f.name.endswith('.csv'): df_imp = pd.read_csv(f)
                else: df_imp = pd.read_excel(f)
                
                if df_imp is not None and not df_imp.empty:
                    # Szukanie kolumn
                    df_imp.columns = [c.lower() for c in df_imp.columns]
                    c_imie = next((c for c in df_imp.columns if 'imi' in c or 'name' in c), None)
                    c_tel = next((c for c in df_imp.columns if 'tel' in c or 'pho' in c), None)
                    
                    if c_imie and c_tel:
                        df_show = pd.DataFrame({
                            "Dodaj": True, "Imię": df_imp[c_imie], "Telefon": df_imp[c_tel], "Ostatni Zabieg": "Nieznany"
                        })
                        st.write("### Wybierz kogo dodać:")
                        edited = st.data_editor(df_show, hide_index=True, use_container_width=True, column_config={"Dodaj": st.column_config.CheckboxColumn("Importuj?", default=True)})
                        
                        to_add = edited[edited["Dodaj"] == True]
                        count = len(to_add)
                        
                        if st.button(f"✅ ZAPISZ {count} KONTAKTÓW"):
                            bar = st.progress(0.0)
                            ok = 0
                            for i, (idx, row) in enumerate(to_add.iterrows()):
                                s, m = db.add_client(SALON_ID, row["Imię"], row["Telefon"], row["Ostatni Zabieg"], None)
                                if s: ok += 1
                                bar.progress((i+1)/count)
                            st.success(f"Dodano {ok} osób!")
                            time.sleep(1)
                            st.rerun()
            except Exception as e:
                st.error(f"Błąd pliku: {e}")

    # 2. RĘCZNE
    with st.expander("➕ Dodaj ręcznie"):
        c1, c2 = st.columns(2)
        i = c1.text_input("Imię")
        t = c1.text_input("Telefon")
        z = c2.text_input("Zabieg", "Manicure")
        if st.button("Zapisz"):
            s, m = db.add_client(SALON_ID, i, t, z, None)
            if s: 
                st.success("Dodano!") 
                st.rerun()
            else: st.error(m)

    # 3. TABELA
    data = db.get_clients(SALON_ID)
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df[['imie', 'telefon', 'ostatni_zabieg']], use_container_width=True)
        d = df.set_index('id')['imie'].to_dict()
        delt = st.selectbox("Usuń:", options=d.keys(), format_func=lambda x: d[x])
        if st.button("Usuń"):
            db.delete_client(delt, SALON_ID)
            st.rerun()
    else:
        st.info("Baza pusta.")

# ========================================================
# ZAKŁADKA 2: KAMPANIA (PODGLĄD 1 SMS -> WYŚLIJ WSZYSTKIE)
# ========================================================
elif page == "🤖 Kampania SMS":
    st.header("Generator SMS")
    data = db.get_clients(SALON_ID)
    
    if not data:
        st.warning("Najpierw dodaj klientki.")
    else:
        df = pd.DataFrame(data)
        
        # 1. KONFIGURACJA
        st.subheader("1. Ustawienia")
        c1, c2 = st.columns(2)
        salon = c1.text_input("Nazwa Salonu", value=st.session_state.get('salon_name', 'Glow Studio'))
        st.session_state['salon_name'] = salon
        cel = c2.text_input("Cel (np. Promocja -20%)")
        
        odbiorcy = st.multiselect("Do kogo?", df['imie'].tolist(), default=df['imie'].tolist())
        target_df = df[df['imie'].isin(odbiorcy)]
        
        # 2. PRÓBKA (PODGLĄD 1 SMS)
        if st.button("👁️ Pokaż Próbkę (1 SMS)"):
            if not salon or not cel or target_df.empty:
                st.error("Uzupełnij dane!")
            else:
                sample = target_df.iloc[0]
                with st.spinner("AI tworzy przykładową wiadomość..."):
                    # Używamy funkcji z utils.py
                    msg = utils.generate_single_message(salon, cel, sample['imie'], sample['ostatni_zabieg'])
                    st.session_state['preview_msg'] = msg
        
        # 3. WIDOK I WYSYŁKA
        if st.session_state['preview_msg']:
            st.info("👇 Tak będzie brzmiał SMS (styl):")
            st.code(st.session_state['preview_msg'], language='text')
            st.warning(f"Pasuje? Kliknij poniżej, aby wysłać do wszystkich {len(target_df)} osób. AI stworzy unikalną treść dla każdej z nich.")
            
            st.write("---")
            mode = st.radio("Tryb:", ["🧪 Test (Za darmo)", "💸 Produkcja (Płatny SMSAPI)"])
            is_test = (mode == "🧪 Test (Za darmo)")
            
            if st.button(f"🚀 WYŚLIJ DO {len(target_df)} OSÓB", type="primary"):
                # Inicjalizacja SMSAPI (jeśli produkcja)
                client = None
                if not is_test:
                    token = st.secrets.get("SMSAPI_TOKEN", "")
                    if not token:
                        st.error("Brak tokenu SMSAPI w Secrets!")
                        st.stop()
                    try:
                        client = SmsApiPlClient(access_token=token)
                    except:
                        st.error("Błąd logowania SMSAPI")
                        st.stop()
                
               st.write("---")
                st.subheader("📨 Raport Wysyłki na Żywo:")
                
                # Pasek postępu
                bar = st.progress(0.0)
                
                # Kontener na logi (żeby pojawiały się jeden pod drugim)
                log_container = st.container()
                
                ok_count = 0
                
                # Pętla wysyłki
                for i, (idx, row) in enumerate(target_df.iterrows()):
                    
                    # Generujemy treść
                    msg = utils.generate_single_message(salon, cel, row['imie'], row['ostatni_zabieg'])
                    
                    # Wyświetlamy wynik na ekranie
                    with log_container:
                        if is_test_mode:
                            st.success(f"✅ [TEST] Wysłano do: **{row['imie']}** ({row['telefon']})")
                            st.code(msg, language='text')
                            ok_count += 1
                        else:
                            try:
                                client.sms.send(to=str(row['telefon']), message=msg)
                                st.success(f"✅ [PŁATNE] Wysłano do: **{row['imie']}**")
                                st.caption(f"Treść: {msg}")
                                ok_count += 1
                            except Exception as e:
                                st.error(f"❌ Błąd wysyłki do {row['imie']}: {e}")
                    
                    time.sleep(1.5) # Odpoczynek dla AI
                    bar.progress((i+1)/len(target_df))
                
                st.balloons()
                st.success(f"🎉 Zakończono! Wysłano pomyślnie: {ok_count} wiadomości.")
                st.session_state['preview_msg'] = None
