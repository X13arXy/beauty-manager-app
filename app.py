import streamlit as st
import pandas as pd
import time

# IMPORTY NASZYCH MODUŁÓW
import database as db
import services as srv

# --- KONFIGURACJA UI ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .auth-container { max-width: 400px; margin: auto; }
</style>
""", unsafe_allow_html=True)

# --- STAN SESJI (SESSION STATE) ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'sms_preview' not in st.session_state: st.session_state['sms_preview'] = None
if 'preview_client' not in st.session_state: st.session_state['preview_client'] = None
if 'campaign_goal' not in st.session_state: st.session_state['campaign_goal'] = ""
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""

# ========================================================
# 1. EKRAN LOGOWANIA
# ========================================================

if not st.session_state['user']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("💅 Beauty SaaS")
        tab1, tab2, tab3 = st.tabs(["Logowanie", "Rejestracja", "Reset Hasła"])
        
        # --- LOGOWANIE ---
        with tab1:
            l_email = st.text_input("Email", key="l1")
            l_pass = st.text_input("Hasło", type="password", key="l2")
            if st.button("Zaloguj się", type="primary"):
                user = db.login_user(l_email, l_pass)
                if user:
                    st.session_state['user'] = user
                    saved_name = db.get_salon_name(user.id)
                    st.session_state['salon_name'] = saved_name
                    st.success("✅ Zalogowano!")
                    st.rerun()
        
        # --- REJESTRACJA ---
        with tab2:
            r_email = st.text_input("Email", key="r1")
            r_pass = st.text_input("Hasło", type="password", key="r2")
            
            # MUST HAVE: Zgody prawne
            zgoda = st.checkbox("Akceptuję Regulamin i Politykę Prywatności *")
            
            if st.button("Załóż konto"):
                if not zgoda:
                    st.warning("Musisz zaakceptować regulamin!")
                else:
                    user = db.register_user(r_email, r_pass)
                    if user:
                        st.session_state['user'] = user
                        st.success("✅ Konto utworzone! Sprawdź email w celu weryfikacji.")
                        time.sleep(2)
                        st.rerun()

        # --- MUST HAVE: RESET HASŁA ---
        with tab3:
            st.write("Zapomniałeś hasła? Podaj email, wyślemy link.")
            reset_email = st.text_input("Twój Email", key="res1")
            if st.button("Wyślij link resetujący"):
                if reset_email:
                    ok, msg = db.reset_password_email(reset_email)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(f"Błąd: {msg}")
                else:
                    st.warning("Podaj email.")

    st.stop()

# ========================================================
# 2. APLIKACJA GŁÓWNA (PO ZALOGOWANIU)
# ========================================================
CURRENT_USER = st.session_state['user']
SALON_ID = CURRENT_USER.id 

with st.sidebar:
    st.write(f"👤 **{CURRENT_USER.email}**")
    if st.button("Wyloguj"):
        db.logout_user()
        st.session_state['user'] = None
        st.rerun()
    st.divider()

st.title("Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

# --- ZAKŁADKA: BAZA KLIENTEK ---
if page == "📂 Baza Klientek":
    st.header("Twoja Baza")

    # Import
    with st.expander("📥 IMPORT (VCF/Excel)", expanded=False):
        uploaded_file = st.file_uploader("Wgraj plik", type=['xlsx', 'csv', 'vcf'])
        
        if uploaded_file:
            df_import = None
            # Rozpoznawanie pliku
            if uploaded_file.name.endswith('.vcf'):
                df_import = srv.parse_vcf(uploaded_file.getvalue())
            elif uploaded_file.name.endswith('.csv'):
                df_import = pd.read_csv(uploaded_file)
            else:
                df_import = pd.read_excel(uploaded_file)
            
            if df_import is not None and not df_import.empty:
                # Standaryzacja nazw kolumn
                df_import.columns = [c.lower() for c in df_import.columns]
                
                # Szukanie odpowiednich kolumn
                col_imie = next((c for c in df_import.columns if 'imi' in c or 'name' in c), None)
                col_tel = next((c for c in df_import.columns if 'tel' in c or 'num' in c), None)

                if col_imie and col_tel:
                    # Przygotowanie tabeli do edycji
                    df_to_show = pd.DataFrame({
                        "Dodaj": True, 
                        "Imię": df_import[col_imie],
                        "Telefon": df_import[col_tel],
                        "Zabieg": "Nieznany"
                    })
                    
                    st.write("Edytuj listę przed importem:")
                    edited_df = st.data_editor(df_to_show, hide_index=True, use_container_width=True)
                    
                    # --- TUTAJ BYŁ BŁĄD WCIĘCIA ---
                    # Ten przycisk musi być równo z linią 'edited_df =' powyżej
                    if st.button(f"💾 Zapisz zaznaczone"):
                        to_import = edited_df[edited_df["Dodaj"] == True]
                        
                        if to_import.empty:
                            st.warning("Nie zaznaczono nikogo do importu.")
                        else:
                            prog_bar = st.progress(0)
                            count = len(to_import)
                            added = 0
                            
                            for idx, row in to_import.iterrows():
                                # Używamy poprawionej wersji z None zamiast ""
                                db.add_client(
                                    SALON_ID, 
                                    str(row["Imię"]), 
                                    str(row["Telefon"]), 
                                    str(row["Zabieg"]), 
                                    None
                                )
                                added += 1
                                prog_bar.progress((idx + 1) / count)
                            
                            st.success(f"Dodano {added} kontaktów!")
                            time.sleep(1.5)
                            st.rerun()
                else:
                    st.error("Nie rozpoznano kolumn Imię/Telefon w pliku.")
# --- NOWA SEKCJA: DODAWANIE RĘCZNE ---
    with st.expander("➕ DODAJ RĘCZNIE (Pojedynczo)", expanded=False):
        with st.form("manual_add_form"):
            c1, c2 = st.columns(2)
            f_imie = c1.text_input("Imię i Nazwisko")
            f_tel = c2.text_input("Telefon")
            
            c3, c4 = st.columns(2)
            f_zabieg = c3.text_input("Ostatni zabieg", value="Manicure")
            f_data = c4.date_input("Data wizyty", value=None)
            
            submitted = st.form_submit_button("💾 Zapisz klientkę")
            
            if submitted:
                if f_imie and f_tel:
                    # Wywołanie funkcji z database.py
                    success, msg = db.add_client(
                        SALON_ID, 
                        f_imie, 
                        f_tel, 
                        f_zabieg, 
                        f_data
                    )
                    
                    if success:
                        st.success(f"✅ Dodano: {f_imie}")
                        time.sleep(1)
                        st.rerun() # Odśwież stronę, żeby zobaczyć nową osobę w tabeli
                    else:
                        st.error(f"Błąd bazy: {msg}")
                else:
                    st.warning("⚠️ Imię i Telefon są wymagane!")

    # Tabela wyświetlania bazy (poza expanderem)
    df = db.get_clients(SALON_ID)
    if not df.empty:
        st.dataframe(df[['imie', 'telefon', 'ostatni_zabieg']], use_container_width=True)
        # Usuwanie
        opts = df.set_index('id')['imie'].to_dict()
        to_del = st.selectbox("Usuń klientkę:", options=opts.keys(), format_func=lambda x: opts[x])
        if st.button("Usuń wybraną"):
            db.delete_client(to_del, SALON_ID)
            st.rerun()
    else:
        st.info("Baza pusta.")
# --- ZAKŁADKA: AUTOMAT SMS ---
elif page == "🤖 Automat SMS":
    st.header("Generator SMS AI")
    df = db.get_clients(SALON_ID)
    
    if df.empty:
        st.warning("Najpierw dodaj klientki w bazie!")
    else:
        # 1. Konfiguracja
        c1, c2 = st.columns(2)
        salon_name = c1.text_input("Nazwa salonu:", value=st.session_state['salon_name'])
        st.session_state['salon_name'] = salon_name
        
        campaign_goal = c2.text_input("Cel Kampanii (np. promocja na hybrydę):", value=st.session_state['campaign_goal'])
        st.session_state['campaign_goal'] = campaign_goal

        wybrane = st.multiselect("Odbiorcy:", df['imie'].tolist(), default=df['imie'].tolist())
        target_df = df[df['imie'].isin(wybrane)]

        # 2. Generowanie
        if salon_name and not target_df.empty:
            if st.button("🔍 Generuj Treść", type="secondary"):
                # Pobierz przykładowe imię
                sample_name = target_df.iloc[0]['imie']
                content = srv.generate_sms_content(salon_name, sample_name, campaign_goal)
                if content:
                    st.session_state['sms_preview'] = content
                    st.session_state['preview_client'] = sample_name
                    st.rerun()

        # 3. Podgląd i Wysyłka
        if st.session_state['sms_preview']:
            st.divider()
            st.subheader("Podgląd SMS:")
            st.code(st.session_state['sms_preview'], language='text')
            
            col_opt, col_btn = st.columns([2, 1])
            mode = col_opt.radio("Tryb wysyłki:", ["🧪 Test (tylko konsola)", "💸 Produkcja (SMSAPI)"])
            is_test = (mode.startswith("🧪"))
            
            if col_btn.button("🚀 WYŚLIJ KAMPANIĘ", type="primary"):
                progress_bar = st.progress(0.0)
                
                # ZMIANA: Przypisujemy wynik funkcji do zmiennej 'raport_df'
                raport_df = srv.send_campaign_logic(
                    target_df, 
                    st.session_state['campaign_goal'],
                    st.session_state['sms_preview'],
                    is_test, 
                    progress_bar, 
                    st.session_state['preview_client'],
                    st.session_state['salon_name']
                ) 
                
                st.balloons()
                st.success("Wysłano!")
                
                # ZMIANA: Wyświetlamy tabelę z raportem
                st.divider()
                st.subheader("📊 Raport z wysyłki")
                st.dataframe(raport_df, use_container_width=True)
                
                # Dodatkowy bajer: Przycisk do pobrania raportu
                csv = raport_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Pobierz raport (CSV)",
                    data=csv,
                    file_name='raport_kampanii.csv',
                    mime='text/csv',
                )

                st.session_state['sms_preview'] = None




