"""Versioned, hash-verified local Hipparcos snapshots; no implicit downloads.

The portable scene codec preserves all accepted catalog values, nulls, metadata,
and row-rejection report. A cache is an application snapshot, not the original
VOTable. No pickle or executable deserialization is used. Failed writes/loads
never replace a current scene or delete a previous snapshot.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
from .deployment import data_root,atomic_json
from .session import make_document,decode_document,canonical_bytes
from .state import ViewState
from .presentation import Presentation

SCHEMA='relativistic-spaceship-viewer.hipparcos-cache/1'
MAX_COMPRESSED=64*1024*1024
MAX_DECODED=128*1024*1024

def cache_root(root=None):
    return Path(root) if root is not None else data_root()/'catalogs'/'hipparcos'

def cached_info(root=None):
    folder=cache_root(root)
    pointer=folder/'latest.json'
    if not pointer.exists():return None
    if pointer.stat().st_size>16384:raise ValueError('Oversized Hipparcos cache pointer.')
    info=json.loads(pointer.read_text(encoding='utf-8'))
    if info.get('schema')!=SCHEMA or not re.fullmatch(r'hipparcos-[a-f0-9]{64}\.json\.gz',str(info.get('file',''))):
        raise ValueError('Invalid Hipparcos cache pointer.')
    if info.get('sha256')!=info['file'][10:74]:raise ValueError('Hipparcos cache identity mismatch.')
    if any(type(info.get(key)) is not int or info[key]<0 for key in ('accepted_rows','compressed_bytes')):
        raise ValueError('Invalid Hipparcos snapshot size metadata.')
    return info

def load_cached(*,root=None,minimum_limit=None):
    folder=cache_root(root);info=cached_info(folder)
    if info is None:raise FileNotFoundError('No local Hipparcos snapshot is available.')
    path=folder/info['file']
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_COMPRESSED:
        raise ValueError('Invalid Hipparcos cache file.')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=info['sha256']:raise ValueError('Hipparcos snapshot checksum mismatch.')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:decoded=stream.read(MAX_DECODED+1)
    if len(decoded)>MAX_DECODED:raise ValueError('Decoded Hipparcos snapshot is too large.')
    body=json.loads(decoded)
    if body.get('schema')!=SCHEMA:raise ValueError('Unsupported Hipparcos snapshot schema.')
    limit=body['server_vmag_limit']
    if minimum_limit is not None and limit is not None and minimum_limit>limit:
        raise ValueError(f'This snapshot covers V < {limit:g}; download the complete library for a wider cut.')
    catalog,_,_,_=decode_document(body['scene'])
    if catalog.n!=info['accepted_rows']:raise ValueError('Hipparcos snapshot row count mismatch.')
    return catalog,info

def save_cached(catalog,*,root=None,server_vmag_limit=None):
    folder=cache_root(root);folder.mkdir(parents=True,exist_ok=True)
    body={'schema':SCHEMA,'server_vmag_limit':server_vmag_limit,
          'scene':make_document(catalog,ViewState(),Presentation(),'Hipparcos local library')}
    raw=gzip.compress(canonical_bytes(body),compresslevel=6,mtime=0)
    digest=hashlib.sha256(raw).hexdigest();name=f'hipparcos-{digest}.json.gz'
    path=folder/name
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('Existing snapshot identity collision or corruption.')
    else:
        with path.open('xb') as stream:stream.write(raw)
    info={'schema':SCHEMA,'file':name,'sha256':digest,'accepted_rows':catalog.n,
          'compressed_bytes':len(raw),'server_vmag_limit':server_vmag_limit,
          'retrieved_utc':catalog.metadata.retrieved_utc,'source':catalog.metadata.source,
          'coordinate_epoch':catalog.metadata.coordinate_epoch,
          'storage':'gzip portable catalog snapshot; not the original VOTable'}
    # Verify all data before moving the pointer; preserve previous files.
    previous=folder/'latest.json'
    # Validate this body through the same safe scene codec before activation.
    restored,_,_,_=decode_document(body['scene'])
    if restored.n!=catalog.n:raise ValueError('Snapshot verification failed.')
    atomic_json(previous,info)
    return info

def startup_choice():
    path=data_root()/'catalog-settings.json'
    try:
        if path.stat().st_size>16384:return 'ask'
        value=json.loads(path.read_text(encoding='utf-8')).get('startup','ask')
        return value if value in ('ask','demo','hipparcos') else 'ask'
    except (OSError,ValueError,TypeError):return 'ask'

def set_startup_choice(choice):
    if choice not in ('ask','demo','hipparcos'):raise ValueError('Invalid catalog startup choice.')
    root=data_root();root.mkdir(parents=True,exist_ok=True)
    atomic_json(root/'catalog-settings.json',{'schema':1,'startup':choice})
