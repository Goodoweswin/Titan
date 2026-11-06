"""Exercise IF result selection using the shipped engine and real IF jobs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def main():
    parser=argparse.ArgumentParser();parser.add_argument('engine');args=parser.parse_args()
    engine=str(Path(args.engine).resolve())
    with tempfile.TemporaryDirectory(prefix='titan-source-links-') as folder:
        session=dict(pid=os.getpid(),token='source-links-verification',library_root=folder)
        worker=subprocess.Popen([engine,'--stdio-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        request=0
        def rpc(command,payload=None):
            nonlocal request
            request+=1
            worker.stdin.write(json.dumps(dict(request_id=request,command=command,payload=payload or {},session=session),ensure_ascii=False)+'\n');worker.stdin.flush()
            response=json.loads(worker.stdout.readline())
            assert response['request_id']==request
            if not response['ok']:raise ValueError(response['error'])
            return response['data']
        try:
            p=rpc('if_demo')
            job=rpc('if_start_job',dict(project=p,operation='batch',options=dict(field_ids=[f['id'] for f in p['fields']])))
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                status=rpc('if_job_status',dict(job_id=job['job_id']))
                if status['status'] in ['completed','failed','cancelled']:break
                time.sleep(.1)
            assert status['status']=='completed',status
            p=rpc('if_accept_job',dict(project=p,job_id=job['job_id']))
            p=rpc('if_save',dict(project=p,expected_revision=p['saved_revision']))
            c=rpc('stats_source_catalog',dict(path=p['project_path']))
            choices=[v for v in c['choices'] if json.loads(v['key'])['metric'] in ['mean','positive_area_fraction']]
            assert len(choices)==2 and all(v['n']==6 and v['missing']==0 for v in choices)
            stats=rpc('stats_from_source',dict(path=c['path'],keys=[v['key'] for v in choices],expected_signature=c['signature'],confirmed=True))
            assert len(stats['datasets'])==2
            table=stats['datasets'][0];run=rpc('stats_analyze',dict(dataset=table))
            rpc('stats_export',dict(dataset=table,style=table['style'],run=run,destination=str(Path(folder)/'export')))
            assert rpc('stats_source_status',dict(source=table['source']))['state']=='current'
            p['fields'][0]['bio_id']='changed-bio';p['revision']+=1
            p=rpc('if_save',dict(project=p,expected_revision=p['saved_revision']))
            assert rpc('stats_source_status',dict(source=table['source']))['state']=='changed'
            stats=rpc('stats_update_source',dict(project=stats,dataset_id=table['id']))
            assert stats['datasets'][0]['rows'][0]['label']=='changed-bio'
            reopened=rpc('stats_open',dict(path=stats['project_path']))
            assert reopened['datasets'][1]['source']['unit']=='%'
            print(json.dumps(dict(passed=True,engine=engine,checks=['IF real batch worker','sample-level catalog n=6','two selected metrics','percent unit','linked stats save/reopen','figure and table export','source change detection','explicit refresh']),ensure_ascii=False,indent=2))
        finally:
            worker.stdin.close()
            try:worker.wait(timeout=10)
            except subprocess.TimeoutExpired:worker.kill();worker.wait()


if __name__=='__main__':main()
