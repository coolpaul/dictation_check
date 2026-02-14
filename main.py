from pathlib import Path
from watchdog.observers import Observer
from config import config
from program import dictation
import time

if __name__ == "__main__":
    dictation.load_processed_history()

    print(f"Checking {config.WATCH_DIR} for unprocessed files...")
    for f in Path(config.WATCH_DIR).iterdir():
        dictation.process_file(f)

    # Start monitoring
    observer = Observer()
    observer.schedule(dictation.NewFileHandler(), config.WATCH_DIR, recursive=False)
    observer.start()
    print(f"Watcher active. Add files to {config.WATCH_DIR} to begin.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()





 