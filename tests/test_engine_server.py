import json
import subprocess
import sys
from pathlib import Path

ENTRY=Path(__file__).resolve().parents[1]/'backend/entry.py'

def test_multiple_requests_share_worker_and_recover_from_bad_input():
 p=subprocess.Popen([sys.executable,str(ENTRY),'--stdio-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8')
 lines=[dict(request_id=1,command='health'),'not json',dict(request_id=2,command='unknown'),dict(request_id=3,command='health')]
 output,_=p.communicate('\n'.join(s if isinstance(s,str) else json.dumps(s) for s in lines)+'\n',timeout=10)
 rows=[json.loads(s) for s in output.splitlines()]
 assert len(rows)==4
 first,invalid,unknown,third=rows
 assert first['ok'] and first['request_id']==1
 # Windows virtualenv redirectors have a different PID from their Python child.
 assert isinstance(first['data']['worker_pid'],int) and first['data']['worker_pid']>0
 assert not invalid['ok'] and not unknown['ok']
 assert third['data']['worker_pid']==first['data']['worker_pid']
 assert third['request_id']==3
 assert p.returncode==0

def test_oversized_line_does_not_desynchronize_following_request():
 payload='x'*(20*1024*1024+1)+'\n'+json.dumps(dict(request_id=4,command='health'))+'\n'
 p=subprocess.run([sys.executable,str(ENTRY),'--stdio-server'],input=payload,capture_output=True,text=True,encoding='utf-8',timeout=10)
 rows=[json.loads(s) for s in p.stdout.splitlines()]
 assert len(rows)==2 and not rows[0]['ok'] and rows[1]['request_id']==4
