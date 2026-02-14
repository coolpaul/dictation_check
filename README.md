# Dictation - infer outcome

This program checks audio files in the dictations directory, transcribes them to text and infers the outcome.
The outcomes and text will be saved in the results.csv file.
Included is an active 'watcher' that remains active and monitors the dictations directory for new files. 
If a new audio file is detected, the file will be transcribed, the outcome will be inferred and added to the results.csv file.

- Configuration can be altered in the config/config.py file
- The main program is located in program/dictation.py
- Dependencies are listed below and in requirements.txt

Audio files are not uploaded to the web.
A local LLM installation of llama3 is required. 
Llama3 can be installed from https://ollama.com:

curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3

To run:
run main.py
results.csv should be created in root directory

To check, the results.csv file can be deleted and main.py restarted.

**Requirements**

| dateparser==1.3.0         |
| faster_whisper==1.2.1     |
| instructor==1.14.5        |
| openai==2.21.0            |
| pydantic==2.12.5          |
| pydub==0.25.1             |
| watchdog==6.0.0           |


