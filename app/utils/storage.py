"""
Enhanced Multi-threaded Storage with Fallback Compatibility and Advanced Features
"""

import os
import shutil
import threading
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.utils.logger import setup_logger
from app.utils.reader import FileReaderFactory
from app.utils.writer import FileWriterFactory

logger = setup_logger(__name__, log_file="storage.log")


class StorageMode(Enum):
    """Storage operation modes."""

    APPEND = "append"
    OVERWRITE = "overwrite"
    MERGE = "merge"


class BackupStrategy(Enum):
    """Backup strategies for data preservation."""

    NONE = "none"
    TIMESTAMPED = "timestamped"
    ROLLING = "rolling"
    VERSIONED = "versioned"


class StorageException(Exception):
    """Base exception for storage operations."""

    pass


class CorruptedDataException(StorageException):
    """Raised when data file is corrupted."""

    pass


class BackupManager:
    """Manages backup operations with multiple strategies."""

    def __init__(
        self,
        strategy: BackupStrategy = BackupStrategy.TIMESTAMPED,
        max_backups: int = 5,
        backup_dir: Optional[str] = None,
    ):
        self.strategy = strategy
        self.max_backups = max_backups
        self.backup_dir = backup_dir

    def create_backup(self, file_path: str) -> Optional[str]:
        """
        Create a backup of the file based on strategy.

        Args:
            file_path: Path to file to backup

        Returns:
            Path to backup file or None
        """
        if not os.path.exists(file_path):
            return None

        if self.strategy == BackupStrategy.NONE:
            return None

        try:
            backup_path = self._get_backup_path(file_path)

            # Create backup directory if needed
            backup_dir = os.path.dirname(backup_path)
            if backup_dir:
                os.makedirs(backup_dir, exist_ok=True)

            # Copy file
            shutil.copy2(file_path, backup_path)
            logger.info(f"📦 Backup created: {backup_path}")

            # Cleanup old backups
            if self.strategy in (BackupStrategy.TIMESTAMPED, BackupStrategy.ROLLING):
                self._cleanup_old_backups(file_path)

            return backup_path

        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return None

    def _get_backup_path(self, file_path: str) -> str:
        """Generate backup file path based on strategy."""
        base_dir = self.backup_dir or os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)

        if self.strategy == BackupStrategy.TIMESTAMPED:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return os.path.join(base_dir, f"{name}_backup_{timestamp}{ext}")

        elif self.strategy == BackupStrategy.ROLLING:
            # Find next available backup number
            for i in range(1, self.max_backups + 1):
                backup_path = os.path.join(base_dir, f"{name}_backup_{i}{ext}")
                if not os.path.exists(backup_path):
                    return backup_path
            # If all slots full, overwrite oldest
            return os.path.join(base_dir, f"{name}_backup_1{ext}")

        elif self.strategy == BackupStrategy.VERSIONED:
            version = self._get_next_version(file_path)
            return os.path.join(base_dir, f"{name}_v{version}{ext}")

        return file_path + ".bak"

    def _get_next_version(self, file_path: str) -> int:
        """Get next version number for versioned backups."""
        base_dir = self.backup_dir or os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)

        version = 1
        while True:
            backup_path = os.path.join(base_dir, f"{name}_v{version}{ext}")
            if not os.path.exists(backup_path):
                return version
            version += 1
            if version > 1000:  # Safety limit
                return 1

    def _cleanup_old_backups(self, file_path: str):
        """Remove old backups exceeding max_backups limit."""
        try:
            base_dir = self.backup_dir or os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)

            # Find all backups
            backups = []
            for file in os.listdir(base_dir):
                if file.startswith(f"{name}_backup") and file.endswith(ext):
                    backup_path = os.path.join(base_dir, file)
                    backups.append((backup_path, os.path.getmtime(backup_path)))

            # Sort by modification time
            backups.sort(key=lambda x: x[1], reverse=True)

            # Remove oldest backups
            for backup_path, _ in backups[self.max_backups :]:
                os.remove(backup_path)
                logger.debug(f"🗑️  Removed old backup: {backup_path}")

        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")

    def restore_from_backup(
        self, file_path: str, backup_path: Optional[str] = None
    ) -> bool:
        """
        Restore file from backup.

        Args:
            file_path: Original file path
            backup_path: Specific backup to restore, or latest if None

        Returns:
            True if restore successful
        """
        try:
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                logger.info(f"✅ Restored from backup: {backup_path}")
                return True

            # Find latest backup
            base_dir = self.backup_dir or os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)

            backups = []
            for file in os.listdir(base_dir):
                if file.startswith(f"{name}_backup") and file.endswith(ext):
                    backup_file = os.path.join(base_dir, file)
                    backups.append((backup_file, os.path.getmtime(backup_file)))

            if not backups:
                logger.warning("No backups found to restore")
                return False

            # Get most recent backup
            latest_backup = max(backups, key=lambda x: x[1])[0]
            shutil.copy2(latest_backup, file_path)
            logger.info(f"✅ Restored from latest backup: {latest_backup}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to restore from backup: {e}")
            return False


class DataValidator:
    """Validates data integrity and structure."""

    @staticmethod
    def validate_structure(data: Any, expected_type: type = list) -> bool:
        """Validate data structure type."""
        return isinstance(data, expected_type)

    @staticmethod
    def validate_items(
        data: List[Dict], required_keys: Optional[List[str]] = None
    ) -> bool:
        """
        Validate that all items have required keys.

        Args:
            data: List of dictionaries to validate
            required_keys: Keys that must be present

        Returns:
            True if valid
        """
        if not isinstance(data, list):
            return False

        if not required_keys:
            return True

        for item in data:
            if not isinstance(item, dict):
                return False
            if not all(key in item for key in required_keys):
                return False

        return True

    @staticmethod
    def sanitize_data(data: List[Dict]) -> List[Dict]:
        """Remove invalid items from data."""
        valid_data = []
        for item in data:
            if isinstance(item, dict) and item:
                valid_data.append(item)
        return valid_data


class MultiThreadStorage:
    """
    Enhanced thread-safe storage with fallback compatibility.
    """

    def __init__(
        self,
        file_path: str,
        output_path: Optional[str] = None,
        autosave: bool = False,
        save_interval: int = 5,
        backup_strategy: BackupStrategy = BackupStrategy.TIMESTAMPED,
        max_backups: int = 5,
        fallback_formats: Optional[List[str]] = None,
        mode: StorageMode = StorageMode.APPEND,
        validate_on_load: bool = True,
        required_keys: Optional[List[str]] = None,
    ):
        """
        Initialize storage with enhanced features.

        Args:
            file_path: Input file path
            output_path: Output file path (defaults to input path)
            autosave: Enable automatic periodic saving
            save_interval: Seconds between autosaves
            backup_strategy: Strategy for creating backups
            max_backups: Maximum number of backups to keep
            fallback_formats: List of fallback file formats to try
            mode: Storage operation mode (append/overwrite/merge)
            validate_on_load: Validate data structure on load
            required_keys: Required keys for validation
        """
        self.file_path = file_path
        self.output_path = output_path or file_path
        self.mode = mode
        self.validate_on_load = validate_on_load
        self.required_keys = required_keys or []

        # Data storage
        self.data: List[Dict] = []
        self._metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "total_operations": 0,
            "last_save": None,
            "last_load": None,
        }

        # Thread safety
        self._lock = threading.RLock()
        self._dirty = False

        # Backup management
        self.backup_manager = BackupManager(
            strategy=backup_strategy, max_backups=max_backups
        )

        # Fallback formats
        self.fallback_formats = fallback_formats or [".csv", ".json", ".jsonl"]

        # Load data with fallback
        self._load_from_file_with_fallback()

        # Autosave
        self._save_interval = save_interval
        self._autosave_thread: Optional[threading.Thread] = None
        self._stop_autosave = threading.Event()

        if autosave:
            self._start_autosave()

        logger.info(
            f"✅ Storage initialized: {self.file_path} ({len(self.data)} items)"
        )

    def add(self, item: Dict[str, Any]) -> None:
        """
        Add an item to the data list with validation.

        Args:
            item: Dictionary item to add
        """
        if not isinstance(item, dict):
            logger.warning(f"⚠️  Invalid item type: {type(item)}")
            return

        with self._lock:
            self.data.append(item)
            self._dirty = True
            self._metadata["total_operations"] += 1

    def add_batch(self, items: List[Dict[str, Any]]) -> int:
        """
        Add multiple items at once.

        Args:
            items: List of items to add

        Returns:
            Number of items successfully added
        """
        added = 0
        with self._lock:
            for item in items:
                if isinstance(item, dict):
                    self.data.append(item)
                    added += 1

            if added > 0:
                self._dirty = True
                self._metadata["total_operations"] += added

        logger.info(f"📦 Batch added: {added}/{len(items)} items")
        return added

    def update(self, condition: Callable[[Dict], bool], updates: Dict[str, Any]) -> int:
        """
        Update items matching condition.

        Args:
            condition: Function to match items
            updates: Dictionary of updates to apply

        Returns:
            Number of items updated
        """
        updated = 0
        with self._lock:
            for item in self.data:
                if condition(item):
                    item.update(updates)
                    updated += 1

            if updated > 0:
                self._dirty = True
                self._metadata["total_operations"] += updated

        logger.info(f"✏️  Updated {updated} items")
        return updated

    def remove(self, condition: Callable[[Dict], bool]) -> int:
        """
        Remove items matching condition.

        Args:
            condition: Function to match items

        Returns:
            Number of items removed
        """
        with self._lock:
            original_count = len(self.data)
            self.data = [item for item in self.data if not condition(item)]
            removed = original_count - len(self.data)

            if removed > 0:
                self._dirty = True
                self._metadata["total_operations"] += removed

        logger.info(f"🗑️  Removed {removed} items")
        return removed

    def query(self, condition: Callable[[Dict], bool]) -> List[Dict]:
        """
        Query data based on a condition.

        Args:
            condition: Function to match items

        Returns:
            List of matching items
        """
        with self._lock:
            return [item.copy() for item in self.data if condition(item)]

    def get_all(self) -> List[Dict]:
        """Get all data (thread-safe copy)."""
        with self._lock:
            return self.data.copy()

    def clear(self) -> None:
        """Clear all data."""
        with self._lock:
            self.data.clear()
            self._dirty = True
            self._metadata["total_operations"] += 1
        logger.info("🗑️  Storage cleared")

    def save(self, create_backup: bool = True) -> bool:
        """
        Save current data to file.

        Args:
            create_backup: Whether to create backup before saving

        Returns:
            True if save successful
        """
        with self._lock:
            if not self._dirty:
                logger.debug("No changes to save")
                return True

            try:
                # Create backup if file exists
                if create_backup and os.path.exists(self.output_path):
                    self.backup_manager.create_backup(self.output_path)

                # Validate data before saving
                if self.validate_on_load:
                    validator = DataValidator()
                    if not validator.validate_structure(self.data):
                        logger.error("❌ Invalid data structure")
                        return False

                # Write data
                writer = FileWriterFactory.get_file_writer(self.output_path)
                writer.write(self.output_path, self.data)

                self._dirty = False
                self._metadata["last_save"] = datetime.now().isoformat()

                logger.info(f"💾 Saved {len(self.data)} items to {self.output_path}")
                return True

            except Exception as e:
                logger.error(f"❌ Save failed: {e}", exc_info=True)
                return False

    def _load_from_file_with_fallback(self) -> None:
        """Load data with fallback format support."""
        # Try primary file
        if self._try_load_file(self.file_path):
            return

        logger.warning(
            f"⚠️  Failed to load {self.file_path}, trying fallback formats..."
        )

        # Try fallback formats
        base_path = os.path.splitext(self.file_path)[0]
        for ext in self.fallback_formats:
            fallback_path = base_path + ext
            if os.path.exists(fallback_path):
                logger.info(f"🔄 Trying fallback: {fallback_path}")
                if self._try_load_file(fallback_path):
                    logger.info(f"✅ Loaded from fallback: {fallback_path}")
                    return

        # No file found, start with empty data
        logger.info("📝 No existing file found, starting with empty storage")
        self.data = []
        self._metadata["last_load"] = datetime.now().isoformat()

    def _try_load_file(self, file_path: str) -> bool:
        """
        Attempt to load data from a file.

        Args:
            file_path: Path to file to load

        Returns:
            True if load successful
        """
        if not os.path.exists(file_path):
            return False

        try:
            reader = FileReaderFactory.get_file_reader(file_path)
            loaded_data = reader.read(file_path)

            # Validate loaded data
            if self.validate_on_load:
                validator = DataValidator()

                if not validator.validate_structure(loaded_data):
                    logger.error(f"❌ Invalid data structure in {file_path}")
                    raise CorruptedDataException("Invalid data structure")

                if self.required_keys:
                    if not validator.validate_items(loaded_data, self.required_keys):
                        logger.warning(
                            f"⚠️  Some items missing required keys, sanitizing..."
                        )
                        loaded_data = validator.sanitize_data(loaded_data)

            # Apply storage mode
            if self.mode == StorageMode.APPEND:
                self.data.extend(loaded_data)
            elif self.mode == StorageMode.OVERWRITE:
                self.data = loaded_data
            elif self.mode == StorageMode.MERGE:
                # Merge by unique ID if available
                existing_ids = {item.get("id") for item in self.data if "id" in item}
                new_items = [
                    item for item in loaded_data if item.get("id") not in existing_ids
                ]
                self.data.extend(new_items)

            self._metadata["last_load"] = datetime.now().isoformat()
            logger.info(f"✅ Loaded {len(loaded_data)} items from {file_path}")
            return True

        except CorruptedDataException:
            # Try to restore from backup
            logger.warning("⚠️  Data corrupted, attempting restore from backup...")
            if self.backup_manager.restore_from_backup(file_path):
                return self._try_load_file(file_path)  # Retry after restore
            return False

        except Exception as e:
            logger.error(f"❌ Failed to load {file_path}: {e}", exc_info=True)
            return False

    def _autosave(self):
        """Periodically save data to file."""
        logger.info(f"🔄 Autosave started (interval: {self._save_interval}s)")

        while not self._stop_autosave.is_set():
            self._stop_autosave.wait(self._save_interval)
            if self._dirty and not self._stop_autosave.is_set():
                self.save(create_backup=False)  # Don't backup on autosave

    def _start_autosave(self):
        """Start the autosave thread."""
        if self._autosave_thread is None or not self._autosave_thread.is_alive():
            self._autosave_thread = threading.Thread(
                target=self._autosave, daemon=True, name="StorageAutosave"
            )
            self._autosave_thread.start()

    def stop_autosave(self):
        """Stop the autosave thread gracefully."""
        if self._autosave_thread and self._autosave_thread.is_alive():
            self._stop_autosave.set()
            self._autosave_thread.join(timeout=5)
            logger.info("🛑 Autosave stopped")

    def get_metadata(self) -> Dict[str, Any]:
        """Get storage metadata."""
        with self._lock:
            return {
                **self._metadata,
                "total_items": len(self.data),
                "dirty": self._dirty,
                "file_path": self.file_path,
                "output_path": self.output_path,
            }

    def __len__(self) -> int:
        """Return number of items in storage."""
        with self._lock:
            return len(self.data)

    def __contains__(self, condition: Callable[[Dict], bool]) -> bool:
        """Check if any item matches condition."""
        with self._lock:
            return any(condition(item) for item in self.data)

    def __del__(self):
        """Cleanup on deletion."""
        self.stop_autosave()
        if self._dirty:
            logger.warning("⚠️  Storage deleted with unsaved changes")


class StorageManager:
    """
    Enhanced context manager for storage operations.
    """

    def __init__(
        self,
        file_path: str,
        output_path: Optional[str] = None,
        autosave: bool = False,
        save_interval: int = 5,
        backup_strategy: BackupStrategy = BackupStrategy.TIMESTAMPED,
        max_backups: int = 5,
        fallback_formats: Optional[List[str]] = None,
        mode: StorageMode = StorageMode.APPEND,
        validate_on_load: bool = True,
        required_keys: Optional[List[str]] = None,
        auto_backup_on_exit: bool = True,
    ):
        """
        Initialize storage manager with enhanced features.

        Args:
            file_path: Input file path
            output_path: Output file path
            autosave: Enable automatic saving
            save_interval: Autosave interval in seconds
            backup_strategy: Backup creation strategy
            max_backups: Maximum backups to keep
            fallback_formats: Fallback file formats
            mode: Storage mode (append/overwrite/merge)
            validate_on_load: Validate data on load
            required_keys: Required keys for validation
            auto_backup_on_exit: Create backup on context exit
        """
        self.input_path = file_path
        self.output_path = output_path or file_path
        self.auto_backup_on_exit = auto_backup_on_exit

        self.storage = MultiThreadStorage(
            file_path=self.input_path,
            output_path=self.output_path,
            autosave=autosave,
            save_interval=save_interval,
            backup_strategy=backup_strategy,
            max_backups=max_backups,
            fallback_formats=fallback_formats,
            mode=mode,
            validate_on_load=validate_on_load,
            required_keys=required_keys,
        )

    def __enter__(self) -> MultiThreadStorage:
        """Enter context manager."""
        return self.storage

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager with cleanup."""
        try:
            # Stop autosave
            self.storage.stop_autosave()

            # Save with backup if no exception occurred
            if exc_type is None:
                self.storage.save(create_backup=self.auto_backup_on_exit)
            else:
                # Save without backup if there was an error
                logger.error(f"⚠️  Exception during storage operation: {exc_val}")
                self.storage.save(create_backup=False)

            # Print summary
            metadata = self.storage.get_metadata()
            logger.info(
                f"📊 Storage session complete: "
                f"{metadata['total_items']} items, "
                f"{metadata['total_operations']} operations"
            )

        except Exception as e:
            logger.error(f"❌ Error during storage cleanup: {e}", exc_info=True)

        return False  # Don't suppress exceptions


# Convenience functions
@contextmanager
def managed_storage(file_path: str, **kwargs) -> MultiThreadStorage:
    """
    Convenience context manager for storage.

    Usage:
        with managed_storage('data.csv', autosave=True) as storage:
            storage.add({"id": 1, "name": "test"})
    """
    manager = StorageManager(file_path, **kwargs)
    try:
        yield manager.storage
    finally:
        manager.__exit__(None, None, None)
