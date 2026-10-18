"""Explicit, bounded Kaggle downloads for local verification; never logs tokens."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from datetime import datetime, timezone

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT/'tests'/'data'/'kaggle'
DATASETS = [
    'uciml/iris',
    'uciml/red-wine-quality-cortez-et-al-2009',
    'yasserh/titanic-dataset',
    'rakannimer/air-passengers',
    'shrutimechlearn/churn-modelling',
    'mirichoi0218/insurance',
    'fedesoriano/air-quality-data-set',
    'uciml/sms-spam-collection-dataset',
    'vivek468/superstore-dataset-final',
    'abcsds/pokemon',
]


def main():
    token = dotenv_values(ROOT/'.env').get('KAGGLE_API_TOKEN')
    if not token:
        raise RuntimeError('Set KAGGLE_API_TOKEN in .env before fetching test datasets.')
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = {'downloaded_at':datetime.now(timezone.utc).isoformat(), 'datasets':[]}
    previous_path = DESTINATION/'manifest.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
    cached = {entry['reference']:entry for entry in previous.get('datasets', [])}
    with requests.Session() as session:
        session.headers['Authorization'] = 'Bearer '+token
        for reference in DATASETS:
            prior = cached.get(reference, {})
            if prior.get('files') and not prior.get('error') and all(
                (ROOT/item['path']).is_file() and hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest() == item['sha256']
                for item in prior['files']):
                manifest['datasets'].append(prior)
                print(reference, 'verified cached source', flush=True)
                continue
            entry = dict(reference=reference, source='https://www.kaggle.com/datasets/'+reference, files=[])
            response = session.get('https://www.kaggle.com/api/v1/datasets/download/'+reference,
                stream=True, timeout=(15,60))
            if not response.ok:
                entry['error'] = f'Kaggle returned HTTP {response.status_code}'
                manifest['datasets'].append(entry)
                print(reference, entry['error'], flush=True)
                continue
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 20*1024*1024:
                    raise ValueError('Download exceeds the 20 MiB verification archive limit.')
            if not zipfile.is_zipfile(io.BytesIO(content)):
                entry['error'] = 'Kaggle response was not a dataset ZIP archive.'
            else:
                directory = DESTINATION/reference.replace('/','__')
                directory.mkdir(exist_ok=True)
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    if sum(item.file_size for item in archive.infolist()) > 50*1024*1024:
                        raise ValueError('Expanded dataset exceeds the 50 MiB verification limit.')
                    for item in archive.infolist():
                        filename = Path(item.filename).name
                        if item.is_dir() or Path(filename).suffix.lower() not in {'.csv','.xls','.xlsx','.txt'}:
                            continue
                        target = directory/filename
                        # Write individual basenames rather than extracting archive paths.
                        data = archive.read(item)
                        target.write_bytes(data)
                        entry['files'].append(dict(path=target.relative_to(ROOT).as_posix(),
                            bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            manifest['datasets'].append(entry)
            print(reference, f"{len(entry['files'])} tabular files", flush=True)
            (DESTINATION/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (DESTINATION/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return 1 if any(item.get('error') for item in manifest['datasets']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
