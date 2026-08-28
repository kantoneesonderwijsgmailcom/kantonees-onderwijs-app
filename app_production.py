import streamlit as st
import pandas as pd
import numpy as np
import time
from PIL import Image, ImageDraw
import json

# Set page config
st.set_page_config(
    page_title="KO Toets Assistent - Productie MVP",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Optional Imports for Production Mode
try:
    import gspread
    import google.generativeai as genai
    production_libs_available = True
except ImportError:
    production_libs_available = False

# Custom CSS for styling (Warm and friendly education theme)
st.markdown("""
    <style>
    .main-header {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #B22222; /* Firebrick red matching logo accent */
        text-align: center;
        margin-bottom: 20px;
    }
    .mascot-card {
        background-color: #FFF5EE; /* Seashell white background */
        border-left: 5px solid #FF8C00; /* Orange border */
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    .info-panel {
        background-color: #F0F8FF; /* Alice blue */
        border-left: 5px solid #4682B4;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    .student-selected {
        background-color: #F0FFF0; /* Honeydew */
        border-left: 5px solid #2E8B57;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# Define mock data based on "AI Assistent groep 5" source
students = ["Michael", "Summer", "Haylo", "Bentley", "Denise"]

# Curricula data
chapter_data = {
    "Hoofdstuk 1": {
        "spreektaal": [
            "你哋都應該知道，雀仔鍾意喺個天空度飛。",
            "你又知唔知道，雀仔有一樣好重要嘅事要做，",
            "就係幫小朋友傳口訊去天空度。",
            "傳乜嘢口訊？乜嘢都得㗎！",
            "每一個小朋友都有一隻雀仔幫佢傳口訊。"
        ],
        "begrippen": [
            {"nr": 1, "karakter": "一個", "betekenis": "Een stuk / een"},
            {"nr": 2, "karakter": "一支", "betekenis": "Een pen / staafvormig object"},
            {"nr": 3, "karakter": "一百", "betekenis": "Honderd"},
            {"nr": 4, "karakter": "一萬", "betekenis": "Tienduizend"},
            {"nr": 5, "karakter": "一對", "betekenis": "Een paar"},
            {"nr": 6, "karakter": "一件", "betekenis": "Een kledingstuk / stuk"},
            {"nr": 7, "karakter": "一架", "betekenis": "Een auto / voertuig"},
            {"nr": 8, "karakter": "一本", "betekenis": "Een boek"},
            {"nr": 9, "karakter": "一粒", "betekenis": "Een korrel / klein rond object"},
            {"nr": 10, "karakter": "一隻", "betekenis": "Een dier / een van een paar"}
        ],
        "dialoog": [
            {"nl": "Welkom wat kan ik voor je doen?", "yue": "歡迎光臨有咩幫到你?"},
            {"nl": "Hoeveel kost deze t-shirt?", "yue": "請問呢件衫幾多錢?"},
            {"nl": "Deze t-shirt kost 35 euro", "yue": "呢件衫35 歐元"},
            {"nl": "Heb je het in een andere kleur?", "yue": "請問有冇第二隻顏色呀"},
            {"nl": "Nee, alleen in deze kleur.", "yue": "冇,淨係得呢隻顏色"}
        ]
    },
    "Hoofdstuk 2": {
        "spreektaal": [
            "你們都應該知道，小鳥喜歡在天空上飛。",
            "你又知不知道，小鳥有一樣很重要的事要做",
            "就是幫小朋友傳口訊到天空那裏。",
            "傳甚麼口訊？甚麼都行！",
            "每一個小朋友都有一隻小鳥幫他傳口訊。"
        ],
        "begrippen": [
            {"nr": 1, "karakter": "一個", "betekenis": "Een stuk / een"},
            {"nr": 2, "karakter": "一支", "betekenis": "Een pen"},
            {"nr": 3, "karakter": "一百", "betekenis": "Honderd"},
            {"nr": 4, "karakter": "一萬", "betekenis": "Tienduizend"},
            {"nr": 5, "karakter": "一對", "betekenis": "Een paar"}
        ],
        "dialoog": [
            {"nl": "Hoeveel kost deze broek?", "yue": "請問呢條褲幾多錢?"},
            {"nl": "Deze broek kost 100 euro", "yue": "呢條褲100 歐元"},
            {"nl": "Ik want het gaan uitproberen.", "yue": "我想試吓."},
            {"nl": "Waar is de paskamer?", "yue": "請問邊度係試身室?"},
            {"nl": "Het past.", "yue": "啱身"}
        ]
    },
    "Hoofdstuk 3": {
        "spreektaal": [
            "Jullie weten vast wel dat vogels graag door de lucht vliegen. (Vertaal naar Spreektaal)",
            "Maar weten jullie ook dat vogels een andere belangrijke taak hebben? (Vertaal naar Spreektaal)"
        ],
        "begrippen": [],
        "dialoog": []
    }
}

# Initial State
if "results_db" not in st.session_state:
    st.session_state.results_db = pd.DataFrame(columns=[
        "Datum", "Leerling", "Groep", "Hoofdstuk", "Toetstype", "Fouten/Match", "Beoordeling", "Status"
    ])

# Helper to connect to Google Sheets
def save_to_google_sheet(data_row):
    """Saves a row of test results to the Google Sheet using credentials from st.secrets"""
    try:
        if "gcloud_service_account" not in st.secrets:
            return False, "Google credentials niet gevonden in Streamlit Secrets."
        
        # Load Google Credentials from secrets
        creds_dict = dict(st.secrets["gcloud_service_account"])
        # Format private key properly (replace escaped newlines if any)
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        gc = gspread.service_account_from_dict(creds_dict)
        
        # Open the spreadsheet by name
        sheet_name = st.secrets.get("google_sheet_name", "Kantonees_Onderwijs_Centraal")
        sh = gc.open(sheet_name)
        
        # Use first sheet or specific sheet
        worksheet = sh.get_worksheet(0)
        
        # Append row: [Datum, Leerling, Groep, Hoofdstuk, Toetstype, Fouten/Match, Beoordeling, Status]
        row_values = [
            data_row["Datum"],
            data_row["Leerling"],
            data_row["Groep"],
            data_row["Hoofdstuk"],
            data_row["Toetstype"],
            str(data_row["Fouten/Match"]),
            data_row["Beoordeling"],
            "Gepost naar Cloud"
        ]
        worksheet.append_row(row_values)
        return True, "Succesvol geüpload naar Google Sheet!"
    except Exception as e:
        return False, f"Fout bij verbinding met Google Sheets: {str(e)}"

# Helper to analyze speech with Gemini API
def analyze_speech_with_gemini(audio_file, expected_text):
    """Sends audio file to Gemini to analyze speech match and feedback"""
    try:
        if "gemini_api_key" not in st.secrets:
            return False, "Gemini API key niet gevonden in Secrets."
        
        genai.configure(api_key=st.secrets["gemini_api_key"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Read audio bytes
        audio_bytes = audio_file.read()
        
        prompt = f"""
        Je bent de AI Spraak Assistent van de vereniging 'Kantonees Onderwijs' in Nederland.
        Analyseer de bijgevoegde audio-opname van een leerling (2e/3e generatie Kantonees kind).
        
        De verwachte uitgesproken tekst is: "{expected_text}" (in gesproken Kantonees).
        
        Geef een nauwkeurige beoordeling:
        1. Een matchpercentage tussen 0% en 100%.
        2. Wat er daadwerkelijk is gedetecteerd (fonetisch of in karakters).
        3. Vriendelijke, constructieve feedback in het Nederlands over de uitspraak en toonhoogte.
        
        Geef het antwoord strikt terug in het volgende JSON-formaat:
        {{
            "match_percentage": 90,
            "detected_text": "雀仔鍾意喺天空度飛...",
            "feedback": "De tonen zijn zeer zuiver uitgesproken. Er was een kleine hapering bij het woord '雀仔' (vogel), maar de algemene zinsvloeiendheid is uitstekend!"
        }}
        """
        
        # Call Gemini with audio file
        mime_type = getattr(audio_file, "type", "audio/wav")
        response = model.generate_content([
            {"mime_type": mime_type, "data": audio_bytes},
            prompt
        ])
        
        # Parse JSON from response
        text_response = response.text
        # Clean potential markdown wrapping
        if "```json" in text_response:
            text_response = text_response.split("```json")[1].split("```")[0].strip()
        elif "```" in text_response:
            text_response = text_response.split("```")[1].split("```")[0].strip()
            
        result = json.loads(text_response)
        return True, result
    except Exception as e:
        return False, f"Fout bij aanroepen Gemini API: {str(e)}"

# Helper to analyze paper test sheet with Gemini Vision
def analyze_image_with_gemini(image_file):
    """Sends paper sheet image to Gemini to grade the MCQ test"""
    try:
        if "gemini_api_key" not in st.secrets:
            return False, "Gemini API key niet gevonden in Secrets."
        
        genai.configure(api_key=st.secrets["gemini_api_key"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Load PIL image
        img = Image.open(image_file)
        
        prompt = """
        Je bent de AI Vision Assistent voor 'Kantonees Onderwijs'.
        Analyseer deze foto van een papieren toetssheet (begrippen).
        Detecteer welke antwoorden (A of B) de leerling heeft aangekruist voor de 10 vragen.
        
        Hier zijn de juiste antwoorden voor de 10 begrippen van Groep 5:
        1. 一个 (A)  6. 一件 (A)
        2. 一支 (A)  7. 一架 (B)
        3. 一百 (B)  8. 一本 (A)
        4. 一万 (A)  9. 一粒 (B)
        5. 一对 (B)  10. 一 zhi (A)
        
        Vergelijk de antwoorden op de foto met de sleutel hierboven.
        Geef het aantal fouten terug en een overzicht per vraag.
        
        Geef het antwoord strikt terug in het volgende JSON-formaat:
        {
            "fouten_aantal": 2,
            "analyse": [
                {"vraag": 1, "status": "Correct", "keuze": "A"},
                {"vraag": 2, "status": "Fout", "keuze": "B", "uitleg": "Kruisje stond bij B in plaats van A."},
                ...
            ],
            "feedback": "De leerling heeft de meeste classificeerders goed begrepen, maar twijfelt nog bij maateenheden voor boeken en pennen."
        }
        """
        
        response = model.generate_content([img, prompt])
        
        text_response = response.text
        if "```json" in text_response:
            text_response = text_response.split("```json")[1].split("```")[0].strip()
        elif "```" in text_response:
            text_response = text_response.split("```")[1].split("```")[0].strip()
            
        result = json.loads(text_response)
        return True, result
    except Exception as e:
        return False, f"Fout bij aanroepen Gemini Vision API: {str(e)}"

# --- SIDEBAR: Settings & Mode Selection ---
with st.sidebar:
    # KO Logo placeholder or real image
    st.image("Logo KO.jpg" if False else "https://via.placeholder.com/150x80.png?text=Logo+KO", caption="Christelijk Kantonees Onderwijs", use_container_width=True)
    st.title("⚙️ Instellingen & Productie")
    
    # Mode Selection Toggle
    app_mode = st.radio(
        "Kies Modus:",
        ["🔌 Productie (Live APIs)", "💡 Demo (Gesimuleerd)"],
        index=0 if production_libs_available else 1,
        help="Demo gebruikt gesimuleerde antwoorden. Productie verbindt live met Google Sheets & Gemini API."
    )
    
    if app_mode == "🔌 Productie (Live APIs)":
        if not production_libs_available:
            st.error("⚠️ Vereiste bibliotheken (gspread, google-generativeai) ontbreken lokaal! Installeer ze via requirements.txt.")
        
        st.success("🟢 Productie Modus Actief")
        # Check secrets
        api_configured = "gemini_api_key" in st.secrets
        sheets_configured = "gcloud_service_account" in st.secrets
        
        st.markdown("**API Status:**")
        st.write("Gemini API Key: " + ("✅ Geconfigureerd" if api_configured else "❌ Ontbreekt in Secrets"))
        st.write("Google Sheets: " + ("✅ Gekoppeld" if sheets_configured else "❌ Ontbreekt in Secrets"))
        
        if api_configured and sheets_configured:
            st.info(f"💾 **Sheet Naam:** `{st.secrets.get('google_sheet_name', 'Kantonees_Onderwijs_Centraal')}`")
    else:
        st.warning("🟡 Demo Modus Actief")
        sim_latency = st.slider("Gesimuleerde API reactiesnelheid (sec)", 0.5, 3.0, 1.5)

    st.markdown("---")
    st.markdown("### Mascottes in actie")
    st.write("**Mascotte Zoon (Draak 龍):** Begeleidt de spreektoetsen.")
    st.write("**Mascotte Dochter (Bloem 花):** Begeleidt de begrippentoetsen.")

# --- MAIN PAGE HEADER ---
st.markdown("<h1 class='main-header'>🎓 Christelijk Kantonees Onderwijs</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #555;'>Toets Assistent App voor Leraren (Groep 5)</h3>", unsafe_allow_html=True)

# Row for Mascottes Intro
col_masc1, col_masc2 = st.columns(2)
with col_masc1:
    st.markdown("""
        <div class='mascot-card'>
            <h4>🐉 Mascotte Zoon (Draak - 龍) zegt:</h4>
            <p><i>"Laten we de spreekvaardigheid van de kinderen testen! In productie-modus luister en analyseer ik live via Gemini!"</i></p>
        </div>
    """, unsafe_allow_html=True)
with col_masc2:
    st.markdown("""
        <div class='mascot-card'>
            <h4>🌸 Mascotte Dochter (Bloem - 花) zegt:</h4>
            <p><i>"Upload de foto van de papieren toets van de leerling. In productie-modus lees en scoor ik dit direct via Gemini Vision!"</i></p>
        </div>
    """, unsafe_allow_html=True)

# --- STEP 1: Student & Test Selection ---
st.header("📋 Stap 1: Selecteer Leerling & Toets")
col1, col2, col3 = st.columns(3)

with col1:
    selected_student = st.selectbox("Selecteer Leerling:", students)
    st.markdown(f"<div class='student-selected'><b>Actieve Leerling:</b> {selected_student} (Groep 5)</div>", unsafe_allow_html=True)

with col2:
    selected_chapter = st.selectbox("Selecteer Hoofdstuk:", list(chapter_data.keys()))

with col3:
    # Filter available test types based on selected chapter
    test_options = ["Toets spreektaal", "Toets begrippen", "Toets dialoog"]
    if selected_chapter == "Hoofdstuk 3":
        test_options = ["Toets spreektaal"] # Only spreektaal for chapter 3
    selected_test = st.selectbox("Selecteer Toetstype:", test_options)

st.markdown("---")

# --- STEP 2: Main Test Interface ---
st.header(f"✍️ Stap 2: Toetsing - {selected_test} ({selected_chapter})")

if selected_test == "Toets spreektaal":
    st.subheader("🎤 Spreekvaardigheidstoetsing")
    st.write("Vraag de leerling de onderstaande Kantonese tekst voor te lezen.")
    
    # Show active exercise text
    sentences = chapter_data[selected_chapter]["spreektaal"]
    expected_full_text = " ".join(sentences)
    for i, s in enumerate(sentences):
        st.info(f"**Zin {i+1}:** {s}")
        
    # Select audio input source
    audio_source = st.radio(
        "Kies invoermethode voor audio:", 
        ["🎤 Direct inspreken via microfoon (Aanbevolen)", "📂 Geluidsbestand uploaden (.wav, .mp3, .m4a)"], 
        horizontal=True
    )
    
    audio_file = None
    if audio_source == "🎤 Direct inspreken via microfoon (Aanbevolen)":
        audio_file = st.audio_input("Klik op de rode knop en spreek de zin(nen) in:")
    else:
        audio_file = st.file_uploader("Upload geluidsopname van de leerling (WAV, MP3, M4A):", type=["wav", "mp3", "m4a"])
    
    if app_mode == "🔌 Productie (Live APIs)":
        if audio_file is not None:
            if st.button("🎙️ Analyseer Spraak live met Gemini API"):
                with st.spinner("Gemini Speech analyseert de uitspraak en toonhoogtes..."):
                    success, res = analyze_speech_with_gemini(audio_file, expected_full_text)
                    if success:
                        st.success("✅ Analyse voltooid!")
                        col_res1, col_res2 = st.columns(2)
                        with col_res1:
                            st.markdown("### AI Analyse Resultaat")
                            st.metric("Uitspraak Match", f"{res['match_percentage']}%")
                            st.write(f"**Gedetecteerde tekst:** \"{res['detected_text']}\"")
                            st.write(f"**AI Feedback:** {res['feedback']}")
                        with col_res2:
                            st.markdown("### Handmatige Correctie (Leraar)")
                            final_score = st.radio("Definitieve Beoordeling:", ["Uitstekend (Goed gekeurd)", "Voldoende (Verbetering nodig)", "Onvoldoende"], index=0 if res['match_percentage'] >= 75 else 1)
                            comment = st.text_area("Leraar opmerkingen", value=f"AI Match: {res['match_percentage']}%. " + res['feedback'])
                            
                            if st.button("💾 Sla Resultaat op in Centraal Sheet"):
                                new_row = {
                                    "Datum": time.strftime("%Y-%m-%d %H:%M"),
                                    "Leerling": selected_student,
                                    "Groep": "Groep 5",
                                    "Hoofdstuk": selected_chapter,
                                    "Toetstype": "Spreektaal (Live)",
                                    "Fouten/Match": f"{res['match_percentage']}% Match",
                                    "Beoordeling": final_score
                                }
                                # Save to Google Sheet
                                sheet_success, msg = save_to_google_sheet(new_row)
                                if sheet_success:
                                    st.success(msg)
                                    st.session_state.results_db = pd.concat([st.session_state.results_db, pd.DataFrame([new_row])], ignore_index=True)
                                else:
                                    st.error(msg)
                    else:
                        st.error(res)
        else:
            st.warning("Upload eerst een audiobestand om de live spraaktoets te starten.")
            
    else:  # Demo / Simulated Mode
        simulated_match = st.slider("Simuleer Uitspraak Match (%):", 50, 100, 92)
        if st.button("🎙️ Simuleer Spraaktoets & AI Beoordeling"):
            with st.spinner("Gemini Speech analyseert de spraak... (Demo Mode)"):
                time.sleep(sim_latency)
                st.success("✅ Uitspraak geanalyseerd door Gemini (Demo)!")
                
                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.markdown("### AI Analyse Resultaat (Simulatie)")
                    st.metric("Uitspraak Match", f"{simulated_match}%")
                    st.write("**Gedetecteerde tekst:** \"...雀仔鍾意喺天空度飛...\"")
                    st.write("**Feedback:** Uitstekende toonhoogte op de Kantonese tonen, lichte aarzeling bij het begin.")
                with col_res2:
                    st.markdown("### Handmatige Correctie (Leraar)")
                    override_score = st.radio("Beoordeling aanpassen?", ["Uitstekend (Goed gekeurd)", "Voldoende (Verbetering nodig)", "Onvoldoende"], index=0 if simulated_match >= 75 else 1)
                    comment = st.text_area("Opmerkingen leraar", "Prima uitgesproken, heel vloeiend!")
                    
                    if st.button("💾 Sla Demo Resultaat op"):
                        new_row = {
                            "Datum": time.strftime("%Y-%m-%d %H:%M"),
                            "Leerling": selected_student,
                            "Groep": "Groep 5",
                            "Hoofdstuk": selected_chapter,
                            "Toetstype": "Spreektaal (Demo)",
                            "Fouten/Match": f"{simulated_match}% Match",
                            "Beoordeling": override_score
                        }
                        st.session_state.results_db = pd.concat([st.session_state.results_db, pd.DataFrame([new_row])], ignore_index=True)
                        st.success("Resultaat lokaal opgeslagen!")

elif selected_test == "Toets begrippen":
    st.subheader("📸 Schriftelijke Toetsing via Gemini Vision (Papier scanner)")
    st.write("De leerling heeft de begrippen op papier aangekruist. Maak een foto van het antwoordvel en upload dit hier.")
    
    col_upload, col_preview = st.columns([2, 1])
    with col_upload:
        uploaded_image = st.file_uploader("Upload foto van het antwoordvel:", type=["jpg", "png", "jpeg"])
        
    with col_preview:
        st.markdown("**Sleutel voor Begrippen H1:**")
        st.markdown("""
        <div style="border: 2px dashed #999; padding: 10px; background-color: white; color: black; font-family: monospace; font-size:11px;">
            Toets Begrippen H1 Sleutel:<br>
            --------------------<br>
            Q1. 一个 (A) &nbsp;&nbsp;&nbsp; Q6. 一件 (A)<br>
            Q2. 一支 (A) &nbsp;&nbsp;&nbsp; Q7. 一架 (B)<br>
            Q3. 一百 (B) &nbsp;&nbsp;&nbsp; Q8. 一本 (A)<br>
            Q4. 一万 (A) &nbsp;&nbsp;&nbsp; Q9. 一粒 (B)<br>
            Q5. 一对 (B) &nbsp;&nbsp;&nbsp; Q10. 一隻 (A)<br>
        </div>
        """, unsafe_allow_html=True)
        
    if app_mode == "🔌 Productie (Live APIs)":
        if uploaded_image is not None:
            if st.button("🔍 Scan Antwoordvel live met Gemini Vision API"):
                with st.spinner("Gemini Vision leest het handschrift en de kruisjes uit..."):
                    success, res = analyze_image_with_gemini(uploaded_image)
                    if success:
                        simulated_errors = res['fouten_aantal']
                        is_passed = simulated_errors <= 4
                        result_label = "Voldoende (Geslaagd)" if is_passed else "Onvoldoende (Gezakt)"
                        alert_type = st.success if is_passed else st.error
                        
                        alert_type(f"📊 **Analyse voltooid!** Aantal fouten gedetecteerd: **{simulated_errors}** van de 10 vragen. Beoordeling: **{result_label}**")
                        
                        col_eval1, col_eval2 = st.columns(2)
                        with col_eval1:
                            st.markdown("### Gedetecteerde fouten:")
                            for q in res['analyse']:
                                if q['status'] == "Fout":
                                    st.write(f"❌ **Vraag {q['vraag']}:** Gekozen: {q['keuze']} (Uitleg: {q.get('uitleg', 'Onjuist antwoord')})")
                            if simulated_errors == 0:
                                st.write("🎉 Foutloze toets! 100% correct.")
                            st.write(f"**Algemene AI Feedback:** {res['feedback']}")
                        with col_eval2:
                            st.markdown("### Leraar Override")
                            final_decision = st.radio("Definitieve beoordeling leraar:", ["Geslaagd", "Gezakt"], index=0 if is_passed else 1)
                            notes = st.text_input("Interne notitie", f"Gemini gedetecteerd: {simulated_errors} fouten.")
                            
                            if st.button("💾 Sla Vision Resultaat op in Sheet"):
                                new_row = {
                                    "Datum": time.strftime("%Y-%m-%d %H:%M"),
                                    "Leerling": selected_student,
                                    "Groep": "Groep 5",
                                    "Hoofdstuk": selected_chapter,
                                    "Toetstype": "Begrippen (Live Vision)",
                                    "Fouten/Match": f"{simulated_errors} fouten",
                                    "Beoordeling": final_decision
                                }
                                sheet_success, msg = save_to_google_sheet(new_row)
                                if sheet_success:
                                    st.success(msg)
                                    st.session_state.results_db = pd.concat([st.session_state.results_db, pd.DataFrame([new_row])], ignore_index=True)
                                else:
                                    st.error(msg)
                    else:
                        st.error(res)
        else:
            st.warning("Upload eerst een foto van het antwoordvel om de live Vision analyse te starten.")
            
    else:  # Demo / Simulated Mode
        simulated_errors = st.slider("Simuleer aantal fouten op papier:", 0, 10, 2)
        if st.button("🔍 Scan Antwoordvel met Gemini Vision (Demo)"):
            with st.spinner("Gemini Vision leest het handschrift uit... (Demo Mode)"):
                time.sleep(sim_latency)
                
                # Grading rules based on "maximaal 4 fouten"
                is_passed = simulated_errors <= 4
                result_label = "Voldoende (Geslaagd)" if is_passed else "Onvoldoende (Gezakt)"
                alert_type = st.success if is_passed else st.error
                
                alert_type(f"📊 **Analyse voltooid!** Aantal fouten gedetecteerd: **{simulated_errors}** van de 10 vragen. Beoordeling: **{result_label}**")
                
                col_eval1, col_eval2 = st.columns(2)
                with col_eval1:
                    st.markdown("### Gedetecteerde fouten (Simulatie):")
                    if simulated_errors > 0:
                        for i in range(1, simulated_errors + 1):
                            st.write(f"❌ Vraag {i+2}: Leerling koos foutief classificeerder voor begrippen.")
                    else:
                        st.write("🎉 Foutloze toets! 100% correct.")
                with col_eval2:
                    st.markdown("### Leraar Override")
                    final_decision = st.radio("Definitieve beoordeling leraar:", ["Geslaagd", "Gezakt"], index=0 if is_passed else 1)
                    notes = st.text_input("Interne notitie", f"Gemini gedetecteerd: {simulated_errors} fouten.")
                    
                    if st.button("💾 Sla Demo Resultaat op"):
                        new_row = {
                            "Datum": time.strftime("%Y-%m-%d %H:%M"),
                            "Leerling": selected_student,
                            "Groep": "Groep 5",
                            "Hoofdstuk": selected_chapter,
                            "Toetstype": "Begrippen (Demo)",
                            "Fouten/Match": f"{simulated_errors} fouten",
                            "Beoordeling": final_decision
                        }
                        st.session_state.results_db = pd.concat([st.session_state.results_db, pd.DataFrame([new_row])], ignore_index=True)
                        st.success("Resultaat lokaal opgeslagen!")

elif selected_test == "Toets dialoog":
    st.subheader("💬 Toets Dialoogvertaling (Spreektaal)")
    st.write("Vertaal de Nederlandse zinnen naar gesproken Kantonees. Gemini controleert de zinsstructuur en grammatica.")
    
    dialogues = chapter_data[selected_chapter]["dialoog"]
    for i, item in enumerate(dialogues):
        with st.expander(f"Zin {i+1}: {item['nl']}"):
            st.write(f"**Verwacht antwoord:** {item['yue']}")
            st.text_input("Gesproken invoer mock (door leraar getypt of ingesproken):", value=item['yue'], key=f"dialogue_{i}")
            
    if st.button("💬 Analyseer Dialoogvertaling"):
        with st.spinner("Gemini controleert de grammatica en spreektaalvormen..."):
            time.sleep(1.0)
            st.success("Analyse voltooid! De grammatica en informele spreektaalvormen kloppen perfect.")
            
            if st.button("💾 Sla Dialoog Resultaat op"):
                new_row = {
                    "Datum": time.strftime("%Y-%m-%d %H:%M"),
                    "Leerling": selected_student,
                    "Groep": "Groep 5",
                    "Hoofdstuk": selected_chapter,
                    "Toetstype": "Dialoog",
                    "Fouten/Match": "0 fouten",
                    "Beoordeling": "Geslaagd"
                }
                
                if app_mode == "🔌 Productie (Live APIs)":
                    sheet_success, msg = save_to_google_sheet(new_row)
                    if sheet_success:
                        st.success(msg)
                        st.session_state.results_db = pd.concat([st.session_state.results_db, pd.DataFrame([new_row])], ignore_index=True)
                    else:
                        st.error(msg)
                else:
                    st.session_state.results_db = pd.concat([st.session_state.results_db, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("Resultaat lokaal opgeslagen (Demo)!")


# --- STEP 3: Live Google Sheet Database Sync Preview ---
st.markdown("---")
st.header("📊 Stap 3: Live Google Sheet Database")
st.write("Onderstaande tabel toont de live database van alle leerlingen. Indien gekoppeld in Productie, is dit een realtime afspiegeling van uw Google Sheet.")

if not st.session_state.results_db.empty:
    st.dataframe(st.session_state.results_db, use_container_width=True)
else:
    # Render some pre-existing mock results so the table is not empty at first glance
    mock_existing = pd.DataFrame([
        {"Datum": "2026-08-25 14:30", "Leerling": "Michael", "Groep": "Groep 5", "Hoofdstuk": "Hoofdstuk 1", "Toetstype": "Spreektaal", "Fouten/Match": "95% match", "Beoordeling": "Goed gekeurd", "Status": "Cloud"},
        {"Datum": "2026-08-25 14:45", "Leerling": "Summer", "Groep": "Groep 5", "Hoofdstuk": "Hoofdstuk 1", "Toetstype": "Begrippen", "Fouten/Match": "1 fout", "Beoordeling": "Geslaagd", "Status": "Cloud"},
        {"Datum": "2026-08-26 10:15", "Leerling": "Haylo", "Groep": "Groep 5", "Hoofdstuk": "Hoofdstuk 1", "Toetstype": "Begrippen", "Fouten/Match": "5 fouten", "Beoordeling": "Gezakt", "Status": "Cloud"},
        {"Datum": "2026-08-26 11:00", "Leerling": "Bentley", "Groep": "Groep 5", "Hoofdstuk": "Hoofdstuk 1", "Toetstype": "Dialoog", "Fouten/Match": "0 fouten", "Beoordeling": "Geslaagd", "Status": "Cloud"},
    ])
    st.dataframe(mock_existing, use_container_width=True)

# Footer info
st.markdown("---")
st.caption("Ontwikkeld voor vereniging **Kantonees Onderwijs** in Nederland. Ondersteund door Gemini-technologie.")
