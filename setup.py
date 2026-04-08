from setuptools import find_packages, setup

MAIN_REQUIREMENTS = [
    "airbyte-cdk>=0.80.0",
    "azure-storage-blob>=12.0.0",
    "azure-identity>=1.15.0"
]

setup(
    name="destination_azure_blob",
    version="0.1.0",
    description="Airbyte Destination: Enhanced Azure Storage Blob Connector",
    author="assured",
    author_email="admin@assuredinsights.com",
    packages=find_packages(),
    install_requires=MAIN_REQUIREMENTS,
    package_data={
        "destination_azure_blob": ["*.json"]
    },
    entry_points={
        'console_scripts': [
            'destination-azure-blob=destination_azure_blob.main:main',
        ],
    },
    python_requires=">=3.9",
    include_package_data=True
)