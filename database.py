import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- KONFIGURACJA SUPABASE ---
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError:
        st.error("❌ Błąd: Brak kluczy SUPABASE w secrets.toml!")
        st.stop()
    except Exception as e:
        st.error(f"❌ Błąd połączenia z bazą: {e}")
        st.stop()

# Inicjalizacja klienta (globalna dla modułu)
supabase: Client = init_supabase()

# --- AUTORYZACJA ---
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
def add_client(salon_id, imie, telefon, zabieg, data):
    try:
        supabase.table("klientki").insert({
            "salon_id": salon_id, 
            "imie": imie, 
            "telefon": telefon,
            "ostatni_zabieg": zabieg, 
            "data_wizyty": str(data)
        }).execute()
        return True
    except Exception as e:
        st.error(f"Błąd bazy: {e}")
        return False

def get_clients(salon_id):
    try:
        res = supabase.table("klientki").select("*").eq("salon_id", salon_id).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        return pd.DataFrame()

def delete_client(client_id, salon_id):
    try:
        supabase.table("klientki").delete().eq("id", client_id).eq("salon_id", salon_id).execute()
        return True
    except Exception:
        return False
