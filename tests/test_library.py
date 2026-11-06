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

def test_export_archive_records_and_verifies_the_exact_exported_png(tmp_path):
 from titan_wb.export import export_analysis
 p,r,s=saved_fixture(tmp_path);destination=tmp_path/'export';audit=export_analysis(p,r,str(destination),figure_settings={'error':'sem'})
 origin=dict(path=str(destination),png_sha256=audit['outputs']['plot.png'])
 doc=save_figure(p,r,audit['figure_settings'],'exported',s,export_origin=origin)
 loaded=load_figure(p['project_path'],doc['id'],s)
 assert loaded['document']['export_origin']==origin
 with pytest.raises(ValueError,match='导出图'):save_figure(p,r,{'error':'sd','title':'different'},'mismatch',s,export_origin=origin)
 assert len(library_list(s)[0]['figures'])==1

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


def test_workspace_groups_wb_and_if_without_moving_files(tmp_path):
    from titan_wb.engine import dispatch

    s = session(tmp_path)
    def call(command, **payload):
        return dispatch(dict(command=command, payload=payload, session=s))

    wb = call('library_create', name='AKT')
    original_index = Path(s['library_root']) / 'index.json'
    before = original_index.read_bytes()
    assert call('library_workspace')['entries'][0]['collection_id'] is None
    assert original_index.read_bytes() == before

    group = call('library_create_collection', name='皮肤衰老')
    fluorescence = call('if_new', name='p16', collection_id=group['id'])
    call('library_assign', entry_id=wb['entry']['entry_id'], collection_id=group['id'])
    call('library_set_resume', entry_id=wb['entry']['entry_id'], resume={'view': 'results'})
    entries = {entry['name']: entry for entry in call('library_workspace')['entries']}
    assert entries['AKT']['resume'] == {'view': 'results'}
    assert entries['AKT']['collection_id'] == entries['p16']['collection_id'] == group['id']
    assert entries['p16']['path'] == fluorescence['project_path']
    call('library_remove_collection', id=group['id'])
    assert all(entry['collection_id'] is None for entry in call('library_workspace')['entries'])
    assert Path(fluorescence['project_path']).is_dir()


def test_workspace_failed_creation_rolls_back_and_retry_registers_once(tmp_path, monkeypatch):
    from titan_wb import library

    s = session(tmp_path)
    atomic_write = library.atomic_json
    with monkeypatch.context() as mock:
        def fail_index(*args):
            raise OSError('injected index failure')
        mock.setattr(library, 'atomic_json', fail_index)
        with pytest.raises(OSError, match='index failure'):
            library.library_create('AKT', s, new_collection_name='皮肤衰老')
    assert not list((Path(s['library_root']) / 'Projects').iterdir())
    assert library.atomic_json is atomic_write
    created = library.library_create('AKT', s, new_collection_name='皮肤衰老')
    catalog = library.library_workspace(s)
    assert len(catalog['entries']) == len(catalog['projects']) == 1
    assert created['entry']['collection_id'] == catalog['projects'][0]['id']


def test_copy_and_relocation_preserve_distinct_memberships(tmp_path):
    from titan_wb import library

    s = session(tmp_path)
    group = library.library_create_collection('课题', s)
    source = library.library_create('AKT', s, collection_id=group['id'])
    copy_path = tmp_path / 'copy.titanwb'
    save_project(source['project'], str(copy_path), None, s)
    copy = library_register(str(copy_path), s, source_entry_id=source['entry']['entry_id'])
    assert copy['entry_id'] != source['entry']['entry_id']
    assert copy['collection_id'] == group['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(library.library_assign, copy['entry_id'], None, s),
            pool.submit(library_register, str(copy_path), s, touch_opened=False),
        ]
        for future in futures:
            future.result()
    moved = tmp_path / 'moved.titanwb'
    copy_path.rename(moved)
    relocated = library_register(str(moved), s, copy['entry_id'])
    assert relocated['entry_id'] == copy['entry_id']
    assert relocated['collection_id'] is None
    with pytest.raises(ValueError, match='课题'):
        library.library_assign(copy['entry_id'], 'missing', s)
    assert library_register(str(moved), s, touch_opened=False)['last_opened'] == relocated['last_opened']


def test_project_outputs_keep_export_revision_and_follow_analysis(tmp_path):
    from titan_wb.engine import dispatch

    project, result, s = saved_fixture(tmp_path)
    folder = tmp_path / 'export'
    dispatch(dict(command='export', payload=dict(project=project, result=result, destination=str(folder)), session=s))
    state = dispatch(dict(command='library_workspace', session=s))
    entry = state['entries'][0]
    artifact, = entry['artifacts']
    assert artifact['source_revision'] == result['input_revision']
    assert artifact['kind'] == 'result_export'
    assert str(folder / 'results.xlsx') in artifact['files']
    group = dispatch(dict(command='library_create_collection', payload={'name': '课题'}, session=s))
    dispatch(dict(command='library_assign', payload=dict(entry_id=entry['entry_id'], collection_id=group['id']), session=s))
    shutil.rmtree(folder)
    current = dispatch(dict(command='library_workspace', session=s))['entries'][0]
    assert current['collection_id'] == group['id']
    assert current['artifacts'][0]['id'] == artifact['id']
    assert current['artifacts'][0]['available'] is False


def test_failed_export_registration_can_retry_without_exporting_again(tmp_path, monkeypatch):
    from titan_wb import library
    from titan_wb.engine import dispatch

    project, result, s = saved_fixture(tmp_path)
    folder = tmp_path / 'export'
    with monkeypatch.context() as mock:
        def fail_index(*args, **kwargs):
            raise OSError('index unavailable')
        mock.setattr(library, 'library_record_export', fail_index)
        out = dispatch(dict(command='export', payload=dict(project=project, result=result, destination=str(folder)), session=s))
    assert (folder / 'results.xlsx').is_file()
    retry = out['library_export_retry']
    for _ in range(2):
        dispatch(dict(command='library_record_export', payload=retry, session=s))
    assert len(library.library_workspace(s)['entries'][0]['artifacts']) == 1


def test_relocation_preflight_rejects_existing_if_copy_without_releasing_its_lock(tmp_path):
    from titan_if import projects, service

    s = session(tmp_path)
    original = service.dispatch('if_new', {'name': 'IF'}, s)
    copy_path = tmp_path / 'copy.titanif'
    copied = projects.save_project(original, str(copy_path), None, s)
    library_register(copied['project_path'], s)
    owner = next(entry for entry in library_list(s) if entry['path'] == original['project_path'])
    with pytest.raises(ValueError, match='另一条'):
        service.dispatch('if_open', {'path': str(copy_path), 'entry_id': owner['entry_id']}, s)
    assert (copy_path / '.writer.lock').is_file()


def test_republished_path_updates_version_and_rejects_changed_output(tmp_path):
    from titan_wb.engine import dispatch
    from titan_wb.library import library_target, library_workspace

    p, result, s = saved_fixture(tmp_path)
    folder = tmp_path / 'out'
    def publish():
        dispatch(dict(command='export', payload=dict(project=p, result=result, destination=str(folder)), session=s))
        return library_workspace(s)['entries'][0]
    first = publish()['artifacts'][0]
    folder.rename(tmp_path / 'earlier')
    p['revision'] += 1
    result = analyze(p)
    entry = publish()
    later, = entry['artifacts']
    assert later['id'] != first['id'] and later['source_revision'] == result['input_revision']
    book = folder / 'results.xlsx'
    book.write_bytes(b'replaced externally')
    with pytest.raises(ValueError, match='已变化'):
        library_target(entry['entry_id'], later['id'], s)


def test_copied_wb_history_keeps_its_plot_without_claiming_source_export(tmp_path):
    from titan_wb.engine import dispatch
    from titan_wb.library import library_workspace

    p, result, s = saved_fixture(tmp_path)
    folder = tmp_path / 'out'
    published = dispatch(dict(command='export', payload=dict(project=p, result=result, destination=str(folder)), session=s))
    save_figure(p, result, {}, '图表', s, export_origin={'path':str(folder),'png_sha256':published['outputs']['plot.png']})
    dest = tmp_path / 'copy.titanwb'
    copied = save_project(p, str(dest), None, s)
    library_register(copied['project_path'], s)
    entries = {entry['path']:entry for entry in library_workspace(s)['entries']}
    assert len(entries[p['project_path']]['artifacts']) == 1
    assert not entries[copied['project_path']]['artifacts']
    assert len(entries[copied['project_path']]['figures']) == 1


def test_malformed_wb_plot_catalog_does_not_hide_unaffected_entries(tmp_path):
    from titan_wb.library import library_workspace

    s = session(tmp_path)
    first = library_create('Malformed', s)['project']
    library_create('Unaffected', s)
    folder = Path(first['project_path']) / 'figures'
    folder.mkdir()
    (folder / 'catalog.json').write_text(json.dumps({
        'version':1, 'figures':[{'id':'a','current_version':'b','versions':[{'version_id':'b'}]}]
    }))
    rows = {entry['name']:entry for entry in library_workspace(s)['entries']}
    assert rows['Unaffected']['available']
    assert rows['Malformed']['available'] and rows['Malformed']['figure_error']
