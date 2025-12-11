import streamlit as st
from supabase import create_client, Client
import time

# --- 1. POŁĄCZENIE Z BAZĄ ---
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Błąd połączenia z bazą: {e}")
        st.stop()

supabase = init_supabase()

# --- 2. FUNKCJE UŻYTKOWNIKA ---
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

# --- 3. ZARZĄDZANIE KLIENTAMI ---
def add_client(salon_id, imie, telefon, zabieg, data):
    # Czyścimy numer telefonu z kresek i spacji
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
        res = supabase.table("klientki").select("*").eq("salon_id", salon_id).execute()
        return res.data
    except:
        return []

def delete_client(client_id, salon_id):
    try:
        supabase.table("klientki").delete().eq("id", client_id).eq("salon_id", salon_id).execute()
    except:
        pass