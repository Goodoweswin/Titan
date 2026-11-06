import copy,json,os
from pathlib import Path
import pytest
from titan_stats.importers import import_table
from titan_stats.analysis import analyze
from titan_stats.models import signature,new_project
from titan_stats.render import render
from titan_stats.service import dispatch,export
from titan_stats import store

@pytest.fixture
def session(tmp_path):return dict(pid=os.getpid(),token='stats-test',library_root=str(tmp_path/'library'))

def data():
    d=import_table(text='Control\tA\tB\n1\t2\t4\n2\t3\t5\n3\t4\t6')['dataset']
    d['confirmed']=True;d['analysis'].update(method='anova',scope='all');return d

def test_shared_anova_reference_and_style_independence():
    d=data();r=analyze(d)
    assert r['omnibus']['statistic']==pytest.approx(7)
    assert r['omnibus']['p_raw']==pytest.approx(.027)
    sig=signature(d);d['style']['width_mm']=60;d['style']['colors']={d['groups'][0]['id']:'#ffffff'}
    assert signature(d)==sig
    d['rows'][0]['values'][d['groups'][0]['id']]='5'
    assert signature(d)!=sig

def test_paired_id_order_and_missing_pairs():
    d=import_table(text='ID\tBefore\tAfter\nP3\t1\t8\nP1\t1\t2\nP2\t1\t4')['dataset'];d['confirmed']=True;d['analysis'].update(method='paired',scale='log2')
    r=analyze(d);assert r['comparisons'][0]['statistic']==pytest.approx(3.464101615)
    d['rows'][0]['values'][d['groups'][1]['id']]=''
    with pytest.raises(ValueError,match='配对'):analyze(d)

def test_design_and_invalid_values_never_silently_drop():
    d=data();d['confirmed']=False
    with pytest.raises(ValueError,match='确认'):analyze(d)
    d['confirmed']=True;d['rows'][0]['values'][d['groups'][0]['id']]='bad'
    with pytest.raises(ValueError,match='有效数值'):analyze(d)
    with pytest.raises(ValueError):import_table(text='A\tB\n1\tNaN')

def test_project_save_conflict_and_library(session,tmp_path):
    p=dispatch('stats_new',{'name':'统计'},session);old=copy.deepcopy(p);p['name']='修改';p['revision']+=1
    p=dispatch('stats_save',{'project':p},session)
    assert store.load(p['project_path'],session)['name']=='修改'
    with pytest.raises(ValueError,match='版本'):dispatch('stats_save',{'project':old},session)
    from titan_wb.library import library_list
    assert library_list(session)[0]['module']=='stats'
    with pytest.raises(ValueError,match='写入者'):store.load(p['project_path'],{**session,'token':'other'})

def test_export_formats_small_panel_and_stale_block(tmp_path):
    d=data();r=analyze(d);style={**d['style'],'width_mm':60,'height_mm':50,'annotations':'p'}
    out=export(d,style,r,str(tmp_path/'export'))
    assert {'plot.png','plot.svg','plot.pdf','results.xlsx','analysis.json','methods.txt','observations.csv'}<=set(out['files'])
    assert '<text' in (tmp_path/'export/plot.svg').read_text()
    from PIL import Image
    image=Image.open(tmp_path/'export/plot.png');assert image.width==int(60/25.4*300)
    from openpyxl import load_workbook
    book=load_workbook(tmp_path/'export/results.xlsx');assert book['总体检验']['B8'].value is not None
    d['rows'][0]['values'][d['groups'][0]['id']]='99'
    with pytest.raises(ValueError,match='过期'):export(d,style,r,str(tmp_path/'stale'))
    assert not (tmp_path/'stale').exists()

def test_xlsx_sheets_and_formula_cache(tmp_path):
    from openpyxl import Workbook
    book=Workbook();book.active.append(['A','B']);book.active.append([1,2]);book.create_sheet('Second').append(['X','Y']);book['Second'].append([3,4]);file=tmp_path/'in.xlsx';book.save(file)
    result=import_table(path=str(file),sheet='Second');assert result['sheets']==['Sheet','Second'];assert result['dataset']['groups'][0]['label']=='X'
    book.active['A2']='=1+1';book.save(file)
    with pytest.raises(ValueError,match='公式'):import_table(path=str(file))

def test_wb_adapter_preserves_units_and_source_lock(session):
    from titan_wb.demo import make_demo
    from titan_wb.analysis import analyze as wb_analyze
    from titan_wb.stats_adapter import datasets
    p=make_demo();r=wb_analyze(p);tables=datasets(p,r)
    assert tables and all(t['source']['locked'] for t in tables)
    assert sum(len(t['source']['records']) for t in tables)==len(r['biological'])
    new=dispatch('stats_from_wb',{'project':p},session);new['revision']+=1
    d=new['datasets'][0];d['rows'][0]['values'][d['groups'][0]['id']]='77'
    with pytest.raises(ValueError,match='来源表'):dispatch('stats_save',{'project':new},session)

def test_long_import_preserves_identity_and_rejects_pseudoreplication():
    d=import_table(text='group,value,unit_id,pair_id\nA,1,Animal1,P1\nB,3,Animal1,P1\nA,2,Animal2,P2\nB,5,Animal2,P2',format='long')['dataset']
    d['confirmed']=True;d['analysis']['method']='welch'
    with pytest.raises(ValueError,match='共享'):analyze(d)
    d['analysis']['method']='paired';assert analyze(d)['comparisons'][0]['effect']==2.5
    with pytest.raises(ValueError,match='重复'):import_table(text='group,value,unit_id\nA,1,S1\nA,2,S1',format='long')

def test_display_group_order_and_alias_do_not_change_inference():
    d=data();r=analyze(d);style={**d['style'],'group_order':[g['id'] for g in reversed(d['groups'])],'annotations':'p','labels':{d['groups'][0]['id']:'对照'}}
    result=render(d,style,r)
    assert result['png'].startswith('data:image/png;base64,')
    assert signature(d)==r['signature']
