"""Offline verified local backup/restore. Archive is plaintext and sensitive.

Run after stopping the worker/API. Does not include credentials/session keys.
Restores only into an EMPTY directory and validates content hashes first.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import json
import os
import shutil
import sqlite3


def backup(root:Path,output:Path):
    if not (root/'textilehr.sqlite3').is_file():raise SystemExit('No local SQLite database to back up')
    if output.exists():raise SystemExit('Backup already exists; refuse overwrite')
    with TemporaryDirectory() as temp:
        tmp=Path(temp)/'textilehr.sqlite3'
        origin=sqlite3.connect(root/'textilehr.sqlite3');dest=sqlite3.connect(tmp)
        try:origin.backup(dest)
        finally:origin.close();dest.close()
        sources=[('textilehr.sqlite3',tmp)]
        for folder in ('uploads','exports'):
            for source in (root/folder).glob('*'):
                if (source.is_file() and not source.is_symlink()
                        and source.name.replace('.','').replace('-','').isalnum()):
                    sources.append((folder+'/'+source.name,source))
        manifest={'format':'textilehr-local-backup-v1','created':datetime.now(timezone.utc).isoformat(),
                  'sensitive_plaintext':True,'files':{name:sha256(file.read_bytes()).hexdigest() for name,file in sources}}
        with ZipFile(output,'x',compression=ZIP_DEFLATED,compresslevel=7) as zipf:
            for name,path in sources:zipf.write(path,name)
            zipf.writestr('manifest.json',json.dumps(manifest,indent=2))
    print('Created private PLAINTEXT backup:',output)
    print('Protect the ZIP and remove old backups in line with your retention policy.')


def restore(archive:Path,destination:Path):
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit('Restore destination must be empty; stop running services first')
    with ZipFile(archive) as zipf:
        if zipf.testzip() is not None:raise SystemExit('ZIP content integrity failed')
        try:manifest=json.loads(zipf.read('manifest.json'))
        except Exception as exc:raise SystemExit('Missing valid backup manifest') from exc
        if manifest.get('format')!='textilehr-local-backup-v1':raise SystemExit('Unrecognized backup format')
        files=manifest['files']
        if 'textilehr.sqlite3' not in files:raise SystemExit('Backup database missing')
        expected=set(files)|{'manifest.json'}
        if set(zipf.namelist())!=expected:raise SystemExit('Backup contents disagree with manifest')
        if sum(i.file_size for i in zipf.infolist())>3*1024**3:
            raise SystemExit('Backup exceeds supported local restore size')
        for name,digest in files.items():
            p=Path(name)
            if p.is_absolute() or '..' in p.parts or len(p.parts)>2 or (p.parts[0] not in ('uploads','exports') and name!='textilehr.sqlite3'):
                raise SystemExit('Unsafe path in backup')
            if sha256(zipf.read(name)).hexdigest()!=digest:raise SystemExit('Backup hash mismatch')
        destination.mkdir(parents=True,exist_ok=True,mode=0o700)
        for name in files:
            target=destination/name
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with target.open('xb') as dst:dst.write(zipf.read(name))
            if os.name!='nt':target.chmod(0o600)
    print('Restored into:',destination)
    print('Review local permissions and start the matching release; API session keys were not restored.')


def purge(data_dir:Path,days:int=30,workspace:str|None=None):
    from backend.storage import Store
    store=Store(data_dir)
    if workspace:
        result=store.purge_retention(workspace,retention_days=days)
        print(f"Purged workspace {workspace}: {result}")
    else:
        workspaces=store.list_workspaces()
        total_jobs=total_exp=total_docs=0
        for ws in workspaces:
            res=store.purge_retention(ws['id'],retention_days=days)
            total_jobs+=res['purged_jobs']
            total_exp+=res['purged_exports']
            total_docs+=res['purged_documents']
        print(f"Purged across {len(workspaces)} workspaces: jobs={total_jobs}, exports={total_exp}, docs={total_docs}, retention_days={days}")


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='operation',required=True)
    b=sub.add_parser('backup');b.add_argument('--data-dir',type=Path,required=True);b.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('restore');r.add_argument('--archive',type=Path,required=True);r.add_argument('--destination',type=Path,required=True)
    p=sub.add_parser('purge');p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--days',type=int,default=30);p.add_argument('--workspace',type=str,default=None)
    args=parser.parse_args()
    if args.operation=='backup':backup(args.data_dir,args.output)
    elif args.operation=='restore':restore(args.archive,args.destination)
    elif args.operation=='purge':purge(args.data_dir,args.days,args.workspace)


if __name__=='__main__':main()
