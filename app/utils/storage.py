import json
from abc import ABC, abstractmethod


class StorageManager(ABC):
    @abstractmethod
    def add(self, key: str, content: any) -> None:
        """Add content associated with a key, ensuring uniqueness."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete content associated with a key."""
        pass

    @abstractmethod
    def read(self, key: str) -> any:
        """Read content associated with a key."""
        pass

    @abstractmethod
    def all(self) -> dict:
        """Return all key-value pairs."""
        pass


class InMemoryStorage(StorageManager):
    def __init__(self):
        self.storage = {}

    def add(self, key: str, content: any) -> bool:
        if key not in self.storage:
            self.storage[key] = content
            return True
        else:
            return False  # Key already exists

    def delete(self, key: str) -> None:
        if key in self.storage:
            del self.storage[key]

    def read(self, key: str) -> any:
        return self.storage.get(key, None)

    def all(self) -> dict:
        return self.storage.copy()


class FileStorage(StorageManager):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = []
        self._load_from_file()

    def add(self, key: str, content: any) -> bool:
        if not self._exists_in_data(key):
            self.data.append({"key": key, "content": content})
            self._save_to_file()
            return True
        else:
            return False  # Key already exists

    def delete(self, key: str) -> None:
        self.data = [item for item in self.data if item["key"] != key]
        self._save_to_file()

    def read(self, key: str) -> any:
        for item in self.data:
            if item["key"] == key:
                return item["content"]
        return None

    def all(self) -> dict:
        all_data = {item["key"]: item["content"] for item in self.data}
        return all_data

    def _load_from_file(self) -> None:
        try:
            with open(self.file_path, "r") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = []

    def _save_to_file(self) -> None:
        with open(self.file_path, "w") as f:
            json.dump(self.data, f, indent=4)

    def _exists_in_data(self, key: str) -> bool:
        for item in self.data:
            if item["key"] == key:
                return True
        return False
