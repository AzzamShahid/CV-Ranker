"""Start/stop only this installation's local worker and API processes.

The installation identity and per-process creation time prevent unrelated
Python or other web servers from being terminated due to PID reuse.
"""
from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))  # scripts/web_control.py is executed directly by Windows .cmd files.


def data_dir():
    return Path(os.getenv('TEXTILEHR_DATA_DIR',Path.home()/'.textilehr-ai-web')).expanduser().resolve()


def active_process(pid,created,module):
    try:
        import psutil
        p=psutil.Process(pid)
        if abs(p.create_time()-created)>3:return None
        argv=p.cmdline()
        if '-m' not in argv or module not in argv:
            return None
        return p
    except (ImportError,OSError,Exception):return None


def health(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/v1/health',timeout=1.2) as r:
            return json.loads(r.read())
    except (URLError,TimeoutError,OSError,ValueError):return None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['start','stop','status'])
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    from backend.storage import Store
    store=Store()
    run=store.root/'web-processes.json'
    port=int(os.getenv('TEXTILEHR_PORT','8765'))
    current=json.loads(run.read_text()) if run.exists() else {}
    old_api=current.get('api',{})
    old_worker=current.get('worker',{})
    api=active_process(old_api.get('pid',0),old_api.get('created',0),'backend')
    worker=active_process(old_worker.get('pid',0),old_worker.get('created',0),'worker')
    if args.command=='status':
        print(f'TextileHR API: {"running" if api else "stopped"}; worker: {"running" if worker else "stopped"}')
        print(f'Local URL: http://127.0.0.1:{port}/')
        return
    if args.command=='stop':
        for label,p in (('api',api),('worker',worker)):
            if p is None:continue
            try:
                if os.name=='nt':
                    try:
                        p.send_signal(signal.CTRL_BREAK_EVENT)
                    except (SystemError,OSError,ValueError):
                        p.terminate()
                else:p.send_signal(signal.SIGTERM)
                p.wait(timeout=10)
                print(label,'stopped')
            except Exception as exc:
                try:
                    p.kill()
                    print(label,'stopped via kill')
                except Exception:
                    print(label,'could not be cleanly stopped; use local process inspector',type(exc).__name__)
        run.unlink(missing_ok=True)
        return
    other=health(port)
    if other and other.get('installation_id')!=store.installation_id:
        raise SystemExit(f'Port {port} is already used by another service. Set TEXTILEHR_PORT instead; nothing was killed.')
    if not other:
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0:
                raise SystemExit(f'Port {port} is already occupied. Choose another port.')
    logdir=store.root/'logs';logdir.mkdir(exist_ok=True)
    env=os.environ.copy();env['TEXTILEHR_DATA_DIR']=str(store.root)
    env['TEXTILEHR_HOST']='127.0.0.1';env['TEXTILEHR_PORT']=str(port)
    flag=(subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS) if os.name=='nt' else 0
    process_info={}
    for label,module,existing in (('worker','worker',worker),('api','backend',api)):
        if existing:
            process_info[label]={'pid':existing.pid,'created':existing.create_time()}
            continue
        output=open(logdir/(label+'.log'),'ab',buffering=0)
        child=subprocess.Popen([sys.executable,'-m',module],cwd=ROOT,env=env,
          stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
          creationflags=flag,close_fds=True)
        output.close()
        try:
            import psutil
            created=psutil.Process(child.pid).create_time()
        except ImportError:
            created=time.time()
        process_info[label]={'pid':child.pid,'created':created}
        print(f'{label} PID {child.pid}')
    run.write_text(json.dumps(process_info,indent=2))
    for i in range(40):
        status=health(port)
        if status and status.get('installation_id')==store.installation_id:
            print(f'TextileHR ready: http://127.0.0.1:{port}/')
            if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{port}/')
            return
        time.sleep(.25)
    raise SystemExit('API not ready. See local logs; worker/API process identities were saved for safe shutdown.')


if __name__=='__main__':main()
