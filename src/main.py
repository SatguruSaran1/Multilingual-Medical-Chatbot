import streamlit as st
import os
from pymongo import MongoClient
from pymongo.encryption import ClientEncryption, Algorithm
from pymongo.encryption_options import AutoEncryptionOpts
from bson.codec_options import CodecOptions
from bson.binary import STANDARD
from chatbot import run_chatbot

# MongoDB Connection Setup
db_user = "admin"
db_password = "admin"
uri = f"mongodb+srv://{db_user}:{db_password}@patient.68p05.mongodb.net/?retryWrites=true&w=majority&appName=Patient"
client = MongoClient(uri)

# Encryption Setup
key_vault_database_name = "encryption"
key_vault_collection_name = "__keyVault"
key_vault_namespace = f"{key_vault_database_name}.{key_vault_collection_name}"
cust_path = "C:\\project\\customer-master-key.txt"

if not os.path.exists(cust_path):
    file_bytes = os.urandom(96)
    with open(cust_path, "wb") as f:
        f.write(file_bytes)
    print(" Generated new CMK.")

with open(cust_path, "rb") as f:
    local_master_key = f.read()

kms_provider_credentials = {"local": {"key": local_master_key}}

client_encryption = ClientEncryption(
    kms_providers=kms_provider_credentials,
    key_vault_namespace=key_vault_namespace,
    key_vault_client=client,
    codec_options=CodecOptions(uuid_representation=STANDARD)
)

key_alt_name = "encryptionKey1"
key_vault_col = client[key_vault_database_name][key_vault_collection_name]
existing_key = key_vault_col.find_one({"keyAltNames": key_alt_name})

if existing_key:
    dek_id = existing_key["_id"]
    print(f" Using existing Data Encryption Key (DEK): {dek_id}")
else:
    dek_id = client_encryption.create_data_key("local", key_alt_names=[key_alt_name])
    print(f" Created new Data Encryption Key (DEK): {dek_id}")

database_name = "encrypted_healthcare"
db = client[database_name]

def login_page():
    st.title("Medical Chatbot Login")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Login")
        role = st.radio("Select Role:", ["Patient", "Admin"])
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            users_col = db["users"]
            user = users_col.find_one({"username": username, "password": password, "role": role})
            
            if user:
                st.session_state['username'] = username
                st.session_state['role'] = role
                st.session_state['logged_in'] = True
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials!")
    
    with col2:
        st.subheader("Register")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        if st.button("Register"):
            if new_password != confirm_password:
                st.error("Passwords do not match!")
            elif not new_username or not new_password:
                st.error("Username and password cannot be empty!")
            else:
                users_col = db["users"]
                if users_col.find_one({"username": new_username}):
                    st.error("Username already exists!")
                else:
                    users_col.insert_one({"username": new_username, "password": new_password, "role": "Patient"})
                    st.success("Registration successful! You can now login.")

def admin_dashboard():
    st.title("Admin Dashboard")
    
    users_col = db["users"]
    patients = users_col.find({"role": "Patient"})
    
    st.subheader("Patient Reports")
    patient_names = [patient["username"] for patient in patients]
    selected_patient = st.selectbox("Select Patient", ["All Patients"] + patient_names)
    
    reports_col = db["reports"]
    if selected_patient == "All Patients":
        reports = reports_col.find().sort("timestamp", -1)
    else:
        reports = reports_col.find({"username": selected_patient}).sort("timestamp", -1)
    
    reports_list = list(reports)
    if not reports_list:
        st.info("No reports found for the selected patient(s)")
    else:
        for report in reports_list:
            with st.expander(f"{report['username']} - {report['timestamp']}"):
                if os.path.exists(report['report']):
                    with open(report['report'], "rb") as file:
                        st.download_button(
                            f"Download Report ({report['timestamp']})", 
                            file, 
                            f"{report['username']}_{report['timestamp']}.pdf", 
                            "application/pdf"
                        )
                else:
                    st.write("Report file not found.")

def patient_dashboard():
    st.title(f"Welcome to Hospital X!")

    tab1, = st.tabs(["Chatbot"])

    with tab1:
        run_chatbot()  # Pass client_encryption to logic1.py
def encrypt_patient_data(patient_data, client_encryption, key_alt_name="encryptionKey1"):
    encrypted_demographic_data = {
        "Name": client_encryption.encrypt(
            patient_data["DemographicData"]["Name"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
            key_alt_name=key_alt_name
        ),
        "Age": client_encryption.encrypt(
            str(patient_data["DemographicData"]["Age"]), Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
            key_alt_name=key_alt_name
        ),
        "Gender": client_encryption.encrypt(
            patient_data["DemographicData"]["Gender"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
            key_alt_name=key_alt_name
        ),
        "Location": client_encryption.encrypt(
            patient_data["DemographicData"]["Location"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
            key_alt_name=key_alt_name
        ),
        "Contact": client_encryption.encrypt(
            patient_data["DemographicData"]["Contact"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
            key_alt_name=key_alt_name
        ),
        "MedicalConditions": client_encryption.encrypt(
            str(patient_data["DemographicData"]["MedicalConditions"]), Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
            key_alt_name=key_alt_name
        )
    }
    
    encrypted_symptoms_data = []
    for symptom in patient_data["SymptomsData"]:
        encrypted_symptom = {
            "Symptom": client_encryption.encrypt(
                symptom["Symptom"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
                key_alt_name=key_alt_name
            ),
            "Severity": client_encryption.encrypt(
                symptom["Severity"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Random,
                key_alt_name=key_alt_name
            ),
            "Frequency": client_encryption.encrypt(
                symptom["Frequency"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
                key_alt_name=key_alt_name
            ),
            "Duration": client_encryption.encrypt(
                symptom["Duration"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Deterministic,
                key_alt_name=key_alt_name
            ),
            "Additional Notes": client_encryption.encrypt(
                symptom["Additional Notes"], Algorithm.AEAD_AES_256_CBC_HMAC_SHA_512_Random,
                key_alt_name=key_alt_name
            )
        }
        encrypted_symptoms_data.append(encrypted_symptom)
    
    encrypted_data = {
        "DemographicData": encrypted_demographic_data,
        "SymptomsData": encrypted_symptoms_data,
        "username": patient_data["username"]  # Store username unencrypted for querying
    }
    return encrypted_data

def decrypt_patient_data(encrypted_data, client_encryption):
    decrypted_demographic_data = {
        "Name": client_encryption.decrypt(encrypted_data["DemographicData"]["Name"]),
        "Age": client_encryption.decrypt(encrypted_data["DemographicData"]["Age"]),
        "Gender": client_encryption.decrypt(encrypted_data["DemographicData"]["Gender"]),
        "Location": client_encryption.decrypt(encrypted_data["DemographicData"]["Location"]),
        "Contact": client_encryption.decrypt(encrypted_data["DemographicData"]["Contact"]),
        "MedicalConditions": client_encryption.decrypt(encrypted_data["DemographicData"]["MedicalConditions"])
    }
    
    decrypted_symptoms_data = []
    for symptom in encrypted_data["SymptomsData"]:
        decrypted_symptom = {
            "Symptom": client_encryption.decrypt(symptom["Symptom"]),
            "Severity": client_encryption.decrypt(symptom["Severity"]),
            "Frequency": client_encryption.decrypt(symptom["Frequency"]),
            "Duration": client_encryption.decrypt(symptom["Duration"]),
            "Additional Notes": client_encryption.decrypt(symptom["Additional Notes"])
        }
        decrypted_symptoms_data.append(decrypted_symptom)
    
    decrypted_data = {
        "DemographicData": decrypted_demographic_data,
        "SymptomsData": decrypted_symptoms_data
    }
    return decrypted_data

def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        login_page()
    else:
        if st.sidebar.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        if st.session_state['role'] == "Patient":
            patient_dashboard()
        elif st.session_state['role'] == "Admin":
            admin_dashboard()

if __name__ == "__main__":
    main()
    