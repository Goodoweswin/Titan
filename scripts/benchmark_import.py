"""Measure installed worker startup and five warm import sequences."""
import argparse,json,subprocess,time,statistics,sys
from pathlib import Path

def benchmark(binary,source,repeats=5):
    rows=[]
    for repeat in range(repeats):
        start=time.perf_counter()
        p=subprocess.Popen([str(binary),'--stdio-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        request_id=0
        def call(command,payload=None):
            nonlocal request_id
            request_id+=1;t=time.perf_counter()
            p.stdin.write(json.dumps(dict(request_id=request_id,command=command,payload=payload or {}))+'\n');p.stdin.flush()
            response=json.loads(p.stdout.readline())
            assert response.get('request_id')==request_id and response['ok'],response
            return response['data'],time.perf_counter()-t
        try:
            health,_=call('health');cold=time.perf_counter()-start
            info,listing=call('inspect_image',dict(path=str(source)))
            eligible=[row for row in info['pages'] if row['error'] is None]
            page=next((row['page_index'] for row in eligible if row['dtype']=='uint16'),eligible[0]['page_index'])
            _,preview=call('preview_image_page',dict(path=str(source),page_index=page,expected_sha256=info['sha256']))
            project,_=call('new_project',dict(name='性能验证'))
            _,importing=call('import_image',dict(project=project,path=str(source),page_index=page,expected_sha256=info['sha256']))
            again,_=call('health');assert health['worker_pid']==again['worker_pid']
            rows.append(dict(cold_start=cold,listing=listing,preview=preview,import_page=importing,worker_starts=1))
            print(json.dumps(rows[-1]),flush=True)
        finally:
            p.stdin.close()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
            p.stdout.close();p.stderr.close()
    return dict(binary=str(binary),source_name=source.name,file_bytes=source.stat().st_size,repeats=repeats,runs=rows,
                summary={key:dict(median=statistics.median(row[key] for row in rows),maximum=max(row[key] for row in rows)) for key in ['cold_start','listing','preview','import_page']})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=benchmark(args.binary.resolve(),args.source.resolve());args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
