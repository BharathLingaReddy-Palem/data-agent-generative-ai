import asyncio
import io
import zipfile
import pandas as pd
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile
from backend.services import upload_limits as limits


@pytest.mark.parametrize('setting,value,content', [
    ('MAX_UPLOAD_BYTES', 8, b'x,y\n1,22222222222\n'),
    ('MAX_DATASET_ROWS', 2, b'x,y\n1,2\n3,4\n5,6\n'),
    ('MAX_DATASET_COLUMNS', 1, b'x,y\n1,2\n'),
    ('MAX_DATASET_CELLS', 3, b'x,y\n1,2\n3,4\n'),
    ('MAX_DATASET_MEMORY_BYTES', 8, b'x,y\n1,2\n'),
])
def test_csv_resource_limits_fail_explicitly(monkeypatch, setting, value, content):
    monkeypatch.setattr(limits, setting, value)
    with pytest.raises(HTTPException) as exc: limits.parse_upload(content, 'data.csv')
    assert exc.value.status_code == 413


def test_read_limit_and_excel_expansion_limit(monkeypatch):
    monkeypatch.setattr(limits, 'MAX_UPLOAD_BYTES', 12)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(limits.read_upload(UploadFile(io.BytesIO(b'x'*13))))
    assert exc.value.status_code == 413
    monkeypatch.setattr(limits, 'MAX_UPLOAD_BYTES', 10000)
    monkeypatch.setattr(limits, 'MAX_DATASET_MEMORY_BYTES', 100)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive: archive.writestr('large.xml', 'x'*1000)
    with pytest.raises(HTTPException) as exc: limits.parse_upload(buffer.getvalue(), 'data.xlsx')
    assert exc.value.status_code == 413


@pytest.mark.parametrize('declared', [True, False])
def test_multipart_body_limit_including_chunked_requests(client, accounts, declared):
    from fastapi import FastAPI, File, UploadFile
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.add_middleware(limits.UploadBodyLimitMiddleware, max_bytes=200)
    @app.post('/api/upload')
    async def upload(file:UploadFile=File(...)): return {'size':len(await file.read())}
    body = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="data.csv"\r\n\r\n' + b'x'*400 + b'\r\n--boundary--\r\n'
    headers = {'Content-Type':'multipart/form-data; boundary=boundary'}
    content = body if declared else iter([body[:100], body[100:]])
    with TestClient(app) as test:
        response = test.post('/api/upload', headers=headers, content=content)
    assert response.status_code == 413, response.text
