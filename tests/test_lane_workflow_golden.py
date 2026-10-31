import csv,json
from pathlib import Path
from test_lane_results import fixture
from titan_wb.analysis import analyze
from titan_wb.projects import save_project,open_project
from titan_wb.export import export_analysis

def test_lane_measurements_survive_display_save_reopen_and_audited_export(tmp_path):
 p=fixture(tmp_path);p['images'][0]['display_inverted']=True
 r=analyze(p);values={m['id']:m for m in r['measurements']}
 assert values['t']['raw_sum']==48000 and values['t']['area_px']==16
 assert values['t']['background_mean']==1000 and values['t']['corrected_sum']==32000
 assert values['r']['raw_sum']==12000 and values['r']['corrected_sum']==8000
 source=Path(p['images'][0]['path']);session=dict(pid=0,token='golden')
 saved=save_project(p,str(tmp_path/'golden.titanwb'),None,session);source.unlink()
 reopened=open_project(saved['project_path'],session);result=analyze(reopened)
 assert result['lane_results'][0]['normalized']==4 and result['lane_results'][1]['normalized'] is None
 output=tmp_path/'export';export_analysis(reopened,result,str(output))
 rows=list(csv.DictReader((output/'lanes.csv').open(encoding='utf-8-sig')))
 assert float(rows[0]['normalized'])==4 and rows[1]['normalized']=='' and rows[1]['status']=='not_detected'
 exported=json.loads((output/'project.json').read_text())
 assert exported['images'][0]['display_inverted'] is True
 assert exported['lane_layouts']==reopened['lane_layouts'] and exported['band_sets']==reopened['band_sets']
