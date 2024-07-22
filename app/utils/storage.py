import csv
import json
import os
import threading
import time
from typing import Callable, Dict, List


class MultiThreadStorage:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = []
        self._load_from_file()
        self._lock = threading.Lock()
        self._dirty = False
        self._save_interval = 5
        self._start_autosave()

    def add(self, item) -> None:
        """Adds an item to the data list."""
        with self._lock:
            self.data.append(item)
            self._dirty = True

    def save(self) -> None:
        """Saves the current state of data to the file."""
        with self._lock:
            if not self._dirty:
                return
            with open(self.file_path, "w") as f:
                json.dump(self.data, f)
            self._dirty = False

    def _load_from_file(self) -> None:
        """Loads data from the file if it exists, otherwise initializes an empty list."""
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                self.data = json.load(f)
        else:
            self.data = []

    def _start_autosave(self):
        def autosave():
            while True:
                time.sleep(self._save_interval)
                self.save()

        thread = threading.Thread(target=autosave, daemon=True)
        thread.start()

    def save_as_csv(self, csv_file_path: str) -> None:
        """Saves the current state of data to a CSV file."""
        with self._lock:
            if not self.data:
                return
            with open(csv_file_path, "w", newline="") as csvfile:
                fieldnames = ["id", "login", "lang", "avatar", "type", "url"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for item in self.data:
                    writer.writerow(item)

    def query(self, condition: Callable[[Dict], bool]) -> List[Dict]:
        """Query the data based on a condition."""
        with self._lock:
            return [item for item in self.data if condition(item)]


class StorageManager:
    def __init__(self, file_path: str):
        self.storage = MultiThreadStorage(file_path)

    def __enter__(self):
        return self.storage

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.storage.save()
