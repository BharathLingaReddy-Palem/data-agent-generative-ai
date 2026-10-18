import os
import io
import pickle
import logging
from typing import Optional, Union
try:
    import boto3
    from botocore.config import Config
except ImportError:
    boto3 = None
    Config = None
import pandas as pd

from backend.config import (
    ENABLE_CLOUD_SYNC,
    R2_ENDPOINT_URL,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_PUBLIC_URL,
    UPLOAD_DIR,
    ARTIFACTS_DIR,
    REPORTS_DIR,
)

logger = logging.getLogger(__name__)

class R2StorageService:
    def __init__(self):
        self.bucket_name = R2_BUCKET_NAME
        self.public_url_base = R2_PUBLIC_URL.rstrip("/")
        self.s3_client = None

        if ENABLE_CLOUD_SYNC and boto3 is not None and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY:
            try:
                self.s3_client = boto3.client(
                    service_name="s3",
                    endpoint_url=R2_ENDPOINT_URL,
                    aws_access_key_id=R2_ACCESS_KEY_ID,
                    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                    region_name="auto",
                    config=Config(s3={"addressing_style": "path"}) if Config else None,
                )
                logger.info(f"Connected to Cloudflare R2 bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client for Cloudflare R2: {e}")
                self.s3_client = None
        else:
            logger.info("Cloudflare R2 boto3 client not loaded or credentials missing. Using local storage fallback.")

    def get_public_url(self, object_name: str) -> str:
        """Returns the public URL for an R2 object."""
        return f"{self.public_url_base}/{object_name}"

    def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Uploads raw bytes to Cloudflare R2. Falls back to local storage on failure.
        """
        if self.s3_client:
            try:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_name,
                    Body=data,
                    ContentType=content_type,
                )
                return self.get_public_url(object_name)
            except Exception as e:
                logger.error(f"R2 upload failed for {object_name}: {e}. Storing locally.")

        # Local storage fallback
        local_path = ARTIFACTS_DIR / object_name.replace("/", "_")
        with open(local_path, "wb") as f:
            f.write(data)
        return str(local_path)

    def upload_file(
        self,
        file_path: Union[str, os.PathLike],
        object_name: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """Uploads a local file to Cloudflare R2."""
        with open(file_path, "rb") as f:
            data = f.read()
        return self.upload_bytes(data, object_name, content_type)

    def upload_dataframe_csv(self, df: pd.DataFrame, object_name: str) -> str:
        """Uploads a Pandas DataFrame as CSV to Cloudflare R2."""
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        return self.upload_bytes(
            csv_buffer.getvalue().encode("utf-8"),
            object_name,
            content_type="text/csv"
        )

    def upload_model_pkl(self, model: object, object_name: str) -> str:
        """Serializes and uploads a trained ML model to Cloudflare R2."""
        pkl_bytes = pickle.dumps(model)
        return self.upload_bytes(
            pkl_bytes,
            object_name,
            content_type="application/octet-stream"
        )

    def upload_pdf_report(self, pdf_bytes_or_path: Union[bytes, str], object_name: str) -> str:
        """Uploads a generated PDF report to Cloudflare R2."""
        if isinstance(pdf_bytes_or_path, (str, os.PathLike)):
            return self.upload_file(pdf_bytes_or_path, object_name, content_type="application/pdf")
        return self.upload_bytes(pdf_bytes_or_path, object_name, content_type="application/pdf")

    def download_bytes(self, object_name: str) -> Optional[bytes]:
        """Downloads an object from Cloudflare R2 as bytes."""
        if self.s3_client:
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_name)
                return response["Body"].read()
            except Exception as e:
                logger.error(f"Failed to download {object_name} from R2: {e}")

        # Try local fallback
        local_path = ARTIFACTS_DIR / object_name.replace("/", "_")
        if local_path.exists():
            with open(local_path, "rb") as f:
                return f.read()
        return None

# Singleton instance
r2_service = R2StorageService()
