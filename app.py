import streamlit as st
from supabase import create_client
import time
from datetime import date
import pandas as pd
# Importujemy funkcję AI z twojego drugiego pliku (zakładam, że nazywa się utils.py)
# Jeśli plik nazywa się inaczej, zmień 'utils' na nazwę swojego pliku
try:
    from utils import generate_single_message
except ImportError:
    st.error("Brak pliku utils.py! Upewnij się, że jest w tym samym folderze.")

# --- 1. KONFIGURACJA STRONY I BAZY ---
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

# --- 2. FUNKCJE LOGIKI BIZNESOWEJ ---
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

def add_client(user_id, imie, telefon, zabieg, data_wizyty):
    clean_tel = ''.join(filter(str.isdigit, str(telefon)))
    data_val = str(data_wizyty) if data_wizyty else None
    try:
        supabase.table("klientki").insert({
            "salon_id": user_id,
            "imie": str(imie),
            "telefon": clean_tel,
            "ostatni_zabieg": str(zabieg),
            "data_wizyty": data_val
        }).execute()
        return True, "Dodano klientkę!"
    except Exception as e:
        return False, str(e)

def get_clients(user_id):
    try:
        res = supabase.table("klientki").select("*").eq("salon_id", user_id).order('created_at', desc=True).execute()
        return res.data
    except Exception as e:
        st.error(f"Błąd pobierania danych: {e}")
        return []

def delete_client(client_id):
    try:
        supabase.table("klientki").delete().eq("id", client_id).execute()
        return True
    except Exception as e:
        return False

# --- 3. INTERFEJS UŻYTKOWNIKA (UI) ---
def main():
    st.title("🌸 Salon Manager & AI")

    # A. Widok dla niezalogowanych
    if not st.session_state['user']:
        tab1, tab2 = st.tabs(["Logowanie", "Rejestracja"])
        with tab1:
            st.subheader("Zaloguj się")
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Hasło", type="password", key="login_pass")
            if st.button("Zaloguj"):
                login_user(email, password)
        with tab2:
            st.subheader("Załóż konto")
            new_email = st.text_input("Email", key="reg_email")
            new_pass = st.text_input("Hasło", type="password", key="reg_pass")
            if st.button("Zarejestruj"):
                register_user(new_email, new_pass)

    # B. Widok dla zalogowanych (Dashboard)
    else:
        user_id = st.session_state['user'].id
        
        with st.sidebar:
            st.write(f"Zalogowany: {st.session_state['user'].email}")
            if st.button("Wyloguj"):
                logout_user()

        # GŁÓWNE ZAKŁADKI
        tab_add, tab_list, tab_campaign = st.tabs(["➕ Dodaj", "📋 Lista", "🚀 Kampania SMS (AI)"])

        # --- ZAKŁADKA 1: DODAWANIE ---
        with tab_add:
            with st.form("add_client_form"):
                c1, c2 = st.columns(2)
                with c1:
                    imie = st.text_input("Imię i Nazwisko")
                    telefon = st.text_input("Telefon")
                with c2:
                    zabieg = st.text_input("Zabieg")
                    data_wizyty = st.date_input("Data", value=date.today())
                
                if st.form_submit_button("Zapisz"):
                    if imie:
                        ok, msg = add_client(user_id, imie, telefon, zabieg, data_wizyty)
                        if ok:
                            st.success(msg)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Imię jest wymagane!")

        # --- ZAKŁADKA 2: LISTA KLIENTÓW ---
        with tab_list:
            clients = get_clients(user_id)
            if clients:
                st.write(f"Baza klientek: {len(clients)}")
                for client in clients:
                    with st.expander(f"{client.get('imie')} - {client.get('ostatni_zabieg')}"):
                        st.write(f"Tel: {client.get('telefon')}")
                        if st.button("Usuń", key=f"del_{client['id']}"):
                            delete_client(client['id'])
                            st.rerun()
            else:
                st.info("Brak klientek.")

        # --- ZAKŁADKA 3: KAMPANIA AI (To tutaj był błąd wcięcia) ---
        with tab_campaign:
            st.subheader("Generator wiadomości SMS")
            clients = get_clients(user_id)
            
            if not clients:
                st.warning("Najpierw dodaj klientki w zakładce 'Lista'!")
            else:
                # Pola konfiguracji kampanii
                cel_kampanii = st.text_input("Cel kampanii (np. promocja -15% na święta)", value="promocja -15% do końca tygodnia")
                
                # Przycisk generowania
                if st.button("🚀 Generuj propozycje SMS"):
                    st.write("---")
                    progress_bar = st.progress(0)
                    
                    # Konwersja listy słowników na DataFrame dla łatwiejszej obsługi
                    df = pd.DataFrame(clients)
                    
                    for index, row in df.iterrows():
                        imie = row.get('imie', 'Klientka')
                        zabieg = row.get('ostatni_zabieg', 'wizyta')
                        salon = "Twój Salon" # Możesz tu wpisać nazwę na sztywno lub pobrać z ustawień

                        # Generowanie przez AI (z pliku utils.py)
                        wiadomosc = generate_single_message(salon, cel_kampanii, imie, zabieg)
                        
                        # Wyświetlanie wyniku
                        st.markdown(f"**Do:** {imie}")
                        st.info(wiadomosc)
                        
                        # Ważne opóźnienie dla API
                        time.sleep(1.5)
                        progress_bar.progress((index + 1) / len(df))
                    
                    st.success("Gotowe! Możesz kopiować wiadomości.")

if __name__ == "__main__":
    main()
