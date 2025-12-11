import streamlit as st
from supabase import create_client
import time
from datetime import date
import pandas as pd

# Import funkcji z utils.py
try:
    from utils import generate_single_message, parse_vcf
except ImportError:
    st.error("Brak pliku utils.py! Wgraj go do folderu aplikacji.")
    st.stop()

# --- 1. KONFIGURACJA ---
st.set_page_config(page_title="Manager Klientek", page_icon="💅")

def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Błąd połączenia z bazą: {e}")
        st.stop()

supabase = init_supabase()

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 2. LOGIKA BAZY DANYCH ---
def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state['user'] = res.user
        st.success("✅ Zalogowano!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Błąd logowania: {e}")

def register_user(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.session_state['user'] = res.user
            st.success("✅ Konto utworzone! Zalogowano.")
            time.sleep(1)
            st.rerun()
    except Exception as e:
        st.error(f"Błąd rejestracji: {e}")

def logout_user():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

def add_client(salon_id, imie, telefon, zabieg, data):
    clean_tel = ''.join(filter(str.isdigit, str(telefon)))
    data_val = str(data) if data and str(data).strip() != "" else None
    
    try:
        supabase.table("klientki").insert({
            "salon_id": salon_id,
            "imie": str(imie),
            "telefon": clean_tel,
            "ostatni_zabieg": str(zabieg),
            "data_wizyty": data_val
        }).execute()
        return True, ""
    except Exception as e:
        return False, str(e)

def get_clients(salon_id):
    try:
        res = supabase.table("klientki").select("*").eq("salon_id", salon_id).order('created_at', desc=True).execute()
        return res.data
    except:
        return []

def delete_client(client_id):
    try:
        supabase.table("klientki").delete().eq("id", client_id).execute()
        return True
    except:
        return False

# --- 3. INTERFEJS (UI) ---
def main():
    st.title("🌸 Salon Manager")

    if not st.session_state['user']:
        # EKRAN LOGOWANIA
        tab1, tab2 = st.tabs(["Logowanie", "Rejestracja"])
        with tab1:
            email = st.text_input("Email", key="log_mail")
            password = st.text_input("Hasło", type="password", key="log_pass")
            if st.button("Zaloguj"):
                login_user(email, password)
        with tab2:
            email = st.text_input("Email", key="reg_mail")
            password = st.text_input("Hasło", type="password", key="reg_pass")
            if st.button("Zarejestruj"):
                register_user(email, password)
    else:
        # PANEL GŁÓWNY
        user_id = st.session_state['user'].id
        
        with st.sidebar:
            st.write(f"Zalogowany: {st.session_state['user'].email}")
            if st.button("Wyloguj"):
                logout_user()

        tab_add, tab_list, tab_ai = st.tabs(["➕ Dodaj / Import", "📋 Lista Klientek", "🤖 Kampania AI"])

        # --- ZAKŁADKA 1: DODAWANIE RĘCZNE I IMPORT ---
        with tab_add:
            st.subheader("1. Dodawanie ręczne")
            with st.form("add_manual"):
                c1, c2 = st.columns(2)
                with c1:
                    imie = st.text_input("Imię i Nazwisko")
                    tel = st.text_input("Telefon")
                with c2:
                    zabieg = st.text_input("Ostatni zabieg")
                    data = st.date_input("Data wizyty", value=date.today())
                
                if st.form_submit_button("Zapisz ręcznie"):
                    ok, msg = add_client(user_id, imie, tel, zabieg, data)
                    if ok:
                        st.success("Dodano!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Błąd: {msg}")

            st.write("---")
            st.subheader("2. 📥 Import z pliku (VCF)")
            uploaded_file = st.file_uploader("Wgraj plik .vcf z kontaktami", type=['vcf'])
            
            if uploaded_file is not None:
                # Używamy funkcji z utils.py
                df_contacts = parse_vcf(uploaded_file.read())
                
                st.write(f"Znaleziono {len(df_contacts)} kontaktów.")
                st.dataframe(df_contacts.head())

                if st.button("💾 Zapisz te kontakty do bazy"):
                    progress = st.progress(0)
                    success_count = 0
                    
                    for index, row in df_contacts.iterrows():
                        ok, _ = add_client(
                            user_id, 
                            row['Imię'], 
                            row['Telefon'], 
                            row.get('Ostatni Zabieg', 'Import'), 
                            date.today()
                        )
                        if ok: success_count += 1
                        time.sleep(0.1) # Lekkie opóźnienie dla stabilności
                        progress.progress((index + 1) / len(df_contacts))
                    
                    st.success(f"Pomyślnie zaimportowano: {success_count} klientek!")
                    time.sleep(2)
                    st.rerun()

        # --- ZAKŁADKA 2: LISTA ---
        with tab_list:
            clients = get_clients(user_id)
            if clients:
                st.write(f"Twoja baza: {len(clients)} osób")
                for c in clients:
                    with st.expander(f"{c['imie']} ({c['telefon']})"):
                        st.write(f"Zabieg: {c['ostatni_zabieg']}")
                        if st.button("Usuń", key=f"del_{c['id']}"):
                            delete_client(c['id'])
                            st.rerun()
            else:
                st.info("Baza jest pusta. Dodaj kogoś lub zaimportuj plik!")

        # --- ZAKŁADKA 3: AI ---
        with tab_ai:
            st.header("Generator Kampanii SMS")
            clients = get_clients(user_id)
            
            if not clients:
                st.warning("Najpierw dodaj klientki!")
            else:
                cel = st.text_input("Co promujemy?", value="Promocja -20% na hasło ZIMA")
                
                if st.button("🚀 Generuj wiadomości"):
                    bar = st.progress(0)
                    df = pd.DataFrame(clients)
                    
                    for i, row in df.iterrows():
                        # Używamy funkcji z utils.py
                        msg = generate_single_message("Twój Salon", cel, row['imie'], row['ostatni_zabieg'])
                        
                        st.markdown(f"**Do: {row['imie']}**")
                        st.info(msg)
                        
                        time.sleep(1.5) # Ważne dla limitów API Google
                        bar.progress((i + 1) / len(df))

if __name__ == "__main__":
    main()
