"""Custom client handling, including CSVStream base class."""

from __future__ import annotations

import fastavro
import os
import sys

from tap_avro.util import PROCESSED_FILES_LOG_PATH, log_processed_file_path, is_file_processed

from datetime import datetime, timezone
from typing import Iterable, List

from singer_sdk import typing as th
from singer_sdk.streams import Stream

SDC_SOURCE_FILE_COLUMN = "_sdc_source_file"
SDC_SOURCE_LINENO_COLUMN = "_sdc_source_lineno"
SDC_SOURCE_FILE_MTIME_COLUMN = "_sdc_source_file_mtime"


class AvroStream(Stream):
    """Stream class for Avro streams."""

    file_paths: list[str] = []  # noqa: RUF012
    header: list[str] = []  # noqa: RUF012

    def __init__(self, *args, **kwargs):
        """Init stream."""
        # cache file_config so we dont need to go iterating the config list again later
        self.file_config = kwargs.pop("file_config")
        super().__init__(*args, **kwargs)

    def get_records(self, context: dict | None) -> Iterable[dict]:
        """Return a generator of row-type dictionary objects.

        The optional `context` argument is used to identify a specific slice of the
        stream if partitioning is required for the stream. Most implementations do not
        require partitioning and should ignore the `context` argument.
        """
        for file_path in self.get_file_paths():            
            # Skip files that are already processed
            # Skip processed files
            if is_file_processed(file_path):
                continue

            file_last_modified = datetime.fromtimestamp(
                os.path.getmtime(file_path), timezone.utc
            )

            file_lineno = -1

            for row in self.get_rows(file_path):
                    file_lineno += 1
                    if not file_lineno:
                        continue
                    if self.config.get("add_metadata_columns", False):
                        row = [file_path, file_last_modified, file_lineno, *row]
                    yield dict(zip(self.header, row))
                    
            # Mark filepath as processed
            log_processed_file_path(file_path)


    

    def _get_recursive_file_paths(self, file_path: str) -> list:
        file_paths = []

        for dirpath, _, filenames in os.walk(file_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if self.is_valid_filename(file_path):
                    file_paths.append(file_path)

        return file_paths

    def get_file_paths(self) -> list:
        """Return a list of file paths to read.

        This tap accepts file names and directories so it will detect
        directories and iterate files inside.
        """
        # Cache file paths so we dont have to iterate multiple times
        if self.file_paths:
            return self.file_paths

        file_path = self.file_config["path"]
        if not os.path.exists(file_path):
            raise Exception(f"File path does not exist {file_path}")

        file_paths = []
        if os.path.isdir(file_path):
            clean_file_path = os.path.normpath(file_path) + os.sep
            file_paths = self._get_recursive_file_paths(clean_file_path)
        elif self.is_valid_filename(file_path):
            file_paths.append(file_path)

        if not file_paths:
            raise RuntimeError(
                f"Stream '{self.name}' has no acceptable files. \
                    See warning for more detail."
            )
        self.file_paths = file_paths

        return file_paths

    def is_valid_filename(self, file_path: str) -> bool:
        """Return a boolean of whether the file includes Avro extension."""
        is_valid = True
        try:
            with open(file_path, 'rb') as f:
                # Try to create an Avro reader, which will check the file's header
                fastavro.reader(f)
                #self.logger.warning(f"Including avro file '{file_path}'")
            return is_valid
        except Exception as e:
            is_valid = False
            self.logger.warning(f"Skipping non-avro or broken avro file '{file_path}'")
            return is_valid

    def get_rows(self, file_path: str) -> Iterable[list]:
        """Return a generator of the rows in a particular avro file."""
        with open(file_path, 'rb') as f:
            yield from fastavro.reader(f)



    
    @property
    def schema(self) -> dict:
        """Return dictionary of record schema.

        Dynamically detect the json schema for the stream.
        This is evaluated prior to any records being retrieved.
        """
        properties: list[th.Property] = []
        self.primary_keys = self.file_config.get("keys", [])

        header = []
        for file_path in self.get_file_paths():
            with open(file_path, 'rb') as f:
                avro_reader = fastavro.reader(f)
                schema = avro_reader.writer_schema
                for i in schema['fields']:
                    header.append(i['name'])
            break
        

        properties.extend(th.Property(column, th.StringType()) for column in header)
        # If enabled, add file's metadata to output
        if self.config.get("add_metadata_columns", False):
            header = [
                SDC_SOURCE_FILE_COLUMN,
                SDC_SOURCE_FILE_MTIME_COLUMN,
                SDC_SOURCE_LINENO_COLUMN,
                *header,
            ]

            properties.extend(
                (
                    th.Property(SDC_SOURCE_FILE_COLUMN, th.StringType),
                    th.Property(SDC_SOURCE_FILE_MTIME_COLUMN, th.DateTimeType),
                    th.Property(SDC_SOURCE_LINENO_COLUMN, th.IntegerType),
                )
            )
        # Cache header for future use
        self.header = header

        return th.PropertiesList(*properties).to_dict()

