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
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    div[data-testid="stExpander"] { border: 1px solid #ddd; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# --- STAN SESJI ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'sms_preview' not in st.session_state: st.session_state['sms_preview'] = None
if 'campaign_goal' not in st.session_state: st.session_state['campaign_goal'] = ""
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""
if 'sms_table_key' not in st.session_state: st.session_state['sms_table_key'] = 0
if 'sms_select_all' not in st.session_state: st.session_state['sms_select_all'] = False

# ========================================================
# 1. LOGOWANIE / REJESTRACJA
# ========================================================
if not st.session_state['user']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("💅 Beauty Manager")
        tab1, tab2 = st.tabs(["Logowanie", "Rejestracja"])
        
        with tab1:
            l_email = st.text_input("Email", key="l1")
            l_pass = st.text_input("Hasło", type="password", key="l2")
            if st.button("Zaloguj się", type="primary"):
                user = db.login_user(l_email, l_pass)
                if user:
                    st.session_state['user'] = user
                    st.session_state['salon_name'] = db.get_salon_name(user.id)
                    st.rerun()

        with tab2:
            r_email = st.text_input("Email", key="r1")
            r_pass = st.text_input("Hasło", type="password", key="r2")
            r_salon = st.text_input("Nazwa Salonu")
            if st.button("Załóż konto"):
                if r_email and r_pass and r_salon:
                    user = db.register_user(r_email, r_pass, r_salon)
                    if user:
                        st.session_state['user'] = user
                        st.session_state['salon_name'] = r_salon
                        st.success("Konto utworzone!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning("Wypełnij wszystkie pola.")
    st.stop()

# ========================================================
# 2. APLIKACJA GŁÓWNA
# ========================================================
CURRENT_USER = st.session_state['user']
SALON_ID = CURRENT_USER.id 

# --- SIDEBAR ---
with st.sidebar:
    st.header(f"🏠 {st.session_state.get('salon_name', 'Twój Salon')}")
    st.caption(f"Zalogowany: {CURRENT_USER.email}")
    
    if st.button("Wyloguj"):
        db.logout_user()
        st.session_state['user'] = None
        st.rerun()

st.title("Panel Salonu")
tabs = st.tabs(["📂 Baza Klientek", "🤖 Automat SMS"])

# ========================================================
# ZAKŁADKA 1: BAZA KLIENTEK
# ========================================================
with tabs[0]:
    col_add, col_import = st.columns(2)

    # --- A. FORMULARZ RĘCZNY (To o co prosiłeś) ---
    with col_add:
        with st.expander("➕ Dodaj Klientkę (Ręcznie)", expanded=True):
            with st.form("add_single_client"):
                new_imie = st.text_input("Imię i Nazwisko")
                new_tel = st.text_input("Telefon")
                new_zabieg = st.text_input("Ostatni zabieg", value="Brak")
                
                if st.form_submit_button("Zapisz w bazie", type="primary"):
                    if new_imie and new_tel:
                        ok, msg = db.add_client(SALON_ID, new_imie, new_tel, new_zabieg, None)
                        if ok: 
                            st.success("Dodano!")
                            time.sleep(0.5)
                            st.rerun()
                        else: st.error(f"Błąd: {msg}")
                    else:
                        st.warning("Podaj imię i telefon.")

    # --- B. IMPORT PLIKU (Przywrócone działanie!) ---
    with col_import:
        with st.expander("📥 Import z pliku (Excel/VCF)"):
            uploaded_file = st.file_uploader("Wgraj plik", type=['xlsx', 'csv', 'vcf'])
            
            if uploaded_file:
                # Logika parsowania pliku
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
                        
                        st.info("Zaznacz osoby do importu:")
                        edited_import = st.data_editor(df_to_show, hide_index=True, use_container_width=True)
                        
                        if st.button(f"💾 Zapisz zaznaczone"):
                            to_import = edited_import[edited_import["Dodaj"] == True]
                            
                            if to_import.empty:
                                st.warning("Nikogo nie zaznaczono.")
                            else:
                                prog_bar = st.progress(0.0)
                                added_count = 0
                                
                                for idx, row in to_import.iterrows():
                                    tel_raw = str(row["Telefon"])
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

    # --- C. TABELA (Przeglądanie i Usuwanie) ---
    st.divider()
    st.subheader("Lista Klientek")
    
    df = db.get_clients(SALON_ID)
    
    if not df.empty:
        cols = ['id', 'imie', 'telefon', 'ostatni_zabieg']
        df = df[[c for c in cols if c in df.columns]]

        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "id": st.column_config.TextColumn("ID", width="small"),
                "imie": "Imię i Nazwisko",
                "telefon": "Telefon",
                "ostatni_zabieg": "Ostatni Zabieg"
            }
        )
        
        # Proste usuwanie po ID
        with st.expander("🗑️ Usuwanie"):
            col_del1, col_del2 = st.columns([3, 1])
            id_to_del = col_del1.text_input("Wpisz ID osoby do usunięcia:")
            if col_del2.button("Usuń"):
                if id_to_del:
                    # Sprawdzamy czy to ID istnieje w danych (bezpieczeństwo)
                    if str(id_to_del) in df['id'].astype(str).values:
                        db.delete_clients_by_ids([int(id_to_del)], SALON_ID)
                        st.success("Usunięto!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Brak takiego ID na liście.")
    else:
        st.info("Baza jest pusta. Dodaj kogoś powyżej.")

# ========================================================
# ZAKŁADKA 2: AUTOMAT SMS
# ========================================================
with tabs[1]:
    st.header("Wysyłka Kampanii")

    df_sms = db.get_clients(SALON_ID)

    if df_sms.empty:
        st.warning("Najpierw dodaj klientki w zakładce Baza!")
    else:
        # 1. WYBÓR ODBIORCÓW
        st.subheader("Krok 1: Wybierz Odbiorców")
        
        c_all, c_none = st.columns([1, 5])
        if c_all.button("Zaznacz wszystkich"):
            st.session_state['sms_select_all'] = True
            st.session_state['sms_table_key'] += 1
            st.rerun()
            
        df_sms.insert(0, "Wybierz", st.session_state['sms_select_all'])
        
        edited_sms = st.data_editor(
            df_sms,
            key=f"sms_editor_{st.session_state['sms_table_key']}",
            height=200,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Wybierz": st.column_config.CheckboxColumn(default=False),
                "id": None, "salon_id": None, "created_at": None, "kierunkowy": None, "data_wizyty": None
            }
        )
        
        targets = edited_sms[edited_sms["Wybierz"] == True]
        count = len(targets)
        
        if count > 0:
            st.success(f"Wybrano: {count} osób")
            
            # 2. TREŚĆ I AI
            st.divider()
            st.subheader("Krok 2: Treść Wiadomości")
            
            grid = st.columns(3)
            if grid[0].button("📅 Wolne Terminy"): st.session_state['campaign_goal'] = "Mamy wolne terminy jutro -20%."
            if grid[1].button("⏰ Przypomnienie"): st.session_state['campaign_goal'] = "Przypominamy, że dawno Cię nie było."
            if grid[2].button("🎁 Promocja"): st.session_state['campaign_goal'] = "Tylko dziś promocja na hybrydę."

            goal = st.text_area("Cel wiadomości (lub wpisz własny):", value=st.session_state['campaign_goal'])
            st.session_state['campaign_goal'] = goal
            
            if st.button("✨ GENERUJ TREŚĆ (AI)", type="primary"):
                if goal:
                    content = srv.generate_sms_content(
                        st.session_state['salon_name'], 
                        {}, 
                        goal,
                        generate_template=True
                    )
                    st.session_state['sms_preview'] = content
                else:
                    st.warning("Wpisz cel kampanii.")

            # 3. PODGLĄD I WYSYŁKA
            if st.session_state['sms_preview']:
                st.divider()
                st.subheader("Krok 3: Weryfikacja i Wysyłka")
                
                final_content = st.text_area(
                    "Oto treść SMS (możesz ją poprawić):", 
                    value=st.session_state['sms_preview'],
                    height=100
                )
                st.session_state['sms_preview'] = final_content
                
                st.caption("ℹ️ Znacznik `{imie}
