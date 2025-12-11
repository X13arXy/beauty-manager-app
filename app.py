import streamlit as st
import pandas as pd
import google.generativeai as genai
import time
from supabase import create_client, Client

# --- 1. KONFIGURACJA ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .auth-container { max-width: 400px; margin: auto; padding: 20px; }
</style>
""", unsafe_allow_html=True)

# --- ŁADOWANIE KLUCZY ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    SMSAPI_TOKEN = st.secrets.get("SMSAPI_TOKEN", "")
except KeyError as e:
    st.error(f"❌ Błąd: Brak klucza {e} w Streamlit Secrets!")
    st.stop()

# Klienci
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash') # Stabilny model
except Exception as e:
    st.error(f"❌ Błąd konfiguracji: {e}")
    st.stop()

try:
    from smsapi.client import SmsApiPlClient
    from smsapi.exception import SmsApiException
except ImportError:
    pass

# --- 2. STAN SESJI ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""

# --- 3. FUNKCJE POMOCNICZE ---

def usun_ogonki(tekst):
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

def parse_vcf(file_content):
    """Czyta kontakty z telefonu"""
    try:
        content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        content = file_content.decode("latin-1")
    contacts = []
    current = {}
    for line in content.splitlines():
        if line.startswith("BEGIN:VCARD"): current = {}
        elif line.startswith("FN:") or line.startswith("N:"):
            if "Imię" not in current:
                parts = line.split(":", 1)[1]
                current["Imię"] = parts.replace(";", " ").strip()
        elif line.startswith("TEL"):
            if "Telefon" not in current:
                num = line.split(":", 1)[1]
                clean = ''.join(filter(str.isdigit, num))
                if len(clean) == 9: clean = "48" + clean
                current["Telefon"] = clean
        elif line.startswith("END:VCARD"):
            if "Imię" in current and "Telefon" in current:
                current["Ostatni Zabieg"] = "Nieznany"
                contacts.append(current)
    return pd.DataFrame(contacts)

def login_user(e, p):
    try:
        res = supabase.auth.sign_in_with_password({"email": e, "password": p})
        st.session_state['user'] = res.user
        st.rerun()
    except Exception as err: st.error(f"Błąd: {err}")

def register_user(e, p):
    try:
        res = supabase.auth.sign_up({"email": e, "password": p})
        if res.user: 
            st.session_state['user'] = res.user
            st.rerun()
    except Exception as err: st.error(f"Błąd: {err}")

def logout_user():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- FUNKCJA WYSYŁAJĄCA Z RAPORTEM (NOWOŚĆ) ---
def send_campaign_batch_with_report(target_df, campaign_goal, salon_name, is_test_mode):
    sms_token = st.secrets.get("SMSAPI_TOKEN", "")
    client = None

    if not is_test_mode:
        if not sms_token:
            st.error("❌ Brak tokenu SMSAPI!")
            return
        try:
            client = SmsApiPlClient(access_token=sms_token)
        except Exception as e:
            st.error(f"Błąd logowania SMSAPI: {e}")
            return

    st.write("---")
    progress_bar = st.progress(0.0)
    status_text = st.empty()
    
    # TU ZBIERAMY DANE DO TABELI
    raport_lista = [] 
    
    # Konfiguracja Batch
    BATCH_SIZE = 5
    total = len(target_df)
    records = target_df.to_dict('records')
    
    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        status_text.text(f"⏳ Przetwarzam pakiet {i+1} z {total}...")
        
        # 1. Generowanie (Szybkie)
        list_txt = ""
        for idx, c in enumerate(batch):
            list_txt += f"ID {idx}: {c['imie']} (Zabieg: {c['ostatni_zabieg']})\n"

        prompt = f"""
        Jesteś recepcjonistką w "{salon_name}".
        Cel: {campaign_goal}.
        Napisz {len(batch)} SMS-ów.
        
        LISTA:
        {list_txt}
        
        ZASADY:
        1. Rozdziel wiadomości znakiem "|||".
        2. Użyj imienia w wołaczu.
        3. Bez polskich znaków.
        4. Podpisz się: {salon_name}.
        """
        
        try:
            resp = model.generate_content(prompt)
            msgs = resp.text.strip().split("|||")
            while len(msgs) < len(batch): msgs.append(f"Czesc! Zapraszamy do {salon_name}.")
        except:
            msgs = [f"Czesc {c['imie']}! Zapraszamy do {salon_name}." for c in batch]

        # 2. Wysyłka + Zapis do Raportu
        for j, person in enumerate(batch):
            if j < len(msgs):
                content = usun_ogonki(msgs[j].strip())
                status = "✅ Wysłano"
                
                if is_test_mode:
                    status = "🧪 Symulacja"
                    time.sleep(0.2)
                else:
                    try:
                        client.sms.send(to=str(person['telefon']), message=content)
                    except Exception as e:
                        status = f"❌ Błąd: {e}"
                
                # DODAJEMY DO RAPORTU
                raport_lista.append({
                    "Klientka": person['imie'],
                    "Telefon": person['telefon'],
                    "Treść SMS": content,
                    "Status": status
                })
        
        prog = min((i + BATCH_SIZE) / total, 1.0)
        progress_bar.progress(prog)
        time.sleep(1)

    status_text.empty()
    st.balloons()
    
    # --- WYŚWIETLENIE RAPORTU ---
    st.success("🎉 Kampania zakończona! Oto pełny raport:")
    
    if raport_lista:
        df_raport = pd.DataFrame(raport_lista)
        st.dataframe(
            df_raport, 
            use_container_width=True,
            column_config={
                "Treść SMS": st.column_config.TextColumn("Wysłana Treść", width="large"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            }
        )
    else:
        st.error("Coś poszło nie tak - brak raportu.")

# --- 4. LOGOWANIE ---
if not st.session_state['user']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("💅 Beauty SaaS")
        t1, t2 = st.tabs(["Logowanie", "Rejestracja"])
        with t1:
            e = st.text_input("Email", key="l1")
            p = st.text_input("Hasło", type="password", key="l2")
            if st.button("Zaloguj", type="primary"): login_user(e, p)
        with t2:
            e = st.text_input("Email", key="r1")
            p = st.text_input("Hasło", type="password", key="r2")
            if st.button("Załóż konto"): register_user(e, p)
    st.stop()

# --- 5. APLIKACJA ---
USER = st.session_state['user']
SALON_ID = USER.id 
USER_EMAIL = CURRENT_USER = USER.email

with st.sidebar:
    st.write(f"Zalogowano: {USER_EMAIL}")
    if st.button("Wyloguj"): logout_user()
    st.divider()

def add_client(imie, telefon, zabieg, data):
    cl = ''.join(filter(str.isdigit, str(telefon)))
    dv = str(data) if data and str(data).strip() != "" else None
    try:
        supabase.table("klientki").insert({
            "salon_id": SALON_ID, "imie": str(imie), "telefon": cl,
            "ostatni_zabieg": str(zabieg), "data_wizyty": dv
        }).execute()
        return True, ""
    except Exception as e: return False, str(e)

def get_clients():
    try:
        res = supabase.table("klientki").select("*").eq("salon_id", SALON_ID).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def delete_client(cid):
    try: supabase.table("klientki").delete().eq("id", cid).eq("salon_id", SALON_ID).execute()
    except: pass

st.title("Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

if page == "📂 Baza Klientek":
    st.header("Baza Klientek")
    with st.expander("📥 Import z telefonu"):
        f = st.file_uploader("Plik", type=['xlsx','csv','vcf'])
        if f:
            try:
                df = None
                if f.name.endswith('.vcf'): df = parse_vcf(f.getvalue())
                elif f.name.endswith('.csv'): df = pd.read_csv(f)
                else: df = pd.read_excel(f)
                
                if df is not None and not df.empty:
                    df.columns = [c.lower() for c in df.columns]
                    ci = next((c for c in df.columns if 'imi' in c or 'name' in c), None)
                    ct = next((c for c in df.columns if 'tel' in c or 'num' in c), None)
                    if ci and ct:
                        sh = pd.DataFrame({"Dodaj": True, "Imię": df[ci], "Telefon": df[ct], "Ostatni Zabieg": "Nieznany"})
                        ed = st.data_editor(sh, hide_index=True, use_container_width=True, column_config={"Dodaj": st.column_config.CheckboxColumn("Import?", default=True)})
                        to_add = ed[ed["Dodaj"]==True]
                        cnt = len(to_add)
                        if st.button(f"✅ ZAPISZ {cnt}"):
                            bar = st.progress(0.0)
                            ok = 0
                            for i, (idx, r) in enumerate(to_add.iterrows()):
                                s, m = add_client(r["Imię"], r["Telefon"], r["Ostatni Zabieg"], None)
                                if s: ok += 1
                                bar.progress(min((i+1)/cnt, 1.0))
                            st.success(f"Zapisano {ok}!")
                            time.sleep(1)
                            st.rerun()
            except: st.error("Błąd pliku")

    df = get_clients()
    if not df.empty:
        st.dataframe(df[['imie','telefon','ostatni_zabieg']], use_container_width=True)
        d = df.set_index('id')['imie'].to_dict()
        dd = st.selectbox("Usuń:", options=d.keys(), format_func=lambda x: d[x])
        if st.button("Usuń"): delete_client(dd); st.rerun()
    else: st.info("Pusto.")

elif page == "🤖 Automat SMS":
    st.header("Kampania SMS")
    df = get_clients()
    if df.empty: st.warning("Brak klientek.")
    else:
        st.write("### Konfiguracja")
        salon = st.text_input("Nazwa Salonu:", value=st.session_state.get('salon_name', ''))
        st.session_state['salon_name'] = salon
        cel = st.text_input("Cel (np. Promocja):")
        wyb = st.multiselect("Do kogo?", df['imie'].tolist(), default=df['imie'].tolist())
        target = df[df['imie'].isin(wyb)]
        
        if salon and not target.empty:
            st.info(f"Odbiorcy: {len(target)}")
            mode = st.radio("Tryb:", ["🧪 Test", "💸 Produkcja"])
            is_test = (mode == "🧪 Test")
            
            if st.button("🚀 URUCHOM KAMPANIĘ", type="primary"):
                send_campaign_batch_with_report(target, cel, salon, is_test)


