import os
import threading
from typing import Callable, Dict, List

from app.utils.reader import FileReaderFactory
from app.utils.writer import FileWriterFactory


class MultiThreadStorage:
    def __init__(
        self,
        file_path: str,
        output_path: str | None = None,
        autosave: bool = False,
        save_interval: int = 5,
    ):
        ##
        self.file_path = file_path
        self.output_path = output_path or file_path
        ###
        self.data = []
        self._load_from_file()
        ###
        self._lock = threading.Lock()
        self._dirty = False

        # following lines to enable autosave
        self._save_interval = save_interval
        if autosave:
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
            writer = FileWriterFactory.get_file_writer(self.output_path)
            writer.write(self.output_path, self.data)
            self._dirty = False

    def _load_from_file(self) -> None:
        """Loads data from the file if it exists, otherwise initializes an empty list."""
        if os.path.exists(self.file_path):
            reader = FileReaderFactory.get_file_reader(self.file_path)
            self.data = reader.read(self.file_path)
        else:
            self.data = []

    def _autosave(self):
        """Periodically saves the data to the file."""
        while True:
            threading.Event().wait(self._save_interval)
            self.save()

    def _start_autosave(self):
        """Starts the autosave thread."""
        autosave_thread = threading.Thread(target=self._autosave, daemon=True)
        autosave_thread.start()

    def query(self, condition: Callable[[Dict], bool]) -> List[Dict]:
        """Query the data based on a condition."""
        with self._lock:
            return [item for item in self.data if condition(item)]


class StorageManager:
    def __init__(
        self,
        file_path: str,
        output_path: str | None = None,
        autosave: bool = False,
        save_interval: int = 5,
    ):
        self.input_path = file_path
        self.output_path = output_path or file_path
        self.storage = MultiThreadStorage(
            self.input_path,
            self.output_path,
            autosave,
            save_interval,
        )

    def __enter__(self):
        return self.storage

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.storage.save()
