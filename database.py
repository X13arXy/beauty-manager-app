import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- INICJALIZACJA BAZY ---
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Błąd połączenia z bazą: {e}")
        st.stop()

supabase: Client = init_supabase()

# --- LOGOWANIE I REJESTRACJA ---
def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return response.user
    except Exception as e:
        st.error(f"Błąd logowania: {e}")
        return None

def register_user(email, password):
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        return response.user
    except Exception as e:
        st.error(f"Błąd rejestracji: {e}")
        return None

def logout_user():
    supabase.auth.sign_out()

# --- OPERACJE NA DANYCH (CRUD) ---

# To jest ta poprawiona funkcja, o którą prosiłeś:
def add_client(salon_id, imie, telefon, zabieg, data):
    # Czyścimy numer telefonu z myślników i spacji
    clean_tel = ''.join(filter(str.isdigit, str(telefon)))
    
    # Tu jest Twój FIX na daty (None zamiast pustego stringa)
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
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

def delete_client(client_id, salon_id):
    try:
        supabase.table("klientki").delete().eq("id", client_id).eq("salon_id", salon_id).execute()
        return True
    except:
        return False
def reset_password_email(email):
    try:
        # To wyśle maila z linkiem do zmiany hasła (obsługiwane przez Supabase)
        supabase.auth.reset_password_for_email(email, {
            "redirect_to": "http://localhost:8501" # Tutaj w przyszłości dasz adres swojej apki w chmurze
        })
        return True, "Link wysłany! Sprawdź email."
    except Exception as e:
        return False, str(e)
