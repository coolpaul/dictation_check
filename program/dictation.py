import os
import sys
import csv
import time
import datetime
from pathlib import Path
from pydub import AudioSegment
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from faster_whisper import WhisperModel
from pydantic import BaseModel, Field
from typing import Optional
import dateparser # Add this at the top
from enum import Enum

## to do for installation:
# Download Ollama: Go to ollama.com and install it.
# run: curl -fsSL https://ollama.com/install.sh | sh    
# ollama pull llama3
# conda activate openslide
# python -m pip install faster-whisper instructor openai
# python -m pip install watchdog
# python -m pip install pydub
# brew install ffmpeg
# python -m pip install dateparser 

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
from config import config

class GenderIdentity(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    UNKNOWN = "Unknown"

class ExtractionSchema(BaseModel):
    meeting_type: str = Field(
        description="Was this a Telephone call or Face-to-Face?"
        )
    follow_up_time: Optional[str] = Field(
        default=None, 
        description="When is the next follow up mentioned?"
        )
    action_list: list[str] = Field(
        description="List of specific tasks or next steps"
        )
    patient_number: Optional[str] = Field(
        default=None, 
        description="Was is the patient's number?"
        )
    patient_sex: GenderIdentity = Field(
        default=GenderIdentity.UNKNOWN, 
        description="Infer the sex of the patient. Sophie is always Female."
        )
    urgency_score: Optional[int] = Field(
        default=None, 
        description="Score 1-10 or None if not mentioned"
        )
    summary: str = Field(
        description="A 2-sentence executive summary of the discussion"
        )
    relative_fu_phrase: Optional[str] = Field(
        default=None, 
        description="The relative follow up time mentioned, e.g., '3 weeks' or '2 months'. Leave None if not mentioned."
        )
    
    # TO ADD ITEMS, ADD THEM HERE, UPDATE LINE 166 (CSV Header), AND line 169 onwards for fields to include...!!!

# Load Whisper once on startup (using CPU/int8 for low memory usage)
print("Loading Transcription Model...")
# check out: https://github.com/openai/whisper tiny, base, small, medium, large turbo
stt_model = WhisperModel("medium", device="cpu", compute_type="int8") 

def load_processed_history():
    """Reads existing CSV to avoid duplicates."""
    if os.path.exists(config.CSV_FILE):
        with open(config.CSV_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                config.CHECKED_FILES.add(row['ID'])
    print(f"There are {len(config.CHECKED_FILES)} historical records.")

def process_file(file_path):
    path = Path(file_path)
    file_id = path.stem
    
    if file_id in config.CHECKED_FILES or path.suffix.lower() not in config.SUPPORTED_FORMATS:
        return # do nothing, only process supported files

    print(f"\n--- New Task: {path.name} ---")
    
    # get dates
    timestamp = os.path.getctime(path) # get gct from file
    created_date = datetime.datetime.fromtimestamp(timestamp) # convert to datetime object for calculations
    created_date_string = created_date.strftime('%Y-%m-%d %H:%M:%S') # convert to string for csv file
    fu_date_final = "N/A" # set final follow up to N/A, so there is always a value

    # convert file (.aifc in from Apple specifically)
    active_audio_path = str(path)
    is_temp = False
    
    if path.suffix.lower() == '.aifc': 
        print("Converting AIFC to WAV...")
        temp_audio = AudioSegment.from_file(path)
        active_audio_path = f"{file_id}_temp.wav"
        temp_audio.export(active_audio_path, format="wav")
        is_temp = True # set to true, so the file can be deleted later

    try:
        # transcribe
        print("Transcribing audio...")
        # 'task="transcribe"' ensures it doesn't translate as it detects foreign accents and translates!
        # 'language="en"' (example for english) forces the language. (https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes)
        # Remove 'language' if you want it to auto-detect but stay in the original.
        segments, _ = stt_model.transcribe(active_audio_path, task="transcribe", language="en")
        transcript_text = " ".join([s.text for s in segments])

        # LLM Extraction using local model (no upload to web), set rules to help interpretation
        print("Extracting info with Local AI...")
        data = config.client.chat.completions.create(
            model="llama3",
            response_model=ExtractionSchema,
            messages=[
                {
                    "role": "system", 
                    "content": """You are an expert at inferring context from dictations. 
                    Today's date is {created_date_string}.
                    
                    RULES:
                    1. MEETING TYPE: If the speaker mentions 'seeing' someone, 'met with', or 'sitting with', it is 'Face-to-Face'. If they mention 'called', 'on the line', or 'spoke to', it is 'Telephone'.
                    2. GENDER: Infer gender from first names (e.g., Sophie/Emma = Female, John/Robert = Male).
                    3. DATE STANDARDIZATION: Always convert 'next' phrases into numbers for 'relative_fu_phrase':
                    - 'next year' -> '1 year'
                    - 'next month' -> '1 month'
                    - 'next week' -> '1 week'
                    
                    EXAMPLES:
                    - Transcript: 'Spoke with Sophie today, follow up next year.' -> Type: Telephone, Sex: Female, relative_fu_phrase: '1 year'
                    - Transcript: 'Met with John in person, see him next month.' -> Type: Face-to-Face, Sex: Male, relative_fu_phrase: '1 month'
                    """
                },
                {"role": "user", "content": f"Extract details from this transcript: {transcript_text}"}
            ]
        )

        # calculate follow up date
        follow_up_dt = None # set to none in case not mentioned
        if data.relative_fu_phrase:
            # Standardize 'next' to '1' just in case the LLM has not detected it (extra loop)
            clean_phrase = data.relative_fu_phrase.lower().replace("next ", "1 ")
            # Use dateparser to calculate the date relative file date
            # add 'in ' to the phrase to make it clear it's in the future
            follow_up_dt = dateparser.parse(
                f"in {clean_phrase}", 
                settings={'RELATIVE_BASE': created_date}
                )
        if follow_up_dt:
            fu_date_final = follow_up_dt.strftime('%Y-%m-%d') # if exists, convert to string for csv 

        # save to CSV
        file_exists = os.path.isfile(config.CSV_FILE)
        with open(config.CSV_FILE, 'a', newline='', encoding='utf-8-sig') as f: # use encoding to ascertain translated correctly
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["ID", "Date_Created", "Type", "Number", "Sex",
                                 "Follow_Up", "FU Date",  "Summary", "Urgency", 
                                 "Actions", "Full_Transcript"])
            writer.writerow([
                file_id, 
                created_date_string, 
                data.meeting_type, 
                data.patient_number,
                data.patient_sex,
                data.follow_up_time, 
                fu_date_final,
                data.summary,
                data.urgency_score if data.urgency_score is not None else "N/A",
                " | ".join(data.action_list), transcript_text
            ])
        
        config.CHECKED_FILES.add(file_id)
        print(f"Successfully logged {file_id}")

    finally:
        if is_temp and os.path.exists(active_audio_path):
            os.remove(active_audio_path) # remove the temp conversion file if it was created

class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            time.sleep(2) # Buffer to allow finish writing the file
            process_file(event.src_path)

