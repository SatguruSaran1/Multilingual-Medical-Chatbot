import importlib.util
modules = ['streamlit','ollama','fpdf','spacy','pymongo','sounddevice','numpy','requests','deep_translator']
for m in modules:
    print(m + ':', importlib.util.find_spec(m) is not None)
