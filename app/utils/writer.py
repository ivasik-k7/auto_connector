import csv
import datetime
import json
import logging
import os
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class FileWriterStrategy(ABC):
    @abstractmethod
    def write(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        """
        Write data to file.

        Args:
            file_path: Path to output file
            data: List of dictionaries to write

        Returns:
            True if successful, False otherwise
        """
        pass

    def validate_data(self, data: Any) -> bool:
        """Validate data before writing."""
        if not isinstance(data, list):
            logger.error(f"Invalid data type: {type(data)}, expected list")
            return False

        if not all(isinstance(item, dict) for item in data):
            logger.error("All data items must be dictionaries")
            return False

        return True


class JsonFileWriter(FileWriterStrategy):
    def write(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        try:
            if not self.validate_data(data):
                return False

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False, default=str)

            logger.debug(
                f"Successfully wrote {len(data)} items to JSON file: {file_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to write JSON file {file_path}: {e}")
            return False


class TxtFileWriter(FileWriterStrategy):
    def write(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        try:
            if not self.validate_data(data):
                return False

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                for item in data:
                    # Convert to JSON string for consistent formatting
                    f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

            logger.debug(
                f"Successfully wrote {len(data)} items to text file: {file_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to write text file {file_path}: {e}")
            return False


class CsvFileWriter(FileWriterStrategy):
    def write(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        try:
            if not self.validate_data(data):
                return False

            if not data:
                logger.warning("No data to write to CSV")
                # Create empty file with header if possible
                self._create_empty_csv(file_path)
                return True

            # Get all unique keys from all dictionaries
            column_names = sorted({key for item in data for key in item.keys()})

            if not column_names:
                logger.warning("No columns found in data")
                return False

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=column_names)
                writer.writeheader()

                # Write rows, filling missing values with empty strings
                for item in data:
                    row = {key: item.get(key, "") for key in column_names}
                    # Convert non-serializable values to string
                    row = {
                        k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                        for k, v in row.items()
                    }
                    writer.writerow(row)

            logger.debug(
                f"Successfully wrote {len(data)} items to CSV file: {file_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to write CSV file {file_path}: {e}")
            return False

    def _create_empty_csv(self, file_path: str) -> bool:
        """Create an empty CSV file with just headers."""
        try:
            with open(file_path, "w", encoding="utf-8", newline="") as file:
                file.write("")  # Create empty file
            return True
        except Exception as e:
            logger.error(f"Failed to create empty CSV file {file_path}: {e}")
            return False


class XmlFileWriter(FileWriterStrategy):
    def write(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        try:
            if not self.validate_data(data):
                return False

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            root = ET.Element("data")

            # Add metadata
            metadata = ET.SubElement(root, "metadata")
            ET.SubElement(metadata, "count").text = str(len(data))
            ET.SubElement(metadata, "timestamp").text = str(datetime.now().isoformat())

            # Add items
            items_element = ET.SubElement(root, "items")
            for item in data:
                item_element = ET.SubElement(items_element, "item")
                for key, value in item.items():
                    # Sanitize key names for XML
                    safe_key = self._sanitize_xml_key(key)
                    field_element = ET.SubElement(item_element, safe_key)
                    field_element.text = str(value) if value is not None else ""

            tree = ET.ElementTree(root)

            # Pretty print XML
            self._indent_xml(root)

            tree.write(file_path, encoding="utf-8", xml_declaration=True)

            logger.debug(
                f"Successfully wrote {len(data)} items to XML file: {file_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to write XML file {file_path}: {e}")
            return False

    def _sanitize_xml_key(self, key: str) -> str:
        """Sanitize key names for XML element names."""
        # Replace invalid XML element name characters with underscore
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9_\-.]", "_", key)
        # Ensure it starts with a letter or underscore
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != "_":
            sanitized = "_" + sanitized
        return sanitized or "field"

    def _indent_xml(self, elem: ET.Element, level: int = 0):
        """Pretty-format XML with indentation."""
        indent = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for elem in elem:
                self._indent_xml(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent


class JsonlFileWriter(FileWriterStrategy):
    """Writer for JSON Lines format (one JSON object per line)."""

    def write(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        try:
            if not self.validate_data(data):
                return False

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                for item in data:
                    json_line = json.dumps(item, ensure_ascii=False, default=str)
                    f.write(json_line + "\n")

            logger.debug(
                f"Successfully wrote {len(data)} items to JSONL file: {file_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to write JSONL file {file_path}: {e}")
            return False


class FileWriterFactory:
    _writers = {
        ".json": JsonFileWriter,
        ".txt": TxtFileWriter,
        ".csv": CsvFileWriter,
        ".xml": XmlFileWriter,
        ".jsonl": JsonlFileWriter,
    }

    @staticmethod
    def get_file_writer(file_path: str) -> FileWriterStrategy:
        """
        Get appropriate file writer based on file extension.

        Args:
            file_path: Path to output file

        Returns:
            FileWriterStrategy instance

        Raises:
            ValueError: If file extension is not supported
        """
        _, ext = os.path.splitext(file_path.lower())

        if ext in FileWriterFactory._writers:
            writer_class = FileWriterFactory._writers[ext]
            return writer_class()
        else:
            raise ValueError(
                f"Unsupported file extension: {ext}. "
                f"Supported extensions: {list(FileWriterFactory._writers.keys())}"
            )

    @staticmethod
    def register_writer(extension: str, writer_class: type) -> None:
        """
        Register a custom writer for a file extension.

        Args:
            extension: File extension (e.g., '.yaml')
            writer_class: Custom writer class implementing FileWriterStrategy
        """
        if not extension.startswith("."):
            extension = "." + extension
        FileWriterFactory._writers[extension.lower()] = writer_class

    @staticmethod
    def get_supported_extensions() -> List[str]:
        """Get list of supported file extensions."""
        return list(FileWriterFactory._writers.keys())
