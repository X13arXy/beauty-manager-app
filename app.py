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
# 1. EKRAN LOGOWANIA I REJESTRACJI
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
                    # Pobieramy nazwę salonu zapisaną przy rejestracji
                    saved_name = db.get_salon_name(user.id)
                    st.session_state['salon_name'] = saved_name
                    st.success("✅ Zalogowano!")
                    st.rerun()
        
        # --- REJESTRACJA (Z NAZWĄ SALONU) ---
        with tab2:
            r_email = st.text_input("Email", key="r1")
            r_pass = st.text_input("Hasło", type="password", key="r2")
            
            # NOWOŚĆ: Pytamy o nazwę salonu od razu
            r_salon = st.text_input("Nazwa Twojego Salonu", placeholder="np. Studio Basia")
            
            zgoda = st.checkbox("Akceptuję Regulamin i Politykę Prywatności *")
            
            if st.button("Załóż konto"):
                if not zgoda:
                    st.warning("Musisz zaakceptować regulamin!")
                elif not r_salon:
                    st.warning("Podaj nazwę salonu!")
                else:
                    # Przekazujemy też nazwę salonu do funkcji
                    user = db.register_user(r_email, r_pass, r_salon)
                    if user:
                        st.session_state['user'] = user
                        st.session_state['salon_name'] = r_salon
                        st.success("✅ Konto utworzone! Sprawdź email w celu weryfikacji.")
                        time.sleep(2)
                        st.rerun()

        # --- RESET HASŁA ---
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
# ... (kod powyżej bez zmian: CURRENT_USER = ... SALON_ID = ...)

with st.sidebar:
    # Wyświetlamy aktualną nazwę jako nagłówek
    # Używamy .get() na wypadek gdyby sesja jeszcze nie miała tej zmiennej
    current_salon_name = st.session_state.get('salon_name', 'Twój Salon')
    st.header(f"🏠 {current_salon_name}")
    
    if CURRENT_USER:
        st.caption(f"Zalogowany: {CURRENT_USER.email}")
    
    # --- EDYCJA NAZWY W SIDEBARZE ---
    with st.expander("⚙️ Ustawienia Salonu"):
        # Pobieramy obecną nazwę do pola edycji
        edit_name = st.text_input("Zmień nazwę:", value=current_salon_name)
        
        if st.button("Zapisz nową nazwę"):
            if edit_name:
                # Aktualizacja w bazie
                db.update_salon_name(SALON_ID, edit_name)
                # Aktualizacja w sesji
                st.session_state['salon_name'] = edit_name
                st.success("Zmieniono!")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("Nazwa nie może być pusta.")
    # ----------------------------------------

    st.divider()
    
    # TU BYŁ BŁĄD - Dodałem key="logout_btn", żeby Streamlit się nie mylił
    if st.button("Wyloguj", key="logout_btn"):
        db.logout_user()
        st.session_state['user'] = None
        st.session_state['salon_name'] = "" # Czyścimy sesję
        st.rerun()
        
    st.divider()

st.title("Panel Salonu")
# ... (reszta kodu bez zmian)

st.title("Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

# ========================================================
# ZAKŁADKA: BAZA KLIENTEK
# ========================================================
if page == "📂 Baza Klientek":
    st.header("Twoja Baza")

    # --- 1. IMPORT DANYCH ---
    with st.expander("📥 IMPORT (VCF/Excel)", expanded=False):
        uploaded_file = st.file_uploader("Wgraj plik", type=['xlsx', 'csv', 'vcf'])
        
        if uploaded_file:
            df_import = None
            if uploaded_file.name.endswith('.vcf'):
                df_import = srv.parse_vcf(uploaded_file.getvalue())
            elif uploaded_file.name.endswith('.csv'):
                df_import = pd.read_csv(uploaded_file)
            else:
                df_import = pd.read_excel(uploaded_file)
            
            if df_import is not None and not df_import.empty:
                df_import.columns = [c.lower() for c in df_import.columns]
                
                col_imie = next((c for c in df_import.columns if 'imi' in c or 'name' in c), None)
                col_tel = next((c for c in df_import.columns if 'tel' in c or 'num' in c), None)

                if col_imie and col_tel:
                    df_to_show = pd.DataFrame({
                        "Dodaj": True, 
                        "Imię": df_import[col_imie],
                        "Telefon": df_import[col_tel],
                        "Zabieg": "Nieznany"
                    })
                    
                    st.write("Edytuj listę przed importem:")
                    edited_df = st.data_editor(df_to_show, hide_index=True, use_container_width=True)
                    
                    if st.button(f"💾 Zapisz zaznaczone"):
                        to_import = edited_df[edited_df["Dodaj"] == True]
                        
                        if to_import.empty:
                            st.warning("Nie zaznaczono nikogo do importu.")
                        else:
                            prog_bar = st.progress(0)
                            count = len(to_import)
                            added = 0
                            
                            for idx, row in to_import.iterrows():
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

    # --- 2. DODAWANIE RĘCZNE ---
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
                    success, msg = db.add_client(SALON_ID, f_imie, f_tel, f_zabieg, f_data)
                    if success:
                        st.success(f"✅ Dodano: {f_imie}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Błąd bazy: {msg}")
                else:
                    st.warning("⚠️ Imię i Telefon są wymagane!")

    # --- 3. TABELA BAZY ---
    df = db.get_clients(SALON_ID)
    if not df.empty:
        st.dataframe(df[['imie', 'telefon', 'ostatni_zabieg']], use_container_width=True)
        
        opts = df.set_index('id')['imie'].to_dict()
        to_del = st.selectbox("Usuń klientkę:", options=opts.keys(), format_func=lambda x: opts[x])
        if st.button("Usuń wybraną"):
            db.delete_client(to_del, SALON_ID)
            st.rerun()
    else:
        st.info("Baza pusta. Dodaj pierwsze klientki!")

# ========================================================
# ZAKŁADKA: AUTOMAT SMS
# ========================================================
elif page == "🤖 Automat SMS":
    st.header("Generator SMS AI")
    
    # 1. Pobieramy dane
    df = db.get_clients(SALON_ID)
    
    if df.empty:
        st.warning("Najpierw dodaj klientki w bazie (zakładka Baza Klientek)!")
    else:
        # 2. Konfiguracja
        c1, c2 = st.columns(2)
        
        # --- NAZWA SALONU (Pobrana z bazy, ale możliwa do edycji) ---
        current_name = st.session_state.get('salon_name', "")
        
        # Jeśli jakimś cudem pusto, dociągamy z bazy
        if not current_name:
            current_name = db.get_salon_name(SALON_ID)
            st.session_state['salon_name'] = current_name

        salon_name = c1.text_input("Nazwa salonu (Podpis SMS):", value=current_name)
        
        # Jeśli użytkownik tu zmieni nazwę, aktualizujemy bazę
        if salon_name != current_name:
            db.update_salon_name(SALON_ID, salon_name)
            st.session_state['salon_name'] = salon_name
            st.toast("✅ Zaktualizowano nazwę salonu!")
        # ------------------------------------------------------------
        
        campaign_goal = c2.text_input("Cel Kampanii:", value=st.session_state['campaign_goal'])
        st.session_state['campaign_goal'] = campaign_goal

        # 3. Wybór Odbiorców
        st.write("---")
        wybrane = st.multiselect("Odbiorcy:", df['imie'].tolist(), default=df['imie'].tolist())
        target_df = df[df['imie'].isin(wybrane)]

        # 4. Generowanie (Podgląd)
        if salon_name and not target_df.empty:
            if st.button("🔍 Generuj Treść (Podgląd)", type="secondary"):
                sample_row = target_df.iloc[0] 
                content = srv.generate_sms_content(salon_name, sample_row, campaign_goal)
                
                if content:
                    st.session_state['sms_preview'] = content
                    st.session_state['preview_client'] = sample_row.get('imie', 'Klientka')
                    st.rerun()

        # 5. Podgląd, Wysyłka i Raport
        if st.session_state['sms_preview']:
            st.divider()
            st.subheader("Podgląd SMS (dla pierwszej osoby):")
            st.info(f"Przykładowy odbiorca: {st.session_state['preview_client']}")
            st.code(st.session_state['sms_preview'], language='text')
            
            col_opt, col_btn = st.columns([2, 1])
            mode = col_opt.radio("Tryb wysyłki:", ["🧪 Test (Symulacja AI)", "💸 Produkcja (SMSAPI)"])
            is_test = (mode.startswith("🧪"))
            
            if col_btn.button("🚀 WYŚLIJ KAMPANIĘ", type="primary"):
                progress_bar = st.progress(0.0)
                
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
                st.success("Proces zakończony!")
                
                st.divider()
                st.subheader("📊 Raport z wysyłki")
                st.dataframe(raport_df, use_container_width=True)
                
                csv = raport_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Pobierz raport (CSV)",
                    data=csv,
                    file_name='raport_kampanii.csv',
                    mime='text/csv',
                )

                st.session_state['sms_preview'] = None



