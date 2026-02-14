import sys
import instructor
from openai import OpenAI
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
print(BASE_DIR)

WATCH_DIR = BASE_DIR / "dictations"  # directory with dictation files, relative path
CSV_FILE = BASE_DIR / "results.csv"  # location results csv file
SUPPORTED_FORMATS = {'.wav', '.aifc', '.aiff', '.mp3'} # formats to check, can be converted to wav in script
CHECKED_FILES = set() # define an empty set

# --- LOCAL AI SETUP (OLLAMA) ---
# Ensure Ollama is running and you have run 'ollama pull llama3'
client = instructor.from_openai(
    OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"),
    mode=instructor.Mode.JSON
)