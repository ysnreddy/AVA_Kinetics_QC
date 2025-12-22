import logging
from pathlib import Path
import boto3
from tqdm import tqdm

logger = logging.getLogger(__name__)


class S3Uploader:
    def __init__(self, bucket_name: str, region_name: str = "us-east-1"):
        self.bucket = bucket_name
        self.s3 = boto3.client("s3", region_name=region_name)

    def upload_file(self, local_path: str, s3_key: str):
        logger.info(f"📤 Uploading → s3://{self.bucket}/{s3_key}")
        self.s3.upload_file(local_path, self.bucket, s3_key)

    def upload_directory(self, local_dir: str, s3_prefix: str):
        local_dir = Path(local_dir)
        files = [f for f in local_dir.rglob("*") if f.is_file()]

        for file in tqdm(files, desc=f"Uploading {local_dir.name}"):
            rel = file.relative_to(local_dir)
            key = f"{s3_prefix}/{rel}".replace("\\", "/")
            self.upload_file(str(file), key)

    def generate_presigned_url(self, s3_key: str, expiry_seconds: int = 7 * 24 * 3600):
        """
        Default expiry: 7 days
        """
        return self.s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": self.bucket,
                "Key": s3_key,
            },
            ExpiresIn=expiry_seconds,
        )
