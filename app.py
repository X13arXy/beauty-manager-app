import streamlit as st
from supabase import create_client
import time
from datetime import date
import pandas as pd

# Import utils
try:
    from utils import generate_single_message_debug, parse_vcf
except ImportError:
    st.error("Brak pliku utils.py!")
    st.stop()

st.set_page_config(page_title="Manager Klientek", page_icon="💅")

# --- DATABASE SETUP ---
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Błąd połączenia z bazą: {e}")
        st.stop()

supabase = init_supabase()

if 'user' not in st.session_state: st.session_state['user'] = None

# --- AUTH & DB FUNCTIONS ---
def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state['user'] = res.user
        st.success("✅ Zalogowano!")
        time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Błąd: {e}")

def register_user(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.session_state['user'] = res.user
            st.success("✅ Konto utworzone!"); time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Błąd: {e}")

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

# --- UI MAIN ---
def main():
    st.title("🌸 Salon Manager AI")

    if not st.session_state['user']:
        t1, t2 = st.tabs(["Logowanie", "Rejestracja"])
        with t1:
            if st.button("Zaloguj", key="l"): login_user(st.text_input("E", key="le"), st.text_input("P", type="password", key="lp"))
        with t2:
            if st.button("Rejestruj", key="r"): register_user(st.text_input("E", key="re"), st.text_input("P", type="password", key="rp"))
    else:
        user_id = st.session_state['user'].id
        with st.sidebar:
            st.write(f"Konto: {st.session_state['user'].email}")
            if st.button("Wyloguj"): logout_user()

        tab_add, tab_list, tab_ai = st.tabs(["➕ Dodaj / Import", "📋 Lista", "🤖 Kampania AI"])

        with tab_add:
            st.info("Opcje dodawania klientek")
            with st.form("manual"):
                c1, c2 = st.columns(2)
                i = c1.text_input("Imię"); t = c1.text_input("Tel")
                z = c2.text_input("Zabieg"); d = c2.date_input("Data")
                if st.form_submit_button("Dodaj"):
                    ok, m = add_client(user_id, i, t, z, d)
                    if ok: st.success("Dodano!"); time.sleep(1); st.rerun()
            
            uploaded = st.file_uploader("Import VCF", type=['vcf'])
            if uploaded:
                df = parse_vcf(uploaded.read())
                st.dataframe(df.head())
                if st.button("Zapisz VCF do bazy"):
                    for _, r in df.iterrows():
                        add_client(user_id, r['Imię'], r['Telefon'], r.get('Ostatni Zabieg','Import'), None)
                    st.success("Zaimportowano!"); time.sleep(1); st.rerun()

        with tab_list:
            cl = get_clients(user_id)
            for c in cl:
                with st.expander(f"{c['imie']}"):
                    st.write(f"Tel: {c['telefon']}"); 
                    if st.button("Usuń", key=f"d{c['id']}"): delete_client(c['id']); st.rerun()

        # --- SEKCJA KAMPANII (TUTAJ NAJWIĘKSZE ZMIANY) ---
        with tab_ai:
            st.header("Generator Kampanii")
            clients = get_clients(user_id)
            
            if not clients:
                st.warning("Brak klientów w bazie.")
            else:
                # 1. Konfiguracja
                col_conf1, col_conf2 = st.columns(2)
                with col_conf1:
                    salon_name = st.text_input("Nazwa Salonu", "KOX BEAUTY")
                with col_conf2:
                    campaign_goal = st.text_input("Cel Kampanii", "Promocja -20% na hasło ZIMA")

                st.divider()

                # 2. LABORATORIUM TESTOWE (Bezpieczne, 1 sztuka)
                st.subheader("🧪 Krok 1: Laboratorium Testowe")
                st.caption("Sprawdź co wymyśli AI zanim wyślesz do wszystkich. To nic nie kosztuje (poza tokenami AI).")
                
                # Lista wyboru klienta do testu
                client_options = {c['imie']: c for c in clients}
                selected_name = st.selectbox("Wybierz klientkę do testu:", list(client_options.keys()))
                test_client = client_options[selected_name]

                if st.button("🧪 GENERUJ TEST (1 sztuka)"):
                    msg, prompt, error = generate_single_message_debug(
                        salon_name, campaign_goal, test_client['imie'], test_client['ostatni_zabieg']
                    )

                    if error:
                        st.error(f"❌ Błąd AI: {error}")
                        st.info("💡 Wskazówka: Sprawdź czy masz poprawny 'GOOGLE_API_KEY' w pliku .streamlit/secrets.toml")
                    else:
                        c1, c2 = st.columns(2)
                        with c1:
                            st.success("✅ Wygenerowana wiadomość:")
                            st.text_area("Wynik", value=msg, height=100)
                        with c2:
                            st.info("🧠 Co widziało AI (Prompt):")
                            st.code(prompt, language="text")

                st.divider()

                # 3. MASOWA PRODUKCJA
                st.subheader("🚀 Krok 2: Generowanie Masowe")
                st.caption("Gdy testy wyjdą dobrze, wygeneruj dla całej listy.")
                
                if st.button("Generuj dla wszystkich klientek"):
                    progress = st.progress(0)
                    for idx, client in enumerate(clients):
                        msg, _, err = generate_single_message_debug(
                            salon_name, campaign_goal, client['imie'], client['ostatni_zabieg']
                        )
                        
                        with st.expander(f"Do: {client['imie']} {('❌ BŁĄD' if err else '✅')}"):
                            if err:
                                st.error(err)
                            else:
                                st.text_area(f"Treść dla {client['imie']}", value=msg, height=80)
                                # Generowanie linku "Wyślij SMS"
                                sms_link = f"sms:{client['telefon']}?body={msg}"
                                st.markdown(f"[📲 Kliknij, aby otworzyć SMS]({sms_link})", unsafe_allow_html=True)
                        
                        time.sleep(1.5) # Ochrona przed banem API
                        progress.progress((idx + 1) / len(clients))

if __name__ == "__main__":
    main()
