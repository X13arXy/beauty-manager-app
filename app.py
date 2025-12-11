import streamlit as st
import pandas as pd
import time
from supabase import create_client, Client

# Import naszych modułów
import database as db
import utils

# --- KONFIGURACJA ---
st.set_page_config(page_title="Beauty SaaS", page_icon="💅", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .element-container { margin-bottom: 0.5rem; }
    /* Ładniejszy wygląd logów */
    .stCode { font-family: 'Courier New', monospace; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# Import SMSAPI
try:
    from smsapi.client import SmsApiPlClient
except ImportError:
    pass

# --- STAN SESJI ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'salon_name' not in st.session_state: st.session_state['salon_name'] = ""
if 'preview_messages' not in st.session_state: st.session_state['preview_messages'] = None

# --- LOGOWANIE ---
if not st.session_state['user']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("💅 Beauty SaaS")
        t1, t2 = st.tabs(["Logowanie", "Rejestracja"])
        with t1:
            e = st.text_input("Email", key="l1")
            p = st.text_input("Hasło", type="password", key="l2")
            if st.button("Zaloguj", type="primary"): db.login_user(e, p)
        with t2:
            e = st.text_input("Email", key="r1")
            p = st.text_input("Hasło", type="password", key="r2")
            if st.button("Załóż konto"): db.register_user(e, p)
    st.stop()

# --- APLIKACJA ---
USER = st.session_state['user']
SALON_ID = USER.id 
USER_EMAIL = USER.email

with st.sidebar:
    st.write(f"Zalogowano: {USER_EMAIL}")
    if st.button("Wyloguj"): db.logout_user()
    st.divider()

st.title("Panel Salonu")
page = st.sidebar.radio("Menu", ["📂 Baza Klientek", "🤖 Automat SMS"])

# 📂 BAZA KLIENTEK (IMPORT)
if page == "📂 Baza Klientek":
    st.header("Baza Klientek")
    with st.expander("📥 Import z telefonu"):
        f = st.file_uploader("Plik (VCF/Excel)", type=['xlsx','csv','vcf'])
        if f:
            try:
                df = None
                if f.name.endswith('.vcf'): df = utils.parse_vcf(f.getvalue())
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
                                s, m = db.add_client(SALON_ID, r["Imię"], r["Telefon"], r["Ostatni Zabieg"], None)
                                if s: ok += 1
                                bar.progress(min((i+1)/cnt, 1.0))
                            st.success(f"Zapisano {ok}!")
                            time.sleep(1)
                            st.rerun()
            except: st.error("Błąd pliku")

    data = db.get_clients(SALON_ID)
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df[['imie','telefon','ostatni_zabieg']], use_container_width=True)
        d = df.set_index('id')['imie'].to_dict()
        dd = st.selectbox("Usuń:", options=d.keys(), format_func=lambda x: d[x])
        if st.button("Usuń"): db.delete_client(dd, SALON_ID); st.rerun()
    else: st.info("Pusto.")

# 🤖 AUTOMAT SMS (RELACYJNY)
elif page == "🤖 Automat SMS":
    st.header("Generator SMS AI (Personalizowany)")
    data = db.get_clients(SALON_ID)
    
    if not data:
        st.warning("Brak klientek.")
    else:
        df = pd.DataFrame(data)
        
        c1, c2 = st.columns(2)
        salon = c1.text_input("Nazwa Salonu:", value=st.session_state.get('salon_name', ''))
        st.session_state['salon_name'] = salon
        cel = c2.text_input("Co chcesz przekazać? (np. Zaproszenie na kawę):")
        
        wyb = st.multiselect("Do kogo?", df['imie'].tolist(), default=df['imie'].tolist())
        target = df[df['imie'].isin(wyb)]
        id_col = 'id' if 'id' in target.columns else None
        selection_signature = sorted(target[id_col].tolist()) if id_col else sorted(target.index.tolist())
        preview_state = st.session_state.get('preview_messages')
        preview_valid = (
            preview_state
            and preview_state.get("generated_for") == selection_signature
            and preview_state.get("salon") == salon
            and preview_state.get("goal") == cel
        )

        st.info(f"Wybrano {len(target)} osób. AI wygeneruje UNIKALNĄ treść dla każdej z nich.")
        mode = st.radio("Tryb:", ["🧪 Test (Symulacja)", "💸 Produkcja (Płatny SMSAPI)"])
        is_test = (mode == "🧪 Test (Symulacja)")

        if st.button("📄 GENERUJ PODGLĄD", type="secondary"):
            preview_msgs = []
            for idx, row in target.iterrows():
                with st.spinner(f"AI pisze do: {row['imie']}..."):
                    msg = utils.generate_single_message(salon, cel, row['imie'], row['ostatni_zabieg'])
                row_id = row["id"] if id_col else idx
                preview_msgs.append({
                    "id": row_id,
                    "imie": row["imie"],
                    "telefon": row["telefon"],
                    "message": msg
                })
            st.session_state['preview_messages'] = {
                "generated_for": selection_signature,
                "salon": salon,
                "goal": cel,
                "messages": preview_msgs
            }
            preview_state = st.session_state['preview_messages']
            preview_valid = True

        if preview_state:
            if preview_valid:
                st.subheader("📄 Podgląd wiadomości")
                for entry in preview_state["messages"]:
                    with st.chat_message("assistant"):
                        st.write(f"**Do: {entry['imie']}** ({entry['telefon']})")
                        st.code(entry["message"], language='text')
                st.success("Podgląd aktualny. Możesz wysłać.")
            else:
                st.info("Podgląd nieaktualny po zmianach. Wygeneruj ponownie, aby wysłać.")

        if preview_valid and st.button("🚀 WYŚLIJ PODGLĄD (LIVE)", type="primary"):
            client = None
            if not is_test:
                token = st.secrets.get("SMSAPI_TOKEN", "")
                if not token:
                    st.error("Brak tokenu SMSAPI!")
                    st.stop()
                try:
                    client = SmsApiPlClient(access_token=token)
                except:
                    st.error("Błąd SMSAPI")
                    st.stop()

            st.write("---")
            st.subheader("📨 Podgląd wysyłki na żywo:")
            messages = preview_state["messages"]
            if not messages:
                st.warning("Brak wiadomości w podglądzie. Wygeneruj ponownie.")
            else:
                bar = st.progress(0.0)
                log_box = st.container()
                total = len(messages)
                for i, entry in enumerate(messages):
                    msg = entry["message"]
                    with log_box:
                        with st.chat_message("assistant"):
                            st.write(f"**Do: {entry['imie']}** ({entry['telefon']})")
                            st.code(msg, language='text')
                            if is_test:
                                st.caption("✅ Symulacja OK")
                            else:
                                try:
                                    client.sms.send(to=str(entry['telefon']), message=msg)
                                    st.caption("✅ Wysłano SMS")
                                except Exception as e:
                                    st.error(f"Błąd wysyłki: {e}")
                    time.sleep(2)
                    bar.progress((i+1)/total)
                st.balloons()
                st.success("Zakończono!")
                st.session_state['preview_messages'] = None
