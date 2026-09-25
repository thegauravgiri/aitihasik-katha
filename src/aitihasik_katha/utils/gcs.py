import os

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import storage

from ..core.logging import get_logger
from .retry import retry


logger = get_logger(__name__)


@retry(exceptions=(GoogleAPICallError,), max_attempts=3, delay_seconds=5)
def _upload_from_filename(blob: storage.Blob, source_file_path: str) -> None:
    blob.upload_from_filename(source_file_path)


def upload_file_to_gcs(bucket_name: str, source_file_path: str, destination_blob_path: str, return_public: bool = True) -> str:
    """Upload a local file to GCS and return its gs:// URI."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_path)
    _upload_from_filename(blob, source_file_path)
    if return_public:
        return f"https://storage.googleapis.com/{bucket_name}/{destination_blob_path}"
    return f"gs://{bucket_name}/{destination_blob_path}"

def upload_folder_to_gcs(bucket_name: str, source_folder: str, destination_prefix: str = "", return_public: bool = True):
    """Upload a local folder to GCS and return it's gs:// URI"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    for root, _, files in os.walk(source_folder):
        for file in files:
            local_path = os.path.join(root, file)

            # Preserve folder structure
            relative_path = os.path.relpath(local_path, source_folder)
            gcs_path = os.path.join(destination_prefix, relative_path).replace("\\", "/")

            blob = bucket.blob(gcs_path)
            _upload_from_filename(blob, local_path)

            logger.debug("Uploaded %s to gs://%s/%s", local_path, bucket_name, gcs_path)
    if return_public:
        return f"https://storage.googleapis.com/{bucket_name}/{destination_prefix}/"
    return destination_prefix


def delete_file_from_gcs(gcs_path: str) -> bool:
    """Delete an object in GCS from its gs:// URI."""
    if not gcs_path.startswith("gs://"):
        raise ValueError("Invalid GCS path. Must start with gs://")

    bucket_name, blob_path = gcs_path.replace("gs://", "", 1).split("/", 1)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    if blob.exists():
        blob.delete()
        return True
    return False
