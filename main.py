import sys
from destination_azure_blob import DestinationAzureBlob
 
if __name__ == "__main__":
    DestinationAzureBlob().run(sys.argv[1:])
