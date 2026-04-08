import sys
from airbyte_cdk.entrypoint import launch
from destination_azure_blob import DestinationAzureBlob

if __name__ == "__main__":
    destination = DestinationAzureBlob()
    launch(destination, sys.argv[1:])
