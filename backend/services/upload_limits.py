"""Bound upload reads and decompression before a dataset enters the session cache."""
import io
import csv
import codecs
import re
import zipfile
import pandas as pd
from fastapi import HTTPException
from backend.config import (MAX_UPLOAD_BYTES, MAX_DATASET_ROWS, MAX_DATASET_COLUMNS,
    MAX_DATASET_CELLS, MAX_DATASET_MEMORY_BYTES)
from backend.services.cleaner import strip_column_names


class UploadBodyLimitMiddleware:
    def __init__(self, app, max_bytes=MAX_UPLOAD_BYTES + 65536):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        path=scope.get('path','')
        if scope['type'] != 'http' or scope.get('method') != 'POST' or (path not in {'/api/upload', '/api/profile'} and not (path.startswith('/api/workspace/') and path.endswith('/batch'))):
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            declared = self.max_bytes + 1
        if declared > self.max_bytes:
            from starlette.responses import JSONResponse
            return await JSONResponse({'detail': 'Upload request exceeds the body limit.'}, status_code=413)(scope, receive, send)
        consumed = 0
        async def limited_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get('body', b''))
            if consumed > self.max_bytes:
                raise HTTPException(413, 'Upload request exceeds the body limit.')
            return message
        return await self.app(scope, limited_receive, send)


async def read_upload(file):
    chunks, size = [], 0
    while True:
        chunk = await file.read(min(1024 * 1024, MAX_UPLOAD_BYTES + 1 - size))
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"Upload exceeds the {MAX_UPLOAD_BYTES}-byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def validate_dataset_size(df):
    if df.empty:
        raise HTTPException(400, "Dataset must contain at least one data row.")
    if len(df) > MAX_DATASET_ROWS or len(df.columns) > MAX_DATASET_COLUMNS or df.size > MAX_DATASET_CELLS:
        raise HTTPException(413, f"Dataset exceeds limits: {MAX_DATASET_ROWS} rows, {MAX_DATASET_COLUMNS} columns, {MAX_DATASET_CELLS} cells.")
    if int(df.memory_usage(index=True, deep=True).sum()) > MAX_DATASET_MEMORY_BYTES:
        raise HTTPException(413, "Decoded dataset exceeds the memory limit.")
    return df


def _csv_source(contents):
    """Decode common exports, then validate logical records before pandas inference."""
    if contents.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        source = contents.decode('utf-32')
    elif contents.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        source = contents.decode('utf-16')
    else:
        try:
            source = contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            source = contents.decode('cp1252')
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', source):
        raise ValueError('CSV contains binary/control characters.')
    # Infer from the header first: a malformed data row must not change the
    # delimiter and thereby hide the mismatch in a single text column.
    header_line = next((line for line in source.splitlines() if line.strip()), '')
    try:
        delimiter = csv.Sniffer().sniff(header_line, delimiters=',;\t|').delimiter
    except csv.Error:
        delimiter = ','
    reader = csv.reader(io.StringIO(source, newline=''), delimiter=delimiter, strict=True)
    header = next((row for row in reader if row and any(v.strip() for v in row)), [])
    columns = len(header)
    if columns > MAX_DATASET_COLUMNS:
        raise HTTPException(413, f'Dataset exceeds the {MAX_DATASET_COLUMNS}-column limit.')
    row_limit = min(MAX_DATASET_ROWS, MAX_DATASET_CELLS // max(columns, 1))
    count = comma_numbers = dot_numbers = 0
    for row in reader:
        if not row or (len(row) == 1 and not row[0].strip()):
            continue
        if len(row) != columns:
            raise ValueError(f'CSV record ending on line {reader.line_num} has {len(row)} fields; expected {columns}. Use empty fields for missing values.')
        count += 1
        if count > row_limit:
            raise HTTPException(413, 'Dataset exceeds the row or cell limit.')
        if count <= 100 and delimiter != ',':
            for value in row:
                comma_numbers += bool(re.fullmatch(r'[+-]?\d+,\d+(?:[eE][+-]?\d+)?', value.strip()))
                dot_numbers += bool(re.fullmatch(r'[+-]?\d+\.\d+(?:[eE][+-]?\d+)?', value.strip()))
    decimal = ',' if comma_numbers > dot_numbers else '.'
    return source, delimiter, decimal, columns


def parse_upload(contents, filename, sheet_name=0):
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f'Upload exceeds the {MAX_UPLOAD_BYTES}-byte limit.')
    suffix = (filename or "").lower().rsplit(".", 1)[-1]
    if suffix not in {"csv", "xlsx", "xls"}:
        raise HTTPException(400, "Supported upload formats: CSV, XLSX and XLS.")
    try:
        if suffix == "xlsx":
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                if sum(item.file_size for item in archive.infolist()) > MAX_DATASET_MEMORY_BYTES:
                    raise HTTPException(413, "Expanded Excel workbook exceeds the memory limit.")
        if suffix in {"xlsx", "xls"}:
            columns = len(pd.read_excel(io.BytesIO(contents), nrows=0, sheet_name=sheet_name).columns)
        else:
            source, delimiter, decimal, columns = _csv_source(contents)
        if columns > MAX_DATASET_COLUMNS:
            raise HTTPException(413, f'Dataset exceeds the {MAX_DATASET_COLUMNS}-column limit.')
        rows = min(MAX_DATASET_ROWS, MAX_DATASET_CELLS // max(columns, 1)) + 1
        df = (pd.read_excel(io.BytesIO(contents), nrows=rows, sheet_name=sheet_name) if suffix in {'xlsx', 'xls'}
            else pd.read_csv(io.StringIO(source), sep=delimiter, decimal=decimal, nrows=rows))
        return validate_dataset_size(strip_column_names(df))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Failed to parse data file: {exc}") from exc
