"""
destination.py — Generic Azure Blob Storage destination.

Each record must contain:
  _blob_path:   full blob path to write to
                e.g. rebound/raw/activity/2026/04/08/20260408.json
  _write_mode:  "overwrite" or "append"
                overwrite — delete existing blob then write
                append    — write new file at path (path is unique per day
                            so this creates a new file without touching old ones)

Both fields are stripped from the record before writing.
Records are buffered per blob path and written at stream completion.
"""

import json
import logging
from collections import defaultdict
from typing import Any, Iterable, Mapping

from airbyte_cdk.destinations import Destination
from airbyte_cdk.models import (
    AirbyteConnectionStatus,
    AirbyteMessage,
    ConfiguredAirbyteCatalog,
    ConnectorSpecification,
    DestinationSyncMode,
    Status,
    Type,
)
from azure.core.exceptions import ResourceNotFoundError

from .storage import get_blob_service_client

BLOB_PATH_FIELD  = "_blob_path"
WRITE_MODE_FIELD = "_write_mode"
DEFAULT_WRITE_MODE = "overwrite"


class DestinationAzureBlob(Destination):

    SUPPORTED_DESTINATION_SYNC_MODES = [
        DestinationSyncMode.overwrite,
        DestinationSyncMode.append,
    ]


    def check(self, logger, config: Mapping[str, Any]) -> AirbyteConnectionStatus:
        """
        Verify connectivity by creating and deleting a test blob.
        """
        try:
            client    = get_blob_service_client(config["credentials"])
            container = config["container"]

            # Create container if it does not exist
            try:
                client.create_container(container)
            except Exception:
                pass  # Already exists

            # Write and delete a test blob
            test_path   = "_airbyte_connection_test/test.json"
            blob_client = client.get_blob_client(container=container, blob=test_path)
            blob_client.upload_blob(b'{"test": true}', overwrite=True)
            blob_client.delete_blob()

            return AirbyteConnectionStatus(status=Status.SUCCEEDED)

        except Exception as e:
            return AirbyteConnectionStatus(
                status=Status.FAILED,
                message=f"Connection check failed: {type(e).__name__}: {str(e)}"
            )

    def write(
        self,
        config: Mapping[str, Any],
        configured_catalog: ConfiguredAirbyteCatalog,
        input_messages: Iterable[AirbyteMessage],
    ) -> Iterable[AirbyteMessage]:
        """
        Buffer records per blob path then write at stream completion.

        Records are grouped by _blob_path. When a stream status COMPLETE
        message arrives, all buffered records for that stream are flushed
        to blob storage.
        """
        client    = get_blob_service_client(config["credentials"])
        container = config["container"]

        # Create container if not exists
        try:
            client.create_container(container)
        except Exception:
            pass

        # Buffer: {stream_name: {blob_path: {"records": [...], "write_mode": str}}}
        buffer: dict = defaultdict(lambda: defaultdict(lambda: {
            "records":    [],
            "write_mode": DEFAULT_WRITE_MODE,
        }))

        for message in input_messages:

            if message.type == Type.RECORD:
                record     = dict(message.record.data)
                stream     = message.record.stream
                namespace = message.record.namespace or ""
                stream_key = f"{namespace}.{stream}" if namespace else stream
                blob_path  = record.pop(BLOB_PATH_FIELD, None)
                write_mode = record.pop(WRITE_MODE_FIELD, DEFAULT_WRITE_MODE)

                if not blob_path:
                    logging.warning(
                        "Record from stream '%s' missing '%s' field — skipping.",
                        stream, BLOB_PATH_FIELD
                    )
                    continue

                buffer[stream_key][blob_path]["records"].append(record)
                buffer[stream_key][blob_path]["write_mode"] = write_mode

            elif message.type == Type.STATE:
                # Flush all buffered streams before emitting state
                # This ensures data is written before state is checkpointed
                for stream_name, paths in list(buffer.items()):
                    self._flush_stream(client, container, stream_name, paths)
                buffer.clear()
                yield message

        # Final flush for any remaining buffered records
        for stream_name, paths in buffer.items():
            self._flush_stream(client, container, stream_name, paths)

    def _flush_stream(
        self,
        client,
        container: str,
        stream_name: str,
        paths: dict,
    ) -> None:
        """
        Write all buffered records for a stream to blob storage.
        One blob per unique _blob_path.
        """
        for blob_path, entry in paths.items():
            records    = entry["records"]
            write_mode = entry["write_mode"]

            if not records:
                continue

            content     = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
            blob_client = client.get_blob_client(container=container, blob=blob_path)

            if write_mode == "overwrite":
                try:
                    blob_client.delete_blob()
                except ResourceNotFoundError:
                    pass  # Does not exist yet — fine

            blob_client.upload_blob(
                content.encode("utf-8"),
                overwrite=(write_mode == "overwrite")
            )

            logging.info(
                "Wrote %d records to %s/%s [%s].",
                len(records), container, blob_path, write_mode
            )