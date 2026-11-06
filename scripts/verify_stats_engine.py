"""Smoke-test the bundled engine without a Python runtime or application data."""
import argparse,json,os,subprocess,tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('engine');args=parser.parse_args();engine=str(Path(args.engine).resolve())
    with tempfile.TemporaryDirectory(prefix='titan-stats-bundled-') as temp:
        session=dict(pid=os.getpid(),token='bundle-verification',library_root=str(Path(temp)/'library'))
        def rpc(command,payload=None):
            process=subprocess.run([engine],input=json.dumps(dict(command=command,payload=payload or {},session=session)),text=True,capture_output=True,check=True)
            result=json.loads(process.stdout)
            if not result['ok']:raise RuntimeError(result['error'])
            return result['data']
        p=rpc('stats_demo');d=p['datasets'][0];run=rpc('stats_analyze',dict(dataset=d))
        assert abs(run['omnibus']['statistic']-7)<1e-10 and abs(run['omnibus']['p_raw']-.027)<1e-10
        d['runs'].append(run);d['style'].update(width_mm=60,height_mm=50,annotations='p');p['revision']+=1
        p=rpc('stats_save',dict(project=p));opened=rpc('stats_open',dict(path=p['project_path']))
        assert opened['datasets'][0]['runs'][0]['signature']==run['signature']
        dest=Path(temp)/'export';out=rpc('stats_export',dict(dataset=d,style=d['style'],run=run,destination=str(dest)))
        assert '<text' in (dest/'plot.svg').read_text() and (dest/'plot.pdf').read_bytes().startswith(b'%PDF')
        assert (dest/'results.xlsx').stat().st_size>1000
        long=rpc('stats_import',dict(text='group,value,unit_id\nA,1,S1\nB,2,S2',format='long'));assert len(long['dataset']['groups'])==2
        print(json.dumps(dict(base='v0.4.0-beta.2',engine=engine,passed=True,checks=['create','analyse F=7 P=.027','save','reopen','long table','PNG','editable SVG','PDF','Excel','JSON','methods'],files=out['files']),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
