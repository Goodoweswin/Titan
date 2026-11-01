"""Environment for testing packaged workers without the development Python."""
import os
from pathlib import Path


def packaged_environment():
    env=dict(os.environ)
    for name in ['PYTHONHOME','PYTHONPATH','VIRTUAL_ENV']:
        env.pop(name,None)
    env['PATH']=str(Path(env.get('SystemRoot','C:/Windows'))/'System32') if os.name=='nt' else '/usr/bin:/bin'
    env['HOME']=str(Path.home())
    env['PYTHONUTF8']='1'
    return env
