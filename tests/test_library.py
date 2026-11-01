import copy,json,os,shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from titan_wb.library import library_create,library_list,library_register,library_remove,save_figure,load_figure,source_signature
from titan_wb.projects import save_project,open_project,release_project
from titan_wb.analysis import analyze


def session(tmp_path,token='library'):
 return dict(pid=os.getpid(),token=token,library_root=str(tmp_path/'library'))

def saved_fixture(tmp_path):
 from test_lane_results import fixture
 s=session(tmp_path);p=save_project(fixture(tmp_path),str(tmp_path/'experiment.titanwb'),None,s);library_register(p['project_path'],s)
 return p,analyze(p),s

def test_new_experiment_is_managed_saved_and_reopenable(tmp_path):
 s=session(tmp_path);created=library_create('实验甲',s);p=created['project'];entry=created['entry']
 assert p['saved_revision']==p['revision']==0
 assert Path(p['project_path']).is_relative_to(Path(s['library_root'])/'Projects')
 assert open_project(p['project_path'],s)['name']=='实验甲'
 assert library_list(s)[0]['entry_id']==entry['entry_id']
 assert library_register(p['project_path'],s)['entry_id']==entry['entry_id'] and len(library_list(s))==1

def test_save_as_same_scientific_id_is_a_distinct_library_entry(tmp_path):
 s=session(tmp_path);first=library_create('first',s);p=first['project']
 copy_project=save_project(p,str(tmp_path/'copy.titanwb'),None,s);second=library_register(copy_project['project_path'],s)
 assert second['project_id']==first['entry']['project_id']
 assert second['entry_id']!=first['entry']['entry_id'] and len(library_list(s))==2
 library_remove(first['entry']['entry_id'],s)
 assert Path(p['project_path']).is_dir() and len(library_list(s))==1

def test_concurrent_index_updates_do_not_lose_entries(tmp_path):
 s=session(tmp_path)
 with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda i:library_create('P'+str(i),s),range(8)))
 assert {e['name'] for e in library_list(s)}=={'P'+str(i) for i in range(8)}

def test_corrupt_index_is_reported_and_never_overwritten_as_empty(tmp_path):
 s=session(tmp_path);library_create('p',s);path=Path(s['library_root'])/'index.json';path.write_text('{bad')
 with pytest.raises(ValueError,match='列表|索引'):library_list(s)
 with pytest.raises(ValueError):library_create('new',s)
 assert path.read_text()=='{bad'

def test_missing_project_remains_visible_and_can_be_relocated(tmp_path):
 s=session(tmp_path);created=library_create('p',s);old=created['project']['project_path'];new=tmp_path/'moved.titanwb';shutil.move(old,new)
 entry=library_list(s)[0];assert not entry['available'] and entry['entry_id']==created['entry']['entry_id']
 located=library_register(str(new),s,entry_id=entry['entry_id'])
 assert located['entry_id']==entry['entry_id'] and library_list(s)[0]['available']

def test_writer_lock_identity_does_not_depend_on_library_context(tmp_path):
 s=session(tmp_path);p=library_create('p',s)['project']
 assert open_project(p['project_path'],{k:v for k,v in s.items() if k!='library_root'})['id']==p['id']
 release_project(p['project_path'],dict(s,library_root='/other-context'))
 assert not (Path(p['project_path'])/'.writer.lock').exists()

def test_figure_is_frozen_restyled_and_updated_only_explicitly(tmp_path):
 p,r,s=saved_fixture(tmp_path);doc=save_figure(p,r,{},'AKT 柱图',s)
 loaded=load_figure(p['project_path'],doc['id'],s);old_version=doc['current_version']
 assert loaded['result']['lane_results'][0]['normalized']==4
 changed=copy.deepcopy(p);changed['revision']+=1;changed['rois'][1]['rect']=[2,25,5,29]
 for roi in changed['rois']:roi['reviewed_revision']=changed['revision']
 changed['lane_layouts'][0]['confirmed_revision']=changed['revision']
 current=save_project(changed,p['project_path'],p['saved_revision'],s);current_result=analyze(current)
 assert current_result['lane_results'][0]['normalized']==3
 assert library_list(s)[0]['figures'][0]['source_stale']
 restyled=save_figure(loaded['project'],loaded['result'],{'colors':{'L1/S1':'#112233'}},'restyled',s,figure_id=doc['id'],expected_version=old_version)
 assert load_figure(p['project_path'],doc['id'],s)['result']['lane_results'][0]['normalized']==4
 with pytest.raises(ValueError,match='源|更新'):save_figure(current,current_result,{},'wrong implicit update',s,figure_id=doc['id'],expected_version=restyled['current_version'])
 updated=save_figure(current,current_result,{},'updated',s,figure_id=doc['id'],expected_version=restyled['current_version'],update_source=True)
 assert len(updated['versions'])==3 and not library_list(s)[0]['figures'][0]['source_stale']
 assert load_figure(p['project_path'],doc['id'],s,version_id=old_version)['result']['lane_results'][0]['normalized']==4
 assert load_figure(p['project_path'],doc['id'],s)['result']['lane_results'][0]['normalized']==3

def test_figure_snapshot_is_portable_with_whole_project_copy(tmp_path):
 p,r,s=saved_fixture(tmp_path);doc=save_figure(p,r,{},'chart',s)
 copied=save_project(p,str(tmp_path/'copy.titanwb'),None,s);shutil.rmtree(p['project_path'])
 loaded=load_figure(copied['project_path'],doc['id'],s)
 assert analyze(loaded['project'])['lane_results'][0]['normalized']==4
 assert loaded['png'].startswith('data:image/png;base64,')

def test_save_as_waits_for_figure_transaction_and_omits_uncommitted_stages(tmp_path):
 import threading,time
 from titan_wb.projects import operation_lock
 p,r,s=saved_fixture(tmp_path);doc=save_figure(p,r,{},'chart',s)
 figures=Path(p['project_path'])/'figures';stage=figures/'.figure-stage-uncommitted';stage.mkdir();(stage/'partial').write_text('incomplete')
 started=threading.Event()
 def copy_project():
  started.set();return save_project(p,str(tmp_path/'copy.titanwb'),None,s)
 with ThreadPoolExecutor(max_workers=1) as pool:
  with operation_lock(figures,'.catalog.lock'):
   future=pool.submit(copy_project);assert started.wait(1);time.sleep(.12)
   assert not future.done(),'Save as must wait for the source figure catalog transaction'
  copied=future.result(timeout=5)
 assert not (Path(copied['project_path'])/'figures'/stage.name).exists()
 assert load_figure(copied['project_path'],doc['id'],s)['document']['id']==doc['id']

def test_failed_or_concurrent_figure_writes_cannot_replace_a_valid_document(tmp_path):
 p,r,s=saved_fixture(tmp_path);doc=save_figure(p,r,{},'chart',s)
 with pytest.raises(ValueError):save_figure(p,r,{'colors':{'x':'invalid'}},'bad',s)
 with pytest.raises(ValueError):save_figure(p,r,{},'old writer',s,figure_id=doc['id'],expected_version='obsolete')
 assert len(library_list(s)[0]['figures'])==1
 assert load_figure(p['project_path'],doc['id'],s)['document']['current_version']==doc['current_version']
 with pytest.raises(ValueError):load_figure(p['project_path'],'../../escape',s)
 with pytest.raises(ValueError):save_figure({**p,'read_only':True},r,{},'read only',s)

def test_style_only_revision_does_not_change_analytical_source_identity(tmp_path):
 p,r,s=saved_fixture(tmp_path);styled=copy.deepcopy(p);styled['revision']+=1;styled['figure_settings']={'colors':{'control':'#112233'}}
 for roi in styled['rois']:roi['reviewed_revision']=styled['revision']
 styled['lane_layouts'][0]['confirmed_revision']=styled['revision']
 assert source_signature(p)==source_signature(styled)
 styled['rois'][1]['rect'][2]-=1
 assert source_signature(p)!=source_signature(styled)

def test_nested_project_copy_is_rejected_before_recursive_history_copy(tmp_path):
 p,r,s=saved_fixture(tmp_path);save_figure(p,r,{},'chart',s)
 dest=Path(p['project_path'])/'originals/nested.titanwb'
 with pytest.raises(ValueError,match='内部|嵌套'):save_project(p,str(dest),None,s)
 assert not dest.exists()

def test_metadata_mutex_is_exclusive_and_recovers_after_worker_exit(tmp_path):
 import subprocess,sys
 from titan_wb.projects import operation_lock
 script="from titan_wb.projects import operation_lock; from pathlib import Path; import sys,time\nwith operation_lock(Path(sys.argv[1]),'.test.lock'):\n print('locked',flush=True);time.sleep(10)"
 env={**os.environ,'PYTHONPATH':str(Path(__file__).parents[1]/'backend')}
 child=subprocess.Popen([sys.executable,'-c',script,str(tmp_path)],stdout=subprocess.PIPE,text=True,env=env)
 try:
  assert child.stdout.readline().strip()=='locked'
  with pytest.raises(ValueError):
   with operation_lock(tmp_path,'.test.lock',timeout=.05):pass
 finally:
  child.terminate();child.wait(timeout=3);child.stdout.close()
 with operation_lock(tmp_path,'.test.lock',timeout=.2):assert (tmp_path/'.test.lock').exists()

def test_new_figure_waits_for_its_first_saved_analysis_revision(tmp_path):
 p,r,s=saved_fixture(tmp_path);p=copy.deepcopy(p);p['revision']+=1;r['input_revision']=p['revision']
 for roi in p['rois']:roi['reviewed_revision']=p['revision']
 p['lane_layouts'][0]['confirmed_revision']=p['revision']
 with pytest.raises(ValueError,match='保存'):save_figure(p,r,{},'not saved yet',s)

def test_save_rechecks_disk_revision_after_acquiring_writer_lock(tmp_path,monkeypatch):
 import titan_wb.projects as projects
 s=session(tmp_path);p=library_create('old',s)['project'];original=projects.check_lock;path=Path(p['project_path'])/'project.json'
 def raced(root,session,acquire=True):
  original(root,session,acquire);disk=json.loads(path.read_text());disk.update(revision=1,name='other writer');path.write_text(json.dumps(disk))
 monkeypatch.setattr(projects,'check_lock',raced)
 with pytest.raises(ValueError,match='变化'):save_project(p,p['project_path'],0,s)
 assert json.loads(path.read_text())['name']=='other writer'

def test_project_manifest_with_windows_separators_opens_portably(tmp_path):
 p,r,s=saved_fixture(tmp_path);path=Path(p['project_path'])/'project.json';disk=json.loads(path.read_text())
 for image in disk['images']:image['path']=image['path'].replace('/','\\')
 path.write_text(json.dumps(disk))
 assert analyze(open_project(p['project_path'],s))['lane_results'][0]['normalized']==4
