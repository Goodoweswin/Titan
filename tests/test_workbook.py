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
 assert set(book.sheetnames)=={'说明','泳道结果','原始测量','参考归一化','生物学汇总','统计结果','样本信息','图像来源','图表'}
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
