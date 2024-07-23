import csv
import json
import os
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod


class FileWriterStrategy(ABC):
    @abstractmethod
    def write(self, file_path: str, data):
        pass


class JsonFileWriter(FileWriterStrategy):
    def write(self, file_path: str, data):
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)


class TxtFileWriter(FileWriterStrategy):
    def write(self, file_path: str, data: dict):
        with open(file_path, "w") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")


class CsvFileWriter(FileWriterStrategy):
    def write(self, file_path: str, data):
        if not data:
            raise ValueError("No data provided!")

        column_names = sorted({key for item in data for key in item})

        with open(file_path, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=column_names)
            writer.writeheader()
            writer.writerows(data)


class XmlFileWriter(FileWriterStrategy):
    def write(self, file_path: str, data: list[dict]) -> None:
        root = ET.Element("root")
        for item in data:
            child = ET.SubElement(root, "item")
            for key, value in item.items():
                elem = ET.SubElement(child, key)
                elem.text = str(value)

        tree = ET.ElementTree(root)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)


class FileWriterFactory:
    @staticmethod
    def get_file_writer(file_path: str) -> FileWriterStrategy:
        _, ext = os.path.splitext(file_path)
        if ext == ".json":
            return JsonFileWriter()
        elif ext == ".txt":
            return TxtFileWriter()
        elif ext == ".csv":
            return CsvFileWriter()
        elif ext == ".xml":
            return XmlFileWriter()
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
