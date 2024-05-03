"""Avro tap class."""

from __future__ import annotations

import json
import os
from typing import List

from singer_sdk import Stream, Tap
from singer_sdk import typing as th  # JSON schema typing helpers
from singer_sdk.helpers._classproperty import classproperty
from singer_sdk.helpers.capabilities import TapCapabilities

from tap_avro.client import AvroStream


class TapAvro(Tap):
    """Avro tap class."""

    name = "tap-avro"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "files",
            th.ArrayType(
                th.ObjectType(
                    th.Property("entity", th.StringType, required=True),
                    th.Property("path", th.StringType, required=True),
                    th.Property("keys", th.ArrayType(th.StringType), required=True),
                    # th.Property(
                    #     "encoding", th.StringType, required=False, default="utf-8"
                    # ),
                    # th.Property("delimiter", th.StringType, required=False),
                    # th.Property("doublequote", th.BooleanType, required=False),
                    # th.Property("escapechar", th.StringType, required=False),
                    # th.Property("quotechar", th.StringType, required=False),
                    # th.Property("skipinitialspace", th.BooleanType, required=False),
                    # th.Property("strict", th.BooleanType, required=False),
                )
            ),
            description="An array of .avro file stream settings.",
        ),
        th.Property(
            "avro_files_definition",
            th.StringType,
            description="A path to the avro file holding an array of file settings.",
        ),
        th.Property(
            "add_metadata_columns",
            th.BooleanType,
            required=False,
            default=False,
            description=(
                "When True, add the metadata columns (`_sdc_source_file`, "
                "`_sdc_source_file_mtime`, `_sdc_source_lineno`) to output."
            ),
        ),
    ).to_dict()

    @classproperty
    def capabilities(self) -> list[TapCapabilities]:
        """Get tap capabilites."""
        return [
            TapCapabilities.CATALOG,
            TapCapabilities.DISCOVER,
        ]

    def get_file_configs(self) -> list[dict]:
        """Return a list of file configs.

        Either directly from the config.json or in an external file
        defined by avro_files_definition.
        """
        avro_files = self.config.get("files")
        avro_files_definition = self.config.get("avro_files_definition")
        if avro_files_definition:
            if os.path.isfile(avro_files_definition):
                with open(avro_files_definition) as f:
                    avro_files = json.load(f)
            else:
                self.logger.error(f"tap-avro: '{avro_files_definition}' file not found")
                exit(1)
        if not avro_files:
            self.logger.error("No avro file definitions found.")
            exit(1)
        return avro_files

    def discover_streams(self) -> list[Stream]:
        """Return a list of discovered streams."""
        return [
            AvroStream(
                tap=self,
                name=file_config.get("entity"),
                file_config=file_config,
            )
            for file_config in self.get_file_configs()
        ]
