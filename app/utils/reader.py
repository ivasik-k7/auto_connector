import csv
import json
import os
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod


class FileReaderStrategy(ABC):
    @abstractmethod
    def read(self, file_path: str):
        pass


class JsonFileReader(FileReaderStrategy):
    def read(self, file_path: str) -> list[dict]:
        with open(file_path, "r") as f:
            return json.load(f)


class TxtFileReader(FileReaderStrategy):
    def read(self, file_path: str) -> list[dict]:
        with open(file_path, "r") as f:
            return [json.loads(line) for line in f.readlines()]


class CsvFileReader(FileReaderStrategy):
    def read(self, file_path: str) -> list[dict]:
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            return [row for row in reader]


class XmlFileReader(FileReaderStrategy):
    def read(self, file_path: str) -> list[dict]:
        tree = ET.parse(file_path)
        root = tree.getroot()
        return [{elem.tag: elem.text for elem in child} for child in root]


class FileReaderFactory:
    @staticmethod
    def get_file_reader(file_path: str) -> FileReaderStrategy:
        _, ext = os.path.splitext(file_path)
        if ext == ".json":
            return JsonFileReader()
        elif ext == ".txt":
            return TxtFileReader()
        elif ext == ".csv":
            return CsvFileReader()
        elif ext == ".xml":
            return XmlFileReader()
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
