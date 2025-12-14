import streamlit as st
import pandas as pd
import time

# IMPORTY TWOICH MODUŁÓW
import database as db
import services as srv

# --- KONFIGURACJA UI ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .success-box { padding: 10px; background-color: #d4edda; color: #155724; border-radius: 5px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- STAN SESJI (SESSION STATE) ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'sms_preview' not in st.session_state: st.session_state['sms_preview'] = None
if 'preview_client' not in st.session_state: st.session_state['preview_client'] = None
if 'campaign_goal' not in st.session_state: st.session_state['campaign_goal'] = ""
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""
if 'sms_table_key_version' not in st.session_state: st.session_state['sms_table_key_version'] = 0
if 'sms_default_check' not in st.session_state: st.session_state['sms_default_check'] = False

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
                    saved_name = db.get_salon_name(user.id)
                    st.session_state['salon_name'] = saved_name
                    st.success("✅ Zalogowano!")
                    time.sleep(0.5)
                    st.rerun()
        
        # --- REJESTRACJA ---
        with tab2:
            r_email = st.text_input("Email", key="r1")
            r_pass = st.text_input("Hasło", type="password", key="r2")
            r_salon = st.text_input("Nazwa Twojego Salonu", placeholder="np. Studio Basia")
            zgoda = st.checkbox("Akceptuję Regulamin *")
            
            if st.button("Załóż konto"):
                if not zgoda:
                    st.warning("Musisz zaakceptować regulamin!")
                elif not r_salon:
                    st.warning("Podaj nazwę salonu!")
                else:
                    user = db.register_user(r_email, r_pass, r_salon)
                    if user:
                        st.session_state['user'] = user
                        st.session_state['salon_name'] = r_salon
                        st.success("✅ Konto utworzone! Potwierdź email jeśli wymagane.")
                        time.sleep(2)
                        st.rerun()

        # --- RESET HASŁA ---
        with tab3:
            st.write("Zapomniałeś hasła? Podaj email.")
            reset_email = st.text_input("Twój Email", key="res1")
            if st.button("Wyślij link resetujący"):
                if reset_email:
                    ok, msg = db.reset_password_email(reset_email)
                    if ok: st.success(msg)
                    else: st.error(f"Błąd: {msg}")

    st.stop()

# ========================================================
# 2. APLIKACJA GŁÓWNA (PO ZALOGOWANIU)
# ========================================================
CURRENT_USER = st.session_state['user']
SALON_ID = CURRENT_USER.id 

with st.sidebar:
    current_salon_name = st.session_state.get('salon_name', 'Twój Salon')
    st.header(f"🏠 {current_salon_name}")
    st.caption(f"ID: {CURRENT_USER.email}")
    
    with st.expander("⚙️ Ustawienia"):
        edit_name = st.text_input("Zmień nazwę:", value=current_salon_name)
        if st.button("Zapisz nazwę"):
            if edit_name:
                db.update_salon_name(SALON_ID, edit_name)
                st.session_state['salon_name'] = edit_name
                st.success("Zapisano!")
                st.rerun()
    
    st.divider()
    if st.button("Wyloguj"):
        db.logout_user()
        st.session_state['user'] = None
        st.rerun()

st.title("Panel Zarządzania")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

# ========================================================
# ZAKŁADKA: BAZA KLIENTEK
# ========================================================
if page == "📂 Baza Klientek":
    st.header("Twoja Baza")

    # --- 1. IMPORT ---
    with st.expander("📥 IMPORT DANYCH (Excel/VCF)", expanded=False):
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
                # Normalizacja kolumn (wszystko na małe litery)
                df_import.columns = [c.lower() for c in df_import.columns]
                
                # Szukanie odpowiednich kolumn
                col_imie = next((c for c in df_import.columns if 'imi' in c or 'name' in c), None)
                col_tel = next((c for c in df_import.columns if 'tel' in c or 'num' in c), None)

                if col_imie and col_tel:
                    # Prezentacja danych do importu
                    df_to_show = pd.DataFrame({
                        "Dodaj": True, 
                        "Imię": df_import[col_imie],
                        "Telefon": df_import[col_tel].astype(str),
                        "Zabieg": "Importowany"
                    })
                    
                    st.info("Sprawdź dane przed importem:")
                    edited_import = st.data_editor(df_to_show, hide_index=True, use_container_width=True)
                    
                    if st.button(f"💾 Zapisz zaznaczone"):
                        to_import = edited_import[edited_import["Dodaj"] == True]
                        
                        if to_import.empty:
                            st.warning("Nikogo nie zaznaczono.")
                        else:
                            prog_bar = st.progress(0.0)
                            added_count = 0
                            
                            for idx, row in to_import.iterrows():
                                # Walidacja w locie
                                tel_raw = str(row["Telefon"])
                                # Używamy funkcji z database.py (która już tam jest) do zapisu
                                success, _ = db.add_client(
                                    SALON_ID, 
                                    str(row["Imię"]), 
                                    tel_raw, 
                                    str(row["Zabieg"]), 
                                    None
                                )
                                if success: added_count += 1
                                prog_bar.progress(min((idx + 1) / len(to_import), 1.0))
                            
                            st.success(f"✅ Dodano {added_count} kontaktów!")
                            time.sleep(1.5)
                            st.rerun()
                else:
                    st.error("Nie znaleziono kolumn 'Imię' i 'Telefon' w pliku.")

    # --- 2. TABELA GŁÓWNA ---
    st.divider()
    
    # Pobranie danych
    df = db.get_clients(SALON_ID)
    
    # Obsługa pustej bazy
    if df.empty:
        df = pd.DataFrame(columns=["id", "salon_id", "imie", "kierunkowy", "telefon", "ostatni_zabieg", "data_wizyty"])
    
    # Upewnienie się, że kolumny istnieją
    if 'kierunkowy' not in df.columns: df['kierunkowy'] = '48'
    
    # Sortowanie kolumn
    cols_order = ['id', 'imie', 'kierunkowy', 'telefon', 'ostatni_zabieg', 'data_wizyty']
    df = df[[c for c in cols_order if c in df.columns]]

    # --- BEZPIECZEŃSTWO: Przełącznik usuwania ---
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1: st.subheader("Edycja Bazy")
    with col_h2: 
        delete_mode = st.toggle("🔴 Włącz tryb usuwania")

    # Konfiguracja edytora
    edited_database = st.data_editor(
        df,
        key="main_db_editor",
        num_rows="dynamic" if delete_mode else "fixed", # Blokada usuwania/dodawania jeśli toggle wyłączony
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True, width="small"),
            "imie": st.column_config.TextColumn("Imię i Nazwisko", required=True),
            "kierunkowy": st.column_config.TextColumn("Kier.", width="small", max_chars=4, default="48"),
            "telefon": st.column_config.TextColumn("Telefon", required=True),
            "ostatni_zabieg": st.column_config.TextColumn("Ostatni Zabieg"),
            "data_wizyty": st.column_config.DateColumn("Data Wizyty")
        }
    )

    if st.button("💾 Zapisz wszystkie zmiany", type="primary"):
        try:
            # Konwersja edytora na słowniki
            raw_data = edited_database.to_dict(orient='records')
            
            # --- LOGIKA ZAPISU I USUWANIA ---
            # 1. Jakie ID są teraz w tabeli?
            current_ids = [row['id'] for row in raw_data if row.get('id') and pd.notna(row['id'])]
            
            # 2. Jakie ID były wcześniej? (żeby wykryć usunięte)
            original_ids = df['id'].tolist() if not df.empty else []
            ids_to_delete = list(set(original_ids) - set(current_ids))

            # 3. Usuwanie
            if ids_to_delete:
                db.delete_clients_by_ids(ids_to_delete, SALON_ID)

            # 4. Zapisywanie (Upsert)
            data_to_upsert = []
            for row in raw_data:
                # Czyścimy dane przed wysłaniem
                clean_row = {
                    "salon_id": SALON_ID,
                    "imie": row.get("imie"),
                    "telefon": ''.join(filter(str.isdigit, str(row.get("telefon", "")))),
                    "kierunkowy": ''.join(filter(str.isdigit, str(row.get("kierunkowy", "48")))),
                    "ostatni_zabieg": row.get("ostatni_zabieg"),
                    "data_wizyty": row.get("data_wizyty")
                }
                # Jeśli to stary wiersz, dodajemy ID. Jeśli nowy, baza nada ID.
                if row.get("id") and pd.notna(row["id"]):
                    clean_row["id"] = row["id"]
                
                data_to_upsert.append(clean_row)

            if data_to_upsert:
                ok, msg = db.update_clients_bulk(data_to_upsert)
                if ok: st.success("✅ Zapisano zmiany!")
                else: st.error(f"Błąd zapisu: {msg}")
            
            # Odświeżenie po chwili
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"Wystąpił błąd: {e}")

# ========================================================
# ZAKŁADKA: AUTOMAT SMS
# ========================================================
elif page == "🤖 Automat SMS":
    st.header("Generator Kampanii AI")
    
    clients_from_db = db.get_clients(SALON_ID)
    
    if clients_from_db.empty:
        st.warning("Baza jest pusta. Dodaj klientki w pierwszej zakładce.")
    else:
        # --- 1. CEL KAMPANII (Z Szybkimi Przyciskami) ---
        st.subheader("1. Co chcesz przekazać?")
        
        # Szybkie przyciski (Callbacki)
        def set_goal(text): st.session_state['campaign_goal'] = text

        c1, c2, c3 = st.columns(3)
        if c1.button("📅 Wolne terminy"): set_goal("Mamy wolne terminy na ten tydzień -20%.")
        if c2.button("🎂 Przypomnienie"): set_goal("Przypominamy o konieczności umówienia wizyty.")
        if c3.button("🎁 Promocja"): set_goal("Promocja na zabiegi pielęgnacyjne -15%.")

        campaign_goal = st.text_area(
            "Lub wpisz własny cel:", 
            value=st.session_state['campaign_goal'],
            placeholder="np. Zapchaj dziury w grafiku na jutro"
        )
        st.session_state['campaign_goal'] = campaign_goal

        # --- 2. WYBÓR ODBIORCÓW ---
        st.subheader("2. Wybierz Odbiorców")
        
        # Logika zaznaczania
        col_all, col_none = st.columns([1, 4])
        if col_all.button("✅ Wszyscy"):
             st.session_state['sms_default_check'] = True
             st.session_state['sms_table_key_version'] += 1
             st.rerun()
        
        # Kopia danych do wyświetlenia
        selection_df = clients_from_db.copy()
        selection_df.insert(0, "Wybierz", st.session_state['sms_default_check'])
        
        # Edytor selekcji
        edited_selection = st.data_editor(
            selection_df,
            key=f"sms_sel_v{st.session_state['sms_table_key_version']}",
            height=300,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Wybierz": st.column_config.CheckboxColumn("Wyślij?", default=False),
                "imie": st.column_config.TextColumn("Klientka", disabled=True),
                "telefon": st.column_config.TextColumn("Telefon", disabled=True),
                "ostatni_zabieg": st.column_config.TextColumn("Ostatni Zabieg", disabled=True),
                "id": None, "salon_id": None, "data_wizyty": None, "kierunkowy": None
            }
        )
        
        target_df = edited_selection[edited_selection["Wybierz"] == True]
        count = len(target_df)

        # --- 3. GENEROWANIE I WYSYŁKA ---
        st.divider()
        if count > 0 and campaign_goal:
            st.info(f"Odbiorcy: **{count} osób**.")
            
            # Krok 1: Generuj Szablon (Zamiast generować dla każdego osobno)
            if st.button("✨ Generuj Szablon SMS"):
                sample_client = target_df.iloc[0]
                # Wywołujemy nową funkcję z services (którą zaraz dostaniesz)
                # Przekazujemy "template=True" żeby AI stworzyło wzór z {imie}
                content = srv.generate_sms_content(
                    st.session_state['salon_name'], 
                    sample_client, 
                    campaign_goal,
                    generate_template=True # <--- WAŻNA ZMIANA
                )
                st.session_state['sms_preview'] = content

            # Krok 2: Podgląd i Wysyłka
            if st.session_state['sms_preview']:
                st.subheader("Podgląd Szablonu:")
                st.code(st.session_state['sms_preview'], language='text')
                st.caption("AI wstawi odpowiednie imię w miejsce '{imie}'.")

                col_opt, col_send = st.columns([2, 1])
                mode = col_opt.radio("Tryb:", ["🧪 Test (Symulacja)", "💸 Produkcja (SMSAPI)"])
                is_test = "Test" in mode

                if col_send.button("🚀 WYŚLIJ KAMPANIĘ", type="primary"):
                    progress_bar = st.progress(0.0)
                    
                    # Przygotowanie danych (klejenie numerów)
                    sending_df = target_df.copy()
                    # Jeśli nie ma kierunkowego, daj 48
                    if 'kierunkowy' not in sending_df.columns: sending_df['kierunkowy'] = '48'
                    
                    # Kleimy numer dla API
                    sending_df['full_phone'] = sending_df.apply(
                        lambda x: str(x['kierunkowy']).strip() + str(x['telefon']).strip(), 
                        axis=1
                    )
                    
                    # Wywołanie logiki wysyłki
                    report = srv.send_campaign_logic(
                        sending_df,
                        st.session_state['sms_preview'], # To jest teraz szablon!
                        is_test,
                        progress_bar,
                        st.session_state['salon_name']
                    )
                    
                    st.success("Wysłano!")
                    st.dataframe(report)
                    st.session_state['sms_preview'] = None # Reset
        else:
            if count == 0: st.caption("Zaznacz kogoś z listy.")
            if not campaign_goal: st.caption("Wpisz cel kampanii.")
