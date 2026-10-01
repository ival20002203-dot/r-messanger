from urllib.parse import urlparse
import boto3
from botocore.config import Config
from django.conf import settings
from storages.backends.s3 import S3Storage

class MinioStorage(S3Storage):
    def url(self,name,parameters=None,expire=None,http_method=None):
        public=getattr(settings,"MINIO_PUBLIC_ENDPOINT","")
        if not public:
            return super().url(name,parameters=parameters,expire=expire,http_method=http_method)
        client=boto3.client(
            "s3",endpoint_url=public,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(signature_version="s3v4",s3={"addressing_style":"path"}),
        )
        params={"Bucket":settings.AWS_STORAGE_BUCKET_NAME,"Key":name}
        if parameters:params.update(parameters)
        return client.generate_presigned_url("get_object",Params=params,ExpiresIn=expire or settings.AWS_QUERYSTRING_EXPIRE,HttpMethod=http_method or "GET")
