import streamlit as st
from supabase import create_client
import time
from datetime import date
import pandas as pd

# --- 0. IMPORT FUNKCJI Z UTILS ---
try:
    from utils import generate_single_message_debug, parse_vcf
except ImportError:
    st.error("Brak pliku utils.py! Upewnij się, że wgrałeś oba pliki.")
    st.stop()

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="Manager Klientek", page_icon="💅")

# --- 2. BAZA DANYCH ---
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Błąd konfiguracji bazy: {e}")
        st.stop()

supabase = init_supabase()

# Inicjalizacja sesji (zapobiega wylogowaniu po odświeżeniu)
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 3. FUNKCJE LOGOWANIA I DANYCH ---
def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state['user'] = res.user
        return True
    except Exception as e:
        st.error(f"Błąd logowania: {e}")
        return False

def register_user(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.session_state['user'] = res.user
            return True
    except Exception as e:
        st.error(f"Błąd rejestracji: {e}")
        return False

def logout_user():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

def add_client(user_id, imie, telefon, zabieg, data):
    clean_tel = ''.join(filter(str.isdigit, str(telefon)))
    data_val = str(data) if data else None
    try:
        supabase.table("klientki").insert({
            "salon_id": user_id, "imie": str(imie), "telefon": clean_tel,
            "ostatni_zabieg": str(zabieg), "data_wizyty": data_val
        }).execute()
        return True, ""
    except Exception as e: return False, str(e)

def get_clients(user_id):
    try:
        res = supabase.table("klientki").select("*").eq("salon_id", user_id).order('created_at', desc=True).execute()
        return res.data
    except: return []

def delete_client(cid):
    try: supabase.table("klientki").delete().eq("id", cid).execute(); return True
    except: return False

# --- 4. INTERFEJS GŁÓWNY ---
def main():
    st.title("🌸 Salon Manager AI")

    # A. EKRAN LOGOWANIA (NAPRAWIONY - UŻYWA FORMULARZY)
    if not st.session_state['user']:
        tab1, tab2 = st.tabs(["Logowanie", "Rejestracja"])
        
        # --- LOGOWANIE ---
        with tab1:
            st.write("Wpisz dane i zatwierdź przyciskiem.")
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Hasło", type="password")
                
                # Przycisk jest wewnątrz formularza - strona nie odświeży się za wcześnie
                submit = st.form_submit_button("Zaloguj się")
                
                if submit:
                    if login_user(email, password):
                        st.success("✅ Zalogowano!")
                        time.sleep(1)
                        st.rerun()

        # --- REJESTRACJA ---
        with tab2:
            st.write("Załóż nowe konto.")
            with st.form("register_form"):
                new_email = st.text_input("Email")
                new_pass = st.text_input("Hasło", type="password")
                
                reg_submit = st.form_submit_button("Zarejestruj się")
                
                if reg_submit:
                    if register_user(new_email, new_pass):
                        st.success("✅ Konto utworzone! Witaj.")
                        time.sleep(1)
                        st.rerun()

    # B. PANEL UŻYTKOWNIKA (PO ZALOGOWANIU)
    else:
        user_id = st.session_state['user'].id
        
        # Sidebar
        with st.sidebar:
            st.write(f"Zalogowany: {st.session_state['user'].email}")
            if st.button("Wyloguj"):
                logout_user()

        # Zakładki
        tab_add, tab_list, tab_ai = st.tabs(["➕ Dodaj / Import", "📋 Lista", "🤖 Kampania AI"])

        # --- 1. DODAWANIE ---
        with tab_add:
            st.info("Dodaj klientkę ręcznie lub z pliku")
            
            # Formularz ręczny
            with st.form("manual_add"):
                c1, c2 = st.columns(2)
                i = c1.text_input("Imię i Nazwisko")
                t = c1.text_input("Telefon")
                z = c2.text_input("Zabieg")
                d = c2.date_input("Data wizyty", value=date.today())
                
                if st.form_submit_button("Zapisz klientkę"):
                    if i:
                        ok, m = add_client(user_id, i, t, z, d)
                        if ok: 
                            st.success("Dodano!")
                            time.sleep(1)
                            st.rerun()
                        else: st.error(f"Błąd: {m}")
                    else: st.warning("Podaj imię!")
            
            st.divider()
            
            # Import pliku
            st.write("📥 **Import kontaktów (VCF)**")
            uploaded = st.file_uploader("Wgraj plik .vcf z telefonu", type=['vcf'])
            if uploaded:
                df = parse_vcf(uploaded.read())
                st.dataframe(df.head())
                if st.button("💾 Zapisz te kontakty w bazie"):
                    progress = st.progress(0)
                    for idx, row in df.iterrows():
                        add_client(user_id, row['Imię'], row['Telefon'], row.get('Ostatni Zabieg', 'Import'), None)
                        progress.progress((idx + 1) / len(df))
                    st.success("Zaimportowano!")
                    time.sleep(1.5)
                    st.rerun()

        # --- 2. LISTA ---
        with tab_list:
            clients = get_clients(user_id)
            if clients:
                st.write(f"Liczba klientek: {len(clients)}")
                for c in clients:
                    with st.expander(f"{c.get('imie', '---')} ({c.get('telefon', '')})"):
                        st.write(f"Zabieg: {c.get('ostatni_zabieg')}")
                        if st.button("Usuń", key=f"del_{c['id']}"):
                            delete_client(c['id'])
                            st.rerun()
            else:
                st.info("Baza pusta. Dodaj kogoś!")

        # --- 3. KAMPANIA AI (Z TESTAMI) ---
        with tab_ai:
            st.header("Generator Kampanii")
            clients = get_clients(user_id)
            
            if not clients:
                st.warning("Dodaj najpierw klientki w zakładce 'Dodaj'!")
            else:
                col1, col2 = st.columns(2)
                with col1: salon = st.text_input("Nazwa Salonu", "Twój Salon")
                with col2: cel = st.text_input("Cel Kampanii", "Promocja -20% na hasło ZIMA")
                
                st.divider()
                st.subheader("🧪 Krok 1: Test (Sprawdź zanim wyślesz)")
                
                # Wybór osoby do testu
                client_map = {c['imie']: c for c in clients}
                test_person_name = st.selectbox("Na kim testujemy?", list(client_map.keys()))
                test_person = client_map[test_person_name]

                if st.button("🧬 Generuj TEST (1 sztuka)"):
                    msg, prompt, err = generate_single_message_debug(
                        salon, cel, test_person['imie'], test_person['ostatni_zabieg']
                    )
                    
                    if err:
                        st.error(f"Błąd AI: {err}")
                        st.info("Sprawdź klucz API w secrets.toml")
                    else:
                        c_res1, c_res2 = st.columns(2)
                        with c_res1:
                            st.success("Wynik (SMS):")
                            st.text_area("Gotowa wiadomość", value=msg, height=120)
                        with c_res2:
                            st.info("Logika (Prompt):")
                            st.code(prompt, language="text")

                st.divider()
                st.subheader("🚀 Krok 2: Generowanie dla wszystkich")
                
                if st.button("Generuj całą listę"):
                    prog = st.progress(0)
                    for i, c in enumerate(clients):
                        msg, _, err = generate_single_message_debug(salon, cel, c['imie'], c['ostatni_zabieg'])
                        
                        with st.expander(f"Do: {c['imie']}"):
                            if err: st.error(err)
                            else:
                                st.text_area("Treść", msg, height=70)
                                link = f"sms:{c['telefon']}?body={msg}"
                                st.markdown(f"[📲 Otwórz w SMS]({link})")
                        
                        time.sleep(1.5)
                        prog.progress((i+1)/len(clients))

if __name__ == "__main__":
    main()
