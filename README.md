# destination-azure-blob

A generic Airbyte destination connector that writes records to Azure Blob Storage.

Unlike the standard Airbyte Azure Blob destination, this connector does not impose
any path structure or filename format. The blob path is determined entirely by the
source connector — making this destination reusable across any source without
modification.

---

## How It Works

The destination reads two control fields from each record:

| Field | Required | Description |
|---|---|---|
| `az_blob_path` | Yes | Full blob path relative to the container. e.g. `{client}/raw/activity/{yyyy}/{MM}/{yyyyMMdd}.json` |
| `az_blob_write_mode` | No | `overwrite` (default) or `append` |

Both fields are stripped from the record before writing. The remaining data is
written as JSONL — one record per line.

Records sharing the same `az_blob_path` within a sync are buffered and written
together as a single blob.

---

## Write Modes

### `overwrite`
Deletes the existing blob at `az_blob_path` (if it exists) then writes all buffered
records. Use this for full refresh streams where the file should be replaced on
every sync.

```
Sync 1 → {client}/raw/{stream}/{yyyy}/{MM}/{dd}/data.json  (written)
Sync 2 → {client}/raw/{stream}/{yyyy}/{MM}/{dd}/data.json  (previous deleted, new written)
```

### `append`
Writes to the given path without deleting. When the path includes a date component
that changes each sync, this naturally creates a new file per sync without touching
previous files — effectively appending history as new files.

```
Sync 1 → {client}/raw/activity/{yyyy}/{MM}/{yyyyMMdd}.json  (written)
Sync 2 → {client}/raw/activity/{yyyy}/{MM}/{yyyyMMdd}.json  (new date, previous untouched)
Sync 3 → {client}/raw/activity/{yyyy}/{MM}/{yyyyMMdd}.json  (new date, previous untouched)
```

---

## Authentication

Configure exactly one authentication method in the destination settings.

### Connection String
```json
{
  "container": "mycontainer",
  "credentials": {
    "auth_type": "connection_string",
    "connection_string": "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
  }
}
```

### SAS Token
```json
{
  "container": "mycontainer",
  "credentials": {
    "auth_type": "sas_token",
    "account_name": "youraccount",
    "sas_token": "sv=2025-01-01&ss=b&..."
  }
}
```

### Account Key
```json
{
  "container": "mycontainer",
  "credentials": {
    "auth_type": "account_key",
    "account_name": "youraccount",
    "account_key": "yourbase64key=="
  }
}
```

### Service Principal
```json
{
  "container": "mycontainer",
  "credentials": {
    "auth_type": "service_principal",
    "account_name": "youraccount",
    "tenant_id": "your-tenant-id",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret"
  }
}
```

---

## Source Integration Guide

To use this destination, your source connector must add `az_blob_path` and
`az_blob_write_mode` to every yielded record.

### Minimal example

```python
def read_records(self, sync_mode, ...):
    for record in fetch_data():
        record["az_blob_path"]  = "{client}/raw/{stream}/{yyyy}/{MM}/{dd}/data.json"
        record["az_blob_write_mode"] = "overwrite"
        yield record
```

### Full refresh stream (overwrite)

The file is replaced on every sync. Use a date-based path so each day's
sync produces a separate dated file:

```python
from datetime import datetime, timezone

def read_records(self, sync_mode, ...):
    today = datetime.now(timezone.utc)
    path  = f"{client}/raw/users/{today.strftime('%Y/%m/%d')}/users.json"

    for user in fetch_users():
        user["az_blob_path"]  = path
        user["az_blob_write_mode"] = "overwrite"
        yield user
```

Result:
```
{client}/raw/users/{yyyy}/{MM}/{dd}/users.json  ← all records in one file, replaced each sync
```

### Incremental stream (append by date)

Event or activity streams where each day produces a new file:

```python
def read_records(self, sync_mode, stream_state=None, ...):
    for day in days_since_last_run(stream_state):
        path = f"{client}/raw/events/{day.strftime('%Y/%m/%d/%Y%m%d')}.json"

        for event in fetch_events(day):
            event["az_blob_path"]  = path
            event["az_blob_write_mode"] = "append"
            yield event
```

Result:
```
{client}/raw/events/{yyyy}/{MM}/{yyyyMMdd}.json  ← one new file per day, history retained
```

### Multiple files from one stream

If your stream needs to write to different paths (e.g. one file per entity ID),
set a different `az_blob_path` per record:

```python
def read_records(self, sync_mode, ...):
    for item in fetch_items():
        item_id = item.get("id")
        item["az_blob_path"]  = f"{client}/raw/items/{yyyy}/{MM}/{dd}/{item_id}.json"
        item["az_blob_write_mode"] = "append"
        yield item
```

Result:
```
{client}/raw/items/{yyyy}/{MM}/{dd}/{id_1}.json
{client}/raw/items/{yyyy}/{MM}/{dd}/{id_2}.json
{client}/raw/items/{yyyy}/{MM}/{dd}/{id_3}.json
```

---

## Output Format

Records are written as JSONL — one JSON object per line.

The `az_blob_path` and `az_blob_write_mode` fields are removed before writing.
Only the original source data appears in the blob.

Example output:
```jsonl
{"id": "ws-1", "name": "Finance", "displayName": "Alice", "role": "Admin"}
{"id": "ws-1", "name": "Finance", "displayName": "Bob", "role": "Member"}
{"id": "ws-2", "name": "Sales", "displayName": "Carol", "role": "Admin"}
```