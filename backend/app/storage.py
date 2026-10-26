import os
from pathlib import Path


class StorageError(Exception):
    pass


class ObjectStorage:
    def __init__(self, config):
        self.config = config
        self.backend = config["STORAGE_BACKEND"]
        if self.backend == "s3":
            if not config.get("S3_BUCKET"):
                raise StorageError("S3_BUCKET is required when STORAGE_BACKEND=s3.")
            import boto3

            self.client = boto3.client("s3", region_name=config["AWS_REGION"])
        elif self.backend == "local":
            self.root = Path(config["STORAGE_DIR"]).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
        else:
            raise StorageError("STORAGE_BACKEND must be either 'local' or 's3'.")

    def put(self, key, data):
        try:
            if self.backend == "s3":
                self.client.put_object(
                    Bucket=self.config["S3_BUCKET"],
                    Key=key,
                    Body=data,
                    ServerSideEncryption="AES256",
                )
            else:
                path = self._local_path(key)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        except Exception as error:
            raise StorageError("Artwork could not be stored.") from error

    def get(self, key):
        try:
            if self.backend == "s3":
                return self.client.get_object(
                    Bucket=self.config["S3_BUCKET"], Key=key
                )["Body"].read()
            return self._local_path(key).read_bytes()
        except Exception as error:
            raise StorageError("Artwork could not be retrieved.") from error

    def delete(self, key):
        try:
            if self.backend == "s3":
                self.client.delete_object(Bucket=self.config["S3_BUCKET"], Key=key)
            else:
                self._local_path(key).unlink(missing_ok=True)
        except Exception as error:
            raise StorageError("Artwork could not be deleted.") from error

    def _local_path(self, key):
        path = (self.root / key).resolve()
        if os.path.commonpath([str(self.root), str(path)]) != str(self.root):
            raise StorageError("Invalid storage object key.")
        return path
