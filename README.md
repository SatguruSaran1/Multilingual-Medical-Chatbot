#  MediBot AI-Powered Patient Screening Chatbot

An intelligent, multilingual patient screening chatbot that collects symptoms, demographic details, and pre-medication conditions through voice or text input, then generates a structured PDF report for doctors. Built with a secure, encrypted MongoDB backend and powered by LLaMA 3 via Ollama for NLP.


##  Features

-  **User Authentication** — Patient & Admin roles with login/register
-  **11 Indian Languages** — English, Hindi, Bengali, Gujarati, Kannada, Malayalam, Marathi, Odia, Punjabi, Tamil, Telugu
-  **Voice & Text Input** — Record symptoms via microphone or type them in
-  **LLaMA 3 NLP** — Extracts and normalizes medical entities from free-form input
-  **Client-Side Encryption** — Patient data encrypted in MongoDB Atlas using AES-256
-  **PDF Report Generation** — Auto-generates and downloads a formatted patient screening report
-  **Text-to-Speech** — Responses read aloud using Sarvam AI's multilingual TTS


## Tech Stack

* Frontend / UI - Streamlit
* LLM / NLP - Ollama (LLaMA 3), spaCy
* Database - MongoDB Atlas
* Encryption - PyMongo Client-Side Field Level Encryption (AES-256)
* Speech-to-Text - Sarvam AI API (`saaras:v1`)
* Text-to-Speech - Sarvam AI API (`bulbul:v1`)
* Translation - Deep Translator (Google Translate)
* Audio Recording - sounddevice, wave, numpy
* PDF Generation - fpdf
* Language - Python 3.10+


##  Prerequisites

Before you begin, make sure you have the following installed:

- **Python 3.10+** — [Download here](https://www.python.org/downloads/)
- **Ollama** — [Download here](https://ollama.com/download) (for running LLaMA 3 locally)
- A **MongoDB Atlas** account — [Sign up free](https://www.mongodb.com/atlas)
- A **Sarvam AI** API key — [Get one here](https://www.sarvam.ai/)


##  Installation & Setup

###  Clone the Repository

```bash
git clone https://github.com/SatguruSaran1/Medical-Chatbot.git
cd Medical-Chatbot
```

###  Install Python Dependencies

```bash
pip install streamlit pymongo deep-translator fpdf spacy sounddevice numpy requests
```

###  Download the spaCy Language Model

```bash
python -m spacy download en_core_web_sm
```

###  Pull and Run LLaMA 3 via Ollama

```bash
ollama pull llama3
ollama serve
```

> Keep `ollama serve` running in a separate terminal while using the app.

###  Set Your Sarvam AI API Key

Set it as an environment variable:

**Windows (PowerShell):**
```powershell
$env:sarvam = "your_sarvam_api_key_here"
```

**macOS / Linux:**
```bash
export sarvam="your_sarvam_api_key_here"
```

###  Configure MongoDB Atlas

1. Create a free cluster at [cloud.mongodb.com](https://cloud.mongodb.com)
2. Create a database user under **Database Access**
3. Whitelist your IP under **Network Access**
4. Copy your connection string from **Connect → Drivers → Python**
5. Open `chatbot.py` and update lines 21–23:

```python
db_user = "your_db_username"
db_password = "your_db_password"
uri = "your_connection_string_here"
```

Also update the same in `main.py` lines 11–14.

---

##  Running the App

```bash
streamlit run main.py
```

Then open **[http://localhost:8501](http://localhost:8501)** in your browser.

> **Note:** Use `main.py` as the entry point (not `chatbot.py`). It handles login, admin dashboard, and encryption setup.

##  Project Structure

```
├── main.py          # Entry point — login, admin dashboard, encryption setup
├── chatbot.py       # Core chatbot logic — symptom collection, NLP, report generation
├── README.md        # This file
└── Sample_report.pdf  # Example of a generated patient report
```



