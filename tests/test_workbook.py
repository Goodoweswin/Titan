import zipfile
import pytest
from test_lane_results import fixture
from titan_wb.analysis import analyze
from titan_wb.export import export_analysis


def sheet_rows(ws):
 rows=list(ws.values);return [dict(zip(rows[0],row)) for row in rows[1:]]

def test_real_excel_has_numeric_ratios_missing_slots_sources_and_same_chart(tmp_path):
 from openpyxl import load_workbook
 p=fixture(tmp_path);p['samples'][0]['name']='样本甲';r=analyze(p);out=tmp_path/'results'
 manifest=export_analysis(p,r,str(out));book=load_workbook(out/'results.xlsx',data_only=True)
 assert set(book.sheetnames)=={'说明','泳道结果','原始测量','参考归一化','生物学汇总','统计结果','样本信息','图像来源','图表','分组描述','多组总体检验','多重比较'}
 rows=sheet_rows(book['泳道结果'])
 assert rows[0]['样本名称']=='样本甲' and rows[0]['目标净积分']==32000
 assert rows[0]['内参净积分']==8000 and rows[0]['目标/内参']==4
 assert rows[0]['目标条带ID']=='t' and rows[0]['内参条带ID']=='r'
 assert rows[1]['泳道']=='L2' and rows[1]['目标/内参'] is None and rows[1]['状态']=='未检出'
 assert book['泳道结果'].freeze_panes=='A2' and book['泳道结果'].auto_filter.ref
 assert book['生物学汇总'].max_row==1 and book['统计结果'].max_row==1
 assert sheet_rows(book['原始测量'])[1]['原始积分']==48000
 assert sheet_rows(book['图像来源'])[0]['SHA256']==p['images'][0]['sha256']
 with zipfile.ZipFile(out/'results.xlsx') as z:
  media=[name for name in z.namelist() if name.startswith('xl/media/')]
  assert len(media)==1 and z.read(media[0])==(out/'plot.png').read_bytes()
 assert 'results.xlsx' in manifest['outputs']
 book.close()

def test_multigroup_workbook_exports_actual_style_units_family_and_simultaneous_intervals(tmp_path,monkeypatch):
 import json
 from openpyxl import load_workbook
 from test_multigroup import units,spec
 import titan_wb.normalization
 values=units(dict(A=[1,2,3],B=[2,3,4],C=[4,5,6]))
 for v in values:v['analyte']='AKT'
 monkeypatch.setattr(titan_wb.normalization,'normalize',lambda *args,**kwargs:([],values))
 p=fixture(tmp_path);p['samples'][0]['group']='A';p['samples'][1]['group']='B'
 p['settings'].update(design_confirmed=True,multigroup_comparisons=[{**spec(),'analyte':'AKT'}]);p['figure_settings']={'error':'sd'}
 r=analyze(p);out=tmp_path/'multi';manifest=export_analysis(p,r,str(out),{'font_size':13},{'error':'sem','colors':{'A':'#123456'},'group_order':['A','B','C']})
 book=load_workbook(out/'results.xlsx',data_only=True)
 groups=sheet_rows(book['分组描述']);a=next(g for g in groups if g['组别']=='A')
 assert a['n']==3 and a['均值']==2 and a['SD']==1 and a['SEM']==pytest.approx(1/3**.5)
 assert a['单位']=='biological' and a['颜色']=='#123456'
 omnibus=sheet_rows(book['多组总体检验'])[0]
 assert omnibus['F']==pytest.approx(7) and omnibus['分子自由度']==2 and omnibus['分母自由度']==6 and omnibus['总体 p']==pytest.approx(.027)
 pair=sheet_rows(book['多重比较'])[0];expected=r['multigroup_comparisons'][0]
 assert pair['效应 B−A']==pytest.approx(expected['effect']) and pair['同时95% CI下界']==pytest.approx(expected['ci95'][0])
 assert pair['调整后 p']==pytest.approx(expected['p_adjusted']) and pair['校正方法']=='tukey' and pair['校正家族范围']=='all_pairs'
 notes={row['项目']:row['内容'] for row in sheet_rows(book['说明'])}
 assert json.loads(notes['图形设置'])['error']=='sem' and json.loads(notes['图形尺寸'])['font_size']==13
 assert notes['分析源签名']==r['source_signature']
 config=json.loads((out/'project.json').read_text());assert config['figure_settings']==manifest['figure_settings'] and config['plot_settings']==manifest['plot_settings']
 assert config['figure_settings']['error']=='sem' and config['figure_settings']['colors']['A']=='#123456'
 assert (out/'multigroup_omnibus.csv').is_file() and (out/'multigroup_comparisons.csv').is_file() and (out/'group_summaries.csv').is_file()
 book.close()

@pytest.mark.parametrize('name',['=1+1','+danger','-sample','@name','中文样本'])
def test_excel_user_text_is_literal_and_does_not_become_a_formula(tmp_path,name):
 from openpyxl import load_workbook
 p=fixture(tmp_path);p['samples'][0]['name']=name;p['name']=name
 out=tmp_path/'results';export_analysis(p,analyze(p),str(out));book=load_workbook(out/'results.xlsx')
 for sheet in book:
  assert all(cell.data_type!='f' for row in sheet for cell in row)
 assert sheet_rows(book['泳道结果'])[0]['样本名称']==name
 book.close()

def test_all_missing_lanes_keep_their_plot_positions_and_export_empty_numeric_cells(tmp_path):
 from openpyxl import load_workbook
 from matplotlib.axes import Axes
 from unittest.mock import patch
 p=fixture(tmp_path);p['rois']=[r for r in p['rois'] if r['role']=='reference']
 for a in p['band_sets'][1]['assignments']:a.update(roi_id=None,status='not_detected')
 seen=[];original=Axes.set_xticks
 def capture(ax,ticks,labels=None,*args,**kwargs):
  if labels is not None:seen.extend(labels)
  return original(ax,ticks,labels,*args,**kwargs)
 out=tmp_path/'results'
 with patch.object(Axes,'set_xticks',capture):export_analysis(p,analyze(p),str(out))
 assert seen==['L1/S1','L2/S2']
 book=load_workbook(out/'results.xlsx',data_only=True)
 assert all(r['目标/内参'] is None for r in sheet_rows(book['泳道结果']))
 book.close()

def test_small_nonzero_results_and_p_values_are_not_formatted_as_zero(tmp_path):
 from openpyxl import load_workbook
 p=fixture(tmp_path);r=analyze(p);r['lane_results'][0]['normalized']=1e-8;r['normalized'][0]['normalized']=1e-8
 r['statistics']=[dict(analyte='AKT',comparison_id='test',family_id='family',test='welch',scale='raw',n_a=3,n_b=3,effect=.1,ci95=[.01,.2],p_raw=1e-8,p_adjusted=2e-8,warnings=[])]
 out=tmp_path/'results';export_analysis(p,r,str(out));book=load_workbook(out/'results.xlsx')
 for name,title in [('泳道结果','目标/内参'),('统计结果','原始 p')]:
  ws=book[name];col=[c.value for c in ws[1]].index(title)+1;cell=ws.cell(2,col)
  assert cell.value==1e-8 and (cell.number_format=='General' or 'E' in cell.number_format)
 book.close()

def test_excel_measurements_join_to_image_hashes_by_identity_not_filename(tmp_path):
 from openpyxl import load_workbook
 p=fixture(tmp_path);p['images'].append({**p['images'][0],'id':'same-name-other-image','sha256':p['images'][0]['sha256']})
 out=tmp_path/'results';export_analysis(p,analyze(p),str(out));book=load_workbook(out/'results.xlsx',data_only=True)
 sources={r['图像ID']:r for r in sheet_rows(book['图像来源'])}
 for measurement in sheet_rows(book['原始测量']):assert sources[measurement['图像ID']]['SHA256']==p['images'][0]['sha256']
 book.close()
