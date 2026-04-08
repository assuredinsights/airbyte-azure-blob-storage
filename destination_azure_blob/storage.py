"""
storage.py — Azure Blob Storage client factory.

Supports four authentication methods:
  - connection_string
  - sas_token
  - account_key
  - service_principal
"""

from azure.storage.blob import BlobServiceClient
from azure.identity import ClientSecretCredential


def get_blob_service_client(credentials: dict) -> BlobServiceClient:
    auth_type = credentials.get("auth_type")

    if auth_type == "connection_string":
        return BlobServiceClient.from_connection_string(
            credentials["connection_string"]
        )

    elif auth_type == "sas_token":
        account_name = credentials["account_name"]
        sas_token    = credentials["sas_token"]
        account_url  = f"https://{account_name}.blob.core.windows.net"
        return BlobServiceClient(
            account_url=account_url,
            credential=sas_token
        )

    elif auth_type == "account_key":
        account_name = credentials["account_name"]
        account_key  = credentials["account_key"]
        account_url  = f"https://{account_name}.blob.core.windows.net"
        return BlobServiceClient(
            account_url=account_url,
            credential=account_key
        )

    elif auth_type == "service_principal":
        account_name  = credentials["account_name"]
        credential    = ClientSecretCredential(
            tenant_id=credentials["tenant_id"],
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"]
        )
        account_url = f"https://{account_name}.blob.core.windows.net"
        return BlobServiceClient(
            account_url=account_url,
            credential=credential
        )

    else:
        raise ValueError(f"Unsupported auth_type: {auth_type!r}")
