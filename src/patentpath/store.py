"""Load and access patent records from the JSON data file."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RecordStore:
    """Store records loaded from a JSON file."""

    def __init__(self, data_file: Path) -> None:
        self.data_file = data_file
        self.records: list[dict[str, Any]] = []

    def load(self) -> None:
        """Load records from the configured JSON file."""
        if not self.data_file.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_file}")

        with self.data_file.open(encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("The data file must contain a JSON list.")

        self.records = data

        logger.info(
            "records loaded",
            extra={"records": len(self.records)},
        )

    def list_records(self) -> list[dict[str, Any]]:
        """Return all loaded records."""
        return self.records

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        """Find a record using its ID."""
        return next(
            (record for record in self.records if record.get("id") == record_id),
            None,
        )
