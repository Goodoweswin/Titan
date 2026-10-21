"""Run every existing test layer; only actual zero exits count as passing."""
import datetime
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
cp=sys.argv[1]
out=ROOT/'artifacts/checkpoints'/cp
out.mkdir(parents=True,exist_ok=True)
commands=[('python',[str(ROOT/'.venv/bin/python'),'-m','pytest','-q']),
          ('frontend',['npm','test','--','--reporter=dot']),
          ('build',['npm','run','build']),
          ('rust',['cargo','test','--manifest-path','src-tauri/Cargo.toml','--quiet'])]
results=[]
for name,cmd in commands:
 with (out/f'{name}.log').open('w') as f:
  p=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 results.append(dict(layer=name,command=cmd,exit_code=p.returncode))
 print(name, 'PASS' if p.returncode==0 else 'FAIL', flush=True)
 if p.returncode:
  print((out/f'{name}.log').read_text()[-3000:]);break
(out/'checks.json').write_text(json.dumps({'cp':cp,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':results},indent=2))
sys.exit(0 if len(results)==len(commands) and all(x['exit_code']==0 for x in results) else 1)
