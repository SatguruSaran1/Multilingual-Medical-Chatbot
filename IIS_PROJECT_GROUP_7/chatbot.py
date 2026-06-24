import streamlit as st
import random
import ollama
import ast
from fpdf import FPDF
import spacy
import os
import time
from pymongo import MongoClient
from pymongo.encryption import Algorithm
import sounddevice as sd
import wave
import numpy as np
import requests
import base64
from deep_translator import GoogleTranslator
import queue
nlp = spacy.load("en_core_web_sm")

# Absolute path for the recorded audio file — used by both record() and speech_to_text()
WAV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_final.wav")

# Assuming MongoDB connection and encryption are passed from main.py
db_user = "satguru24510_db_user"
db_password = "LMNS2jNezvrNsU88"
uri = f"mongodb+srv://{db_user}:{db_password}@iis-grp-project-7-chatb.2pai8tl.mongodb.net/?retryWrites=true&w=majority&appName=IIS-GRP-PROJECT-7-CHATBOT"
try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')  # Test the connection early
    database_name = "encrypted_healthcare"
    db = client[database_name]
except Exception as _mongo_err:
    import streamlit as _st
    _st.error(f" Could not connect to MongoDB: {_mongo_err}\n\nCheck your internet connection and that your IP is whitelisted in MongoDB Atlas.")
    client = None
    db = None

def create_patient_entry(symptoms_list, demographic_list, medical_conditions):
    single_entry = {
        "DemographicData": {
            "Name": demographic_list[0],
            "Age": demographic_list[1],
            "Gender": demographic_list[2],
            "Location": demographic_list[3],
            "Contact": demographic_list[4],
            "MedicalConditions": medical_conditions
        },
        "SymptomsData": [],
        "username": st.session_state['username']
    }
    patient_name = demographic_list[0]
    symptoms_data = symptoms_list[0].get(patient_name, {})
    for symptom, details in symptoms_data.items():
        single_entry["SymptomsData"].append({
            "Symptom": symptom.capitalize(),
            "Severity": details["severity"],
            "Frequency": details["frequency"],
            "Duration": details["duration"],
            "Additional Notes": "N.A."
        })
    return single_entry

def translate(text,language):
    if language=="od":
        language="or"
    return GoogleTranslator(source='auto', target=language).translate(text)

def translate_list(text,language):
    if language=="od":
        language="or"
    text1=[]
    for i in text:
        i2=GoogleTranslator(source='auto', target=language).translate(i)
        text1.append(i2)
    return text1
def text_to_speech(text, language):
    api_key = os.getenv("sarvam")
    url = "https://api.sarvam.ai/text-to-speech"
    payload = {
        "inputs": [f"{text}"],
        "target_language_code": f"{language}-IN",
        "speaker": "meera",
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v1"
    }
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": api_key
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        response_data = response.json()
        if "audios" in response_data and response_data["audios"]:
            audio_base64 = response_data["audios"][0]
            audio_bytes = base64.b64decode(audio_base64)
            filename = "output.wav"
            with open(filename, "wb") as f:
                f.write(audio_bytes)
            
            # Play the saved WAV file
            try:
                # Read the WAV file
                with wave.open(filename, 'rb') as wf:
                    sample_rate = wf.getframerate()
                    channels = wf.getnchannels()
                    audio_data = wf.readframes(wf.getnframes())
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Play audio using sounddevice
                sd.play(audio_array, samplerate=sample_rate)
                sd.wait()  # Wait until playback is finished
                return True
            except Exception as e:
                print(f"Error playing audio: {e}")
                return False
    return False
def write_and_speak(text, language):
    if language != "en":
        if language=="od":
            language="or"
            translated_text = GoogleTranslator(source='auto', target=language).translate(text)
            st.write(translated_text)
            language="od"
            text_to_speech(translated_text, language)
        else:
            translated_text = GoogleTranslator(source='auto', target=language).translate(text)
            st.write(translated_text)
            text_to_speech(translated_text, language)
    else:
        st.write(text)
        text_to_speech(text, language)

def record(language):
    filename = WAV_PATH
    sample_rate = 44100
    channels = 1
    chunk_duration = 0.5  # Reduced for quicker detection
    max_silence_time = 2.0  # Reduced to react faster
    silence_threshold_multiplier = 1.8
    calibrate_seconds = 1.0
    chunk_samples = int(sample_rate * chunk_duration)
    silence_chunks_required = int(max_silence_time / chunk_duration)
    audio_q = queue.Queue()
    recorded_data = []
    silence_counter = 0
    recording_flag = [True]

    # === Ambient calibration (only once per session) ===
    if 'ambient_rms' not in st.session_state:
        ambient_noise = sd.rec(int(sample_rate * calibrate_seconds), samplerate=sample_rate, channels=channels, dtype='int16')
        sd.wait()
        st.session_state.ambient_rms = np.sqrt(np.mean(ambient_noise.astype(np.float32) ** 2))

    silence_threshold = st.session_state.ambient_rms * silence_threshold_multiplier

    def audio_callback(indata, frames, time, status):
        nonlocal silence_counter
        if status:
            print(f"Stream status: {status}")
        rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
        audio_q.put(indata.copy())

        if rms < silence_threshold:
            silence_counter += 1
        else:
            silence_counter = 0

        if silence_counter >= silence_chunks_required:
            recording_flag[0] = False

    with sd.InputStream(samplerate=sample_rate, channels=channels,
                        blocksize=chunk_samples, dtype='int16',
                        callback=audio_callback):
        write_and_speak("Please speak now", language)
        while recording_flag[0]:
            try:
                chunk = audio_q.get(timeout=1)
                recorded_data.append(chunk)
            except queue.Empty:
                pass

    # Save to WAV
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join([chunk.tobytes() for chunk in recorded_data]))
    return True

def speech_to_text():
    url = "https://api.sarvam.ai/speech-to-text-translate"
    api_key = os.getenv("sarvam")
    payload = {'model': 'saaras:v1', 'prompt': ''}
    files = [('file', ('output_final.wav', open(WAV_PATH, 'rb'), 'audio/wav'))]
    headers = {'api-subscription-key': api_key}
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    if response.status_code == 200:
        try:
            response_data = response.json()
            transcript = response_data.get('transcript')  # Use .get() to avoid KeyError
            return transcript if transcript else "None"
        except ValueError:
            print("Error: Invalid JSON response from API")
            return "None"
    else:
        print(f"Error: API request failed with status code {response.status_code}")
        return "None"
        

def detect_time_phrases(text):
    doc = nlp(text)
    time_phrases = [ent.text for ent in doc.ents if ent.label_ in ["DATE", "TIME"]]
    return time_phrases[0] if time_phrases else None

def extract_entities(sentence, entity_type):
    prompt = (
        f"Extract all {entity_type} explicitly mentioned in the following sentence and normalize them if needed. "
        "For example, map 'head is paining' to 'headache', 'high temperature' or 'high fever' to 'fever', etc. "
        "ONLY return a valid Python list. DO NOT include any explanations, introductions, or extra text. "
        "If no entities are found, return an empty list [].\n\n"
        f"Sentence: \"{sentence}\""
    )
    response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
    try:
        return ast.literal_eval(response['message']['content'])
    except (ValueError, SyntaxError):
        return []

def take_medical_terms(input_type,language, text_input=None):
    if input_type == "Voice":
        medical_voice = record(language)
        if medical_voice==True:
            medical_input =speech_to_text()
        else:
            medical_voice=record(language)    # at this part i can create a loop where if the number of times the user does not answer exceeds 2 times than i will start the option for text.
            medical_input =speech_to_text()
        if medical_input and medical_input != "None":
            return extract_entities(medical_input, 'medical term') or []
    elif input_type == "text" and text_input:
        return extract_entities(text_input, 'medical term') or []
    return []

def take_symptoms(input_type,language, text_input=None):
    if input_type == "Voice":
        symptoms_voice = record(language)
        if symptoms_voice==True:
            symptoms_input =speech_to_text()
        else:
            symptoms_voice=record(language)    # at this part i can create a loop where if the number of times the user does not answer exceeds 2 times than i will start the option for text.
            symptoms_input =speech_to_text()
        if symptoms_input and symptoms_input != "None":
            return extract_entities(symptoms_input, 'symptom') or []
    elif input_type == "text" and text_input:
        return extract_entities(text_input, 'symptom') or []
    return []

def patient_details(language):
    if 'chat_stage' not in st.session_state:
        st.session_state.chat_stage = 'name'
        st.session_state.patient_details = {}
        st.session_state.voice_attempts = {}
        st.session_state.prompt_spoken_flags = {}

    input_type = st.session_state.get('input_type', 'Text')
    prompt_flags = st.session_state.prompt_spoken_flags

    def prompt_input(prompt, input_key, stage, entity_type=None, validate_func=None, force_text=False):
        if not prompt_flags.get(stage, False):
            write_and_speak(prompt, language)
            prompt_flags[stage] = True

        if force_text or input_type == "Text":
            text_input = st.text_input(translate(f"Your {stage}",language), key=input_key)
            if st.button(translate(f"Submit {stage}",language), key=f"submit_{stage}"):
                if entity_type:
                    result = extract_entities(text_input, entity_type)
                    if result:
                        return result[0]
                    write_and_speak(f"Sorry, I couldn’t recognize your {stage}. Please try again.", language)
                    return None
                elif validate_func:
                    result = validate_func(text_input)
                    if result:
                        return result
                    write_and_speak(f"Please enter a valid {stage}.", language)
                    return None
                return text_input.title()
        else:
            if st.button(translate(f"Record {stage}",language), key=f"record_{stage}"):
                voice_success = record(language)
                if voice_success:
                    input_data = speech_to_text()
                    if input_data and input_data != "None":
                        if entity_type:
                            result = extract_entities(input_data, entity_type)
                            if result:
                                return result[0]
                        elif validate_func:
                            result = validate_func(input_data)
                            if result:
                                return result
                        st.session_state.voice_attempts[stage] = st.session_state.voice_attempts.get(stage, 0) + 1
                        if st.session_state.voice_attempts[stage] >= 2:
                            write_and_speak(f"Sorry, I couldn’t understand your {stage}. Please type it instead.", language)
                            return "switch_to_text"
                        write_and_speak(f"Sorry, I couldn’t understand your {stage}. Please try speaking again.", language)
                    else:
                        st.session_state.voice_attempts[stage] = st.session_state.voice_attempts.get(stage, 0) + 1
                        if st.session_state.voice_attempts[stage] >= 2:
                            write_and_speak(f"Sorry, I couldn’t understand your {stage}. Please type it instead.", language)
                            return "switch_to_text"
                        write_and_speak(f"Sorry, I couldn’t understand your {stage}. Please try speaking again.", language)
                else:
                    st.session_state.voice_attempts[stage] = st.session_state.voice_attempts.get(stage, 0) + 1
                    if st.session_state.voice_attempts[stage] >= 2:
                        write_and_speak(f"Sorry, I couldn’t record your {stage}. Please type it instead.", language)
                        return "switch_to_text"
                    write_and_speak(f"Sorry, I couldn’t record your {stage}. Please try speaking again.", language)
        return None

    if st.session_state.chat_stage == 'name':
        result = prompt_input(
            "Hi, my name is Medibot. What’s your name?",
            "name_input",
            "name",
            entity_type="name"
        )
        if result == "switch_to_text":
            st.session_state.input_type = "Text"
            st.rerun()
        elif result:
            st.session_state.patient_details['name'] = result.title()
            write_and_speak(f"Hello {result}, it’s a pleasure to meet you!", language)
            st.session_state.chat_stage = 'age'
            st.rerun()

    elif st.session_state.chat_stage == 'age':
        first_name = st.session_state.patient_details['name'].split()[0]

        if not prompt_flags.get("age", False):
            write_and_speak(f"{first_name}, can you tell me how old you are?", language)
            prompt_flags["age"] = True

        def validate_age(text):
            age = next((int(i) for i in text.split() if i.isdigit()), None)
            return age if age else None

        age_input = st.text_input(translate("Your age",language), key="age_input")
        if st.button(translate("Submit Age",language), key="submit_age"):
            result = validate_age(age_input)
            if result:
                st.session_state.patient_details['age'] = result
                st.session_state.chat_stage = 'gender'
                st.rerun()
            else:
                write_and_speak("Please enter a valid age.", language)

    elif st.session_state.chat_stage == 'gender':
        first_name = st.session_state.patient_details['name'].split()[0]
        if not prompt_flags.get("gender", False):
            write_and_speak(f"Alright {first_name}, what’s your gender? (Male, Female, Others)", language)
            prompt_flags["gender"] = True

        gender = st.radio(translate("Gender",language), translate_list(["Male","Female","Others"],language), key="gender_input")
        if st.button(translate("Submit Gender",language)):
            st.session_state.patient_details['gender'] = gender
            st.session_state.chat_stage = 'city'
            st.rerun()

    elif st.session_state.chat_stage == 'city':
        result = prompt_input(
            "Great! Could you tell me the city you are from?",
            "city_input",
            "city",
            entity_type="city"
        )
        if result == "switch_to_text":
            st.session_state.input_type = "Text"
            st.rerun()
        elif result:
            st.session_state.patient_details['city'] = result.title()
            st.session_state.chat_stage = 'contact'
            st.rerun()

    elif st.session_state.chat_stage == 'contact':
        def validate_contact(text):
            return text if text.isdigit() and len(text) == 10 else None

        result = prompt_input(
            "Lastly, could you provide your 10-digit mobile phone number?",
            "contact_input",
            "contact",
            validate_func=validate_contact,
            force_text=True
        )
        if result:
            st.session_state.patient_details['contact'] = result
            st.session_state.chat_stage = 'confirm'
            st.rerun()

    elif st.session_state.chat_stage == 'confirm':
        details = st.session_state.patient_details
        if not prompt_flags.get("confirm", False):
            write_and_speak("Thank you for providing your details!\n Please check all your details and click on Yes if Correct and No if you need to change any detail ", language)
            st.write(translate(f"Here’s what I’ve noted:\n- Name: {details['name']}\n- Age: {details['age']}\n- Gender: {details['gender']}\n- City: {details['city']}\n- Contact: {details['contact']}",language))
            prompt_flags["confirm"] = True
        confirm = st.radio(translate("Are these details correct?",language), [translate("Yes",language), translate("No",language)], key="confirm_input")
        if st.button(translate("Confirm Details",language)):
            if translate(confirm,"en") == "Yes":
                write_and_speak("Great, you're all set!", language)
                st.session_state.chat_stage = 'done'
                return [details['name'], details['age'], details['gender'], details['city'], details['contact']]
            else:
                st.session_state.chat_stage = 'correct_detail'
                st.rerun()

    elif st.session_state.chat_stage == 'correct_detail':
        if not prompt_flags.get("correct_detail", False):
            write_and_speak("Which detail is incorrect?", language)
            prompt_flags["correct_detail"] = True

        options = ["Name", "Age", "Gender", "City", "Contact"]
        wrong_detail = st.radio(translate("Select incorrect detail", language), translate_list(options,language), key="wrong_detail")

        if st.button(translate("Confirm selection", language), key="confirm_wrong_detail"):
            st.session_state.confirmed_wrong_detail = translate(wrong_detail, "en")
            st.session_state.chat_stage = "correct_confirmed"
            st.rerun()


    elif st.session_state.chat_stage == "correct_confirmed":
        wrong_detail = st.session_state.confirmed_wrong_detail

        if wrong_detail == "Name":
            st.session_state.prompt_spoken_flags["name"] = False
            result = prompt_input(
                "Please enter your correct Name",
                "name_input",
                "name",
                entity_type="name"
            )
            if result == "switch_to_text":
                st.session_state.input_type = "Text"
                st.rerun()
            elif result:
                st.session_state.patient_details['name'] = result.title()
                st.session_state.prompt_spoken_flags["confirm"] = False
                st.session_state.chat_stage = "confirm"
                st.rerun()


        elif wrong_detail == "Age":
            st.session_state.prompt_spoken_flags["age"] = False
            write_and_speak("Please enter your correct age", language)

            def validate_age(text):
                age = next((int(i) for i in text.split() if i.isdigit()), None)
                return age if age else None

            age_input = st.text_input(translate("Your age", language), key="age_input")
            if st.button(translate("Submit Age", language), key="submit_age"):
                result = validate_age(age_input)
                if result:
                    st.session_state.patient_details['age'] = result
                    st.session_state.prompt_spoken_flags["confirm"] = False
                    st.session_state.chat_stage = "confirm"
                    st.rerun()
                else:
                    write_and_speak("Please enter a valid age.", language)

        elif wrong_detail == "Gender":
            st.session_state.prompt_spoken_flags["gender"] = False
            write_and_speak("Please enter correct gender", language)
            gender = st.radio(translate("Gender", language), translate_list(["Male", "Female", "Others"], language), key="gender_input")
            if st.button(translate("Submit Gender", language)):
                st.session_state.patient_details['gender'] = gender
                st.session_state.prompt_spoken_flags["confirm"] = False
                st.session_state.chat_stage = "confirm"
                st.rerun()

        elif wrong_detail == "City":
            st.session_state.prompt_spoken_flags["city"] = False
            write_and_speak("Please tell the correct name of your city", language)
            result = prompt_input(
                "Great! Could you tell me the city you are from?",
                "city_input",
                "city",
                entity_type="city"
            )
            if result == "switch_to_text":
                st.session_state.input_type = "Text"
                st.rerun()
            elif result:
                st.session_state.patient_details['city'] = result.title()
                st.session_state.prompt_spoken_flags["confirm"] = False
                st.session_state.chat_stage = "confirm"
                st.rerun()

        elif wrong_detail == "Contact":
            st.session_state.prompt_spoken_flags["contact"] = False

            def validate_contact(text):
                return text if text.isdigit() and len(text) == 10 else None

            result = prompt_input(
                "Please enter your correct mobile number",
                "contact_input",
                "contact",
                validate_func=validate_contact,
                force_text=True
            )
            if result:
                st.session_state.patient_details['contact'] = result
                st.session_state.prompt_spoken_flags["confirm"] = False
                st.session_state.chat_stage = "confirm"
                st.rerun()



def emotion(n, symptom):
    more = [
        f"Got it—more severe {symptom}. How often are you feeling this way? (occasionally, daily, or constantly)",
        f"It seems like you're experiencing {symptom} quite intensely. Could you tell me how often this occurs? (occasionally, daily, or constantly)",
        f"{symptom} appears to be impacting you significantly. Is it occasional, daily, or constant? (occasionally, daily, or constantly)",
        f"The severity of your {symptom} seems high. How frequent is this feeling? (occasionally, daily, or constantly)",
        f"You're describing your {symptom} as more severe. How often does it happen? (occasionally, daily, or constantly)",
        f"It sounds like your {symptom} is very serious. Could you specify the frequency? (occasionally, daily, or constantly)",
        f"You're experiencing intense {symptom}. Do you feel it occasionally, daily, or constantly? (occasionally, daily, or constantly)",
        f"Your {symptom} severity seems significant. How regularly are you affected? (occasionally, daily, or constantly)",
        f"The {symptom} you're describing is intense. How frequently does this occur? (occasionally, daily, or constantly)",
        f"With this severity of {symptom}, we need to understand its frequency. How often do you feel it? (occasionally, daily, or constantly)"
    ]
    less = [
        f"Got it—less severe {symptom}. How often are you feeling this way? (occasionally, daily, or constantly)",
        f"It seems like your {symptom} isn't too intense. How often do you notice it? (occasionally, daily, or constantly)",
        f"Your {symptom} appears to be minimal. Could you tell me the frequency? (occasionally, daily, or constantly)",
        f"The severity of your {symptom} is low. How regularly do you experience it? (occasionally, daily, or constantly)",
        f"You're describing your {symptom} as less severe. How often does it happen? (occasionally, daily, or constantly)",
        f"It sounds like your {symptom} is manageable. Could you specify how often it occurs? (occasionally, daily, or constantly)",
        f"You're experiencing mild {symptom}. Is it occasional, daily, or constant? (occasionally, daily, or constantly)",
        f"Your {symptom} severity seems minimal. How frequently are you affected? (occasionally, daily, or constantly)",
        f"The {symptom} you're describing is less intense. How often does this occur? (occasionally, daily, or constantly)",
        f"With this mild {symptom}, we’d like to understand its frequency. How often do you feel it? (occasionally, daily, or constantly)"
    ]
    moderate = [
        f"Got it—moderate {symptom}. How often are you feeling this way? (occasionally, daily, or constantly)",
        f"It seems like your {symptom} is moderate in intensity. Could you tell me how often this occurs? (occasionally, daily, or constantly)",
        f"Your {symptom} appears to be of moderate severity. Is it occasional, daily, or constant? (occasionally, daily, or constantly)",
        f"The severity of your {symptom} seems moderate. How frequent is this feeling? (occasionally, daily, or constantly)",
        f"You're describing your {symptom} as moderate. How often does it happen? (occasionally, daily, or constantly)",
        f"It sounds like your {symptom} is moderate. Could you specify the frequency? (occasionally, daily, or constantly)",
        f"You're experiencing moderate {symptom}. Do you feel it occasionally, daily, or constantly? (occasionally, daily, or constantly)",
        f"Your {symptom} severity seems moderate. How regularly are you affected? (occasionally, daily, or constantly)",
        f"The {symptom} you're describing is moderate. How frequently does this occur? (occasionally, daily, or constantly)",
        f"With this moderate {symptom}, we need to understand its frequency. How often do you feel it? (occasionally, daily, or constantly)"
    ]
    n = int(n)
    if 0 <= n <= 3:
        return less[random.randint(0, 9)]
    elif 4 <= n <= 7:
        return moderate[random.randint(0, 9)]
    elif 8 <= n <= 10:
        return more[random.randint(0, 9)]

def emotion1(symptom, severity, freq1):
    responses = [
        f"Got it. Can you share more about {symptom} with {severity} level and how it has been affecting you {freq1}? When did you first notice this? (a few days ago, a week ago)",
        f"Understood. You mentioned {symptom} with {severity} level happening {freq1}. How long has this been going on? (a few days ago, a week ago)",
        f"Thanks for sharing. Since you’ve had {symptom} with {severity} level {freq1}, do you recall when it first started? (a few days ago, a week ago)",
        f"I see. Regarding {symptom} with {severity} level occurring {freq1}, when did you begin to notice it? (a few days ago, a week ago)",
        f"Okay, noted. Since you’ve been dealing with {symptom} with {severity} level {freq1}, when did it initially start? (a few days ago, a week ago)"
    ]
    return responses[random.randint(0, 4)]

def emotion2():
    responses = [
        f"I appreciate you sharing that. It seems like this has been persistent. Would you like to mention any other symptoms or stop here? (type 'more' or 'exit')",
        f"Thank you for that information. It sounds like this has been ongoing. Would you like to add any more details or stop here? (type 'more' or 'exit')",
        f"Thanks for sharing. This seems to have been happening for some time. Do you have any other symptoms to mention, or would you like to stop here? (type 'more' or 'exit')",
        f"Appreciate the details. It looks like this has been lasting for a while. Would you prefer to share more or end here? (type 'more' or 'exit')",
        f"Thanks for that. This seems to have been happening for some time now. Would you like to discuss other symptoms or finish here? (type 'more' or 'exit')"
    ]
    return responses[random.randint(0, 4)]

def emotion3(symptom):
    responses = [
        f"I'm sorry to hear that. Let's get some more details. On a scale of 1 to 9, how severe would you say your {symptom} are?",
        f"I understand. To better assist you, could you rate the severity of your {symptom} on a scale of 1 to 9?",
        f"That sounds difficult. Can you rate how severe your {symptom} are on a scale from 1 to 9?",
        f"I'm sorry you're feeling this way. On a scale of 1 to 9, how intense would you say your {symptom} are?",
        f"Thanks for sharing. To understand better, can you rate your {symptom} severity on a scale of 1 to 9?"
    ]
    return responses[random.randint(0, 4)]

def greet(name):
    requests = [
        f"Hello, {name}! Could you please share the symptoms you're experiencing?",
        f"Hi, {name}! May I ask what symptoms you are currently facing?",
        f"Good day, {name}! Could you kindly describe the symptoms you're dealing with?",
        f"Welcome, {name}! Please let me know what symptoms you're experiencing.",
        f"Hello, {name}! I’d appreciate it if you could tell me about the symptoms you’ve been having."
    ]
    return requests[random.randint(0, 4)]

def ending(name):
    responses = [
        f"Thank you, {name}! Wishing you a speedy recovery and take care!",
        f"You're welcome, {name}! Take good care of yourself and feel better soon!",
        f"Thanks, {name}! Stay safe, and I hope you feel better soon!",
        f"You're welcome, {name}! Take care and I hope you start feeling better soon!",
        f"Thank you, {name}! Take care, and I wish you a quick recovery!"
    ]
    return responses[random.randint(0, 4)]



def database(symptoms, ml, name):
    severity, freq_list, duration = [], [], []
    for i in range(len(ml)):
        severity.append(translate(ml[i][0],"en"))
        freq_list.append(translate(str(ml[i][1]),"en"))
        duration.append(translate(ml[i][2],"en"))
    d = {}
    for k, symptom in enumerate(symptoms):
        d[symptom] = {"severity": severity[k] if k < len(severity) else "", 
                      "frequency": freq_list[k] if k < len(freq_list) else "", 
                      "duration": duration[k] if k < len(duration) else ""}
    if 'master_database' not in st.session_state:
        st.session_state.master_database = []
    st.session_state.master_database.append({name: d})

def freq(text):
    l = ["daily", "constantly", "occasionally", "frequently"]
    for ele in l:
        if ele in text.lower():
            return ele
    return 11

ml = []

def ask_follow_up_questions(ml, symptom, language):
    symptom_key = f"follow_up_{symptom}"
    if symptom_key not in st.session_state:
        st.session_state[symptom_key] = {
            'stage': 'severity',
            'data': [],
            'attempts': {'frequency': 0, 'duration': 0}
        }

    if 'prompt_spoken_flags' not in st.session_state:
        st.session_state.prompt_spoken_flags = {}

    if 'record_prompt_spoken' not in st.session_state:
        st.session_state.record_prompt_spoken = False

    follow_up = st.session_state[symptom_key]
    ls = follow_up['data']
    stage = follow_up['stage']
    attempts = follow_up['attempts']
    input_type = st.session_state.get('input_type', 'Text')

    # Only process the current symptom if no other symptom is in an active stage
    active_symptom = st.session_state.get('active_symptom', symptom)
    if active_symptom != symptom:
        return
    st.session_state.active_symptom = symptom

    # === SEVERITY ===
    if stage == 'severity':
        prompt_flag = f"{symptom}_severity_prompted"
        if not st.session_state.prompt_spoken_flags.get(prompt_flag, False):
            write_and_speak(emotion3(symptom), language)
            st.session_state.prompt_spoken_flags[prompt_flag] = True

        severity_input = st.radio(
            translate(f"Select the severity of {symptom} (1-9)", language),
            options=[str(i) for i in range(1, 10)],
            key=f"severity_{symptom}"
        )

        if st.button(translate(f"Submit Severity for {symptom}", language), key=f"submit_severity_{symptom}"):
            ls.append(severity_input)
            follow_up['data'] = ls
            follow_up['stage'] = 'frequency'
            st.session_state[symptom_key] = follow_up
            st.session_state.record_prompt_spoken = False
            st.rerun()

    # === FREQUENCY ===
    elif stage == 'frequency':
        prompt_flag = f"{symptom}_frequency_prompted"
        if not st.session_state.prompt_spoken_flags.get(prompt_flag, False):
            write_and_speak(emotion(ls[0], symptom), language)
            st.session_state.prompt_spoken_flags[prompt_flag] = True
        freq_input = st.radio(
                translate(f"Frequency of {symptom}", language),
                options=translate_list(["occasionally", "daily", "constantly"], language),
                key=f"freq_{symptom}"
            )

        if st.button(translate(f"Submit Frequency for {symptom}", language), key=f"submit_freq_{symptom}"):
            ls.append(translate(freq_input, 'en'))
            follow_up['data'] = ls
            follow_up['stage'] = 'duration'
            st.session_state[symptom_key] = follow_up
            st.session_state.record_prompt_spoken = False
            st.rerun()

    # === DURATION ===
    elif stage == 'duration':
        prompt_flag = f"{symptom}_duration_prompted"
        if not st.session_state.prompt_spoken_flags.get(prompt_flag, False):
            write_and_speak(emotion1(symptom, ls[0], ls[1]), language)
            st.session_state.prompt_spoken_flags[prompt_flag] = True
            attempts["duration"]=0
        if input_type == "Voice":
            if st.button(translate(f"Record Duration for {symptom}", language), key=f"record_dur_{symptom}"):
                if not st.session_state.record_prompt_spoken:
                    st.session_state.record_prompt_spoken = True

                if record(language):
                    duration_input = speech_to_text()
                    dur2 = detect_time_phrases(duration_input) if duration_input != "None" else None
                    if dur2:
                        ls.append(dur2)
                        follow_up['data'] = ls
                        follow_up['stage'] = 'done'
                        ml.append(ls)
                        st.session_state[symptom_key] = follow_up
                        st.session_state[f"symptom_{symptom}_done"] = True
                        st.session_state.record_prompt_spoken = False
                        st.session_state.active_symptom = None  # Allow next symptom
                        st.rerun()
                    else:
                        attempts['duration'] += 1
                        if attempts['duration'] >= 2:
                            write_and_speak("Sorry, I couldn’t understand your duration. Please type it instead.", language)
                            st.session_state.input_type = "Text"
                            st.session_state.record_prompt_spoken = False
                            st.rerun()
                        else:
                            write_and_speak("Please speak a valid timeline!", language)
                else:
                    attempts['duration'] += 1
                    if attempts['duration'] >= 2:
                        write_and_speak("Sorry, I couldn’t record your duration. Please type it instead.", language)
                        st.session_state.input_type = "Text"
                        st.session_state.record_prompt_spoken = False
                        st.rerun()
                    else:
                        write_and_speak("Sorry, I couldn’t record your duration. Please try again.", language)
        else:
            duration_input = st.text_input(translate(f"When did {symptom} start?", language), key=f"duration_{symptom}")
            if st.button(translate(f"Submit Duration for {symptom}", language), key=f"submit_dur_{symptom}"):
                dur2 = detect_time_phrases(duration_input)
                if dur2:
                    ls.append(dur2)
                    follow_up['data'] = ls
                    follow_up['stage'] = 'done'
                    ml.append(ls)
                    st.session_state[f"symptom_{symptom}_done"] = True
                    st.session_state.pop('active_symptom', None)
                    st.session_state.pop('follow_up_question_index', None)
                    st.rerun()

                else:
                    write_and_speak("Please enter a valid timeline!", language)



def printer(data):
    for patient in data:
        for patient_name, symptoms in patient.items():
            st.write("Symptoms and Details:")
            for symptom, details in symptoms.items():
                if symptom != "Pre-medication":
                    st.write(f"- Symptom: {symptom.capitalize()}")
                    st.write(f"  Severity: {details.get('severity', 'N/A')}")
                    st.write(f"  Frequency: {details.get('frequency', 'N/A')}")
                    st.write(f"  Duration: {details.get('duration', 'N/A')}")

def generate_report(demographics_list, patient_data, pre_med_conditions, filename="patient_report.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", style='B', size=18)
    pdf.cell(200, 10, "PATIENT SCREENING REPORT", ln=True, align='C')
    pdf.ln(10)
    demographics = {"Name": translate(demographics_list[0],"en"), "Age": str(demographics_list[1]), "Gender": translate(demographics_list[2],"en"),
                    "City": translate(demographics_list[3],"en"), "Phone No.": demographics_list[4]}

    pdf.set_font("Arial", style='B', size=14)
    pdf.cell(200, 10, "Patient Demographics", ln=True, border='B')
    pdf.set_font("Arial", size=12)
    pdf.ln(5)

    for key, value in demographics.items():
        pdf.cell(50, 10, f"{key}:", border=1)
        pdf.cell(140, 10, value, border=1, ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", style='B', size=14)
    pdf.cell(200, 10, "Symptoms Summary", ln=True, border='B')
    pdf.set_font("Arial", size=12)
    pdf.ln(5)

    col_widths = [40, 30, 30, 40]
    headers = ["Symptom", "Frequency", "Severity", "Duration"]
    row_height = 10

    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], row_height, header, border=1, align='C')
    pdf.ln(row_height)

    for data in patient_data:
        for _, symptoms in data.items():
            for symptom, details in symptoms.items():
                if symptom != "Pre-medication":
                    pdf.cell(col_widths[0], row_height, translate(symptom.capitalize(),"en"), border=1)
                    pdf.cell(col_widths[1], row_height, translate(str(details["frequency"]),"en"), border=1)
                    pdf.cell(col_widths[2], row_height, str(details["severity"]), border=1)
                    pdf.cell(col_widths[3], row_height, translate(details["duration"],"en"), border=1, ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", style='B', size=14)
    pdf.cell(200, 10, "Pre-Medication Conditions", ln=True, border='B')
    pdf.set_font("Arial", size=12)
    pdf.ln(5)

    for condition in pre_med_conditions:
        condition=translate(condition,"en")
        pdf.cell(200, 10, f"- {condition}", ln=True)

    pdf.output(filename)
    return filename

def run_chatbot():
    supported_languages = {
        "en": "English", "hi": "Hindi", "bn": "Bengali", "gu": "Gujarati",
        "kn": "Kannada", "ml": "Malayalam", "mr": "Marathi", "od": "Odia",
        "pa": "Punjabi", "ta": "Tamil", "te": "Telugu"
    }

    if 'chatbot_stage' not in st.session_state:
        st.session_state.chatbot_stage = 'language_selection'
        st.session_state.selected_language = 'en'
        st.session_state.symptoms_collected = []
        st.session_state.ml = []
        st.session_state.medications = []
        st.session_state.input_type = 'Voice'
        st.session_state.username = None
        st.session_state.prompt_spoken_flags = {}

    if st.session_state.chatbot_stage == 'language_selection':
        st.write("Please select your preferred language:")
        language_options = list(supported_languages.values())
        selected_language_display = st.radio("Choose Language", options=language_options, key="language_selector")
        if st.button("Confirm Language"):
            try:
                selected_lang_code = next(key for key, value in supported_languages.items() if value == selected_language_display)
                st.session_state.selected_language = selected_lang_code
                st.session_state.master_database = []
                st.session_state.chatbot_stage = 'details'
                st.rerun()
            except StopIteration:
                st.error("Invalid language selection. Please try again.")
        return

    if st.session_state.chatbot_stage == 'details':
        details = patient_details(st.session_state.selected_language)
        if details:
            st.session_state.details = details
            st.session_state.chatbot_stage = 'symptoms'
            st.rerun()

    elif st.session_state.chatbot_stage == 'symptoms':
        name = st.session_state.details[0]
        if not st.session_state.prompt_spoken_flags.get("symptoms_prompted", False):
            write_and_speak(greet(name), st.session_state.selected_language)
            st.session_state.prompt_spoken_flags["symptoms_prompted"] = True

        if st.session_state.input_type == "Voice":
            if 'symptom_attempts' not in st.session_state:
                st.session_state.symptom_attempts = 0
            if st.button("Record Symptoms", key="record_symptoms"):
                symptoms = take_symptoms("Voice", st.session_state.selected_language)
                if symptoms:
                    new_symptoms = [s for s in symptoms if s not in st.session_state.symptoms_collected]
                    st.session_state.symptoms_collected.extend(new_symptoms)
                    st.write(f"Identified symptoms: {', '.join(st.session_state.symptoms_collected)}")
                    st.session_state.symptom_attempts = 0
                    st.session_state.chatbot_stage = 'follow_up'
                    st.session_state.prompt_spoken_flags["symptoms_prompted"] = False
                    st.rerun()
                else:
                    st.session_state.symptom_attempts += 1
                    if st.session_state.symptom_attempts >= 2:
                        write_and_speak("Sorry, I couldn’t recognize any symptoms. Please type them instead.", st.session_state.selected_language)
                        st.session_state.input_type = "Text"
                        st.session_state.symptom_attempts = 0
                        st.rerun()
                    write_and_speak("No symptoms recognized. Please try speaking again.", st.session_state.selected_language)
        else:
            symptom_input = st.text_input(translate("Enter your symptoms", st.session_state.selected_language), key="symptom_input")
            if st.button(translate("Submit Symptoms", st.session_state.selected_language), key="submit_symptoms"):
                symptoms = take_symptoms("text", st.session_state.selected_language, symptom_input)
                if symptoms:
                    new_symptoms = [s for s in symptoms if s not in st.session_state.symptoms_collected]
                    st.session_state.symptoms_collected.extend(new_symptoms)
                    st.write(f"Identified symptoms: {', '.join(st.session_state.symptoms_collected)}")
                    st.session_state.chatbot_stage = 'follow_up'
                    st.session_state.prompt_spoken_flags["symptoms_prompted"] = False
                    st.rerun()
                else:
                    write_and_speak("No symptoms recognized. Please enter valid symptoms.", st.session_state.selected_language)

    elif st.session_state.chatbot_stage == 'follow_up':
        pending_symptoms = [s for s in st.session_state.symptoms_collected if f"symptom_{s}_done" not in st.session_state]

        if not pending_symptoms:
            st.session_state.chatbot_stage = 'more_symptoms'
            st.rerun()
        current_symptom = st.session_state.get("active_symptom", None)
        if not current_symptom:
            st.session_state.active_symptom = pending_symptoms[0]
            st.rerun()
        # Call follow-up for the current symptom
        ask_follow_up_questions(st.session_state.ml, st.session_state.active_symptom, st.session_state.selected_language)


    elif st.session_state.chatbot_stage == 'more_symptoms':
        if not st.session_state.prompt_spoken_flags.get("more_prompted", False):
            write_and_speak(emotion2(), st.session_state.selected_language)
            st.session_state.prompt_spoken_flags["more_prompted"] = True

        choice = st.radio(translate("More symptoms or exit?",st.session_state.selected_language), translate_list(["more", "exit"],st.session_state.selected_language), key="more_exit")
        if st.button(translate("Submit Choice", st.session_state.selected_language), key="submit_more_exit"):
            if choice == "more":
                st.session_state.chatbot_stage = 'symptoms'
            else:
                database(st.session_state.symptoms_collected, st.session_state.ml, st.session_state.details[0])
                st.session_state.chatbot_stage = 'medications'
            st.session_state.prompt_spoken_flags["more_prompted"] = False
            st.rerun()

    elif st.session_state.chatbot_stage == 'medications':
        if not st.session_state.prompt_spoken_flags.get("med_prompted", False):
            write_and_speak("Do you have any ongoing medical condition or take any medication regularly? (Yes/No)", st.session_state.selected_language)
            st.session_state.prompt_spoken_flags["med_prompted"] = True

        med_choice = st.radio(translate("Response",st.session_state.selected_language), translate_list(["Yes", "No"],st.session_state.selected_language), key="med_choice")
        if st.button(translate("Submit Medications or your medical conditions", st.session_state.selected_language), key="submit_med_choice"):
            if translate(med_choice,"en") == "Yes":
                st.session_state.chatbot_stage = 'medications_input'
            else:
                st.session_state.chatbot_stage = 'summary'
            st.session_state.prompt_spoken_flags["med_prompted"] = False
            st.rerun()

    elif st.session_state.chatbot_stage == 'medications_input':
        if st.session_state.input_type == "Voice":
            if 'med_attempts' not in st.session_state:
                st.session_state.med_attempts = 0
            if not st.session_state.prompt_spoken_flags.get("med_input_prompted", False):
                write_and_speak("Please record your premedical conditions and medications.", st.session_state.selected_language)
                st.session_state.prompt_spoken_flags["med_input_prompted"] = True

            if st.button(translate("Record Medications", st.session_state.selected_language), key="record_meds"):
                meds = translate_list(take_medical_terms("Voice", st.session_state.selected_language), "en")
                if meds:
                    st.session_state.medications.extend([m for m in meds if m not in st.session_state.medications])
                    st.write(f"Added medications: {', '.join(meds)}")
                    st.session_state.med_attempts = 0
                    # ⬇️ Go back to medications stage and ask again
                    st.session_state.chatbot_stage = 'medications'
                    st.session_state.prompt_spoken_flags["med_input_prompted"] = False
                    st.session_state.prompt_spoken_flags["med_prompted"] = False
                    st.rerun()
                else:
                    st.session_state.med_attempts += 1
                    if st.session_state.med_attempts >= 2:
                        write_and_speak("Sorry, I couldn’t recognize any medications. Please type them instead.", st.session_state.selected_language)
                        st.session_state.input_type = "Text"
                        st.session_state.med_attempts = 0
                        st.rerun()
                    write_and_speak("No medications recognized. Please try speaking again.", st.session_state.selected_language)

        else:
            if not st.session_state.prompt_spoken_flags.get("med_input_prompted", False):
                write_and_speak("Please enter your medications.", st.session_state.selected_language)
                st.session_state.prompt_spoken_flags["med_input_prompted"] = True

            med_input = st.text_input(translate("Enter your medications", st.session_state.selected_language), key="med_input")
            if st.button(translate("Submit Medications", st.session_state.selected_language), key="submit_meds"):
                meds = translate_list(take_medical_terms("text", st.session_state.selected_language, med_input), "en")
                if meds:
                    st.session_state.medications.extend([m for m in meds if m not in st.session_state.medications])
                    st.write(f"Added medications: {', '.join(meds)}")
                    # ⬇️ Ask again
                    st.session_state.chatbot_stage = 'medications'
                    st.session_state.prompt_spoken_flags["med_input_prompted"] = False
                    st.session_state.prompt_spoken_flags["med_prompted"] = False
                    st.rerun()
                else:
                    write_and_speak("No medications recognized. Please enter valid medications.", st.session_state.selected_language)

    elif st.session_state.chatbot_stage == 'summary':
        name = st.session_state.details[0]
        if not st.session_state.prompt_spoken_flags.get("summary_prompted", False):
            write_and_speak("We recorded your responses as shown below:", st.session_state.selected_language)
            base_lst = ["Name: ", "Age: ", "Gender: ", "City: ", "Phone No.: "]
            for i, detail in enumerate(st.session_state.details):
                st.write(f"{base_lst[i]}{detail}")
            printer(st.session_state.get('master_database', []))
            st.write("Your Pre-medications:")
            for med in st.session_state.medications:
                st.write(f"- {med}")
            write_and_speak("We kindly request you to summarize the symptoms and medical conditions for the doctor to assist you more effectively with your diagnosis and Please be prepared to share any reports related to pre-medication conditions, if applicable.", st.session_state.selected_language)
            write_and_speak(ending(name), st.session_state.selected_language)
            st.session_state.prompt_spoken_flags["summary_prompted"] = True

        if st.button(translate("Generate Report", st.session_state.selected_language), key="generate_report"):
            timestamp = f"{st.session_state.username}_{int(time.time())}"
            os.makedirs("reports", exist_ok=True)
            filename = f"reports/{timestamp}.pdf"
            report_file = generate_report(st.session_state.details, st.session_state.get('master_database', []), st.session_state.medications, filename)
            
            if os.path.exists(report_file):
                st.write("**Generated Report:**")
                with open(report_file, "rb") as file:
                    btn = st.download_button(
                        label="Download Report",
                        data=file,
                        file_name=f"report_{timestamp}.pdf",
                        mime="application/pdf",
                        key=f"download_new_report_{timestamp}"
                    )

                # Delete the file after offering it for download
                try:
                    os.remove(report_file)
                    st.info("Report auto-deleted for your security.")
                except Exception as e:
                    st.warning(f"Failed to delete report securely: {e}")

                st.success("Report generated and deleted successfully!")
                st.session_state.chatbot_stage = 'done'

if __name__ == "__main__":
    run_chatbot()