import copy,warnings
import numpy as np
import pytest
from titan_wb.figures import validate_figure_settings,figure_data,jitter_positions


def project_and_result():
 from titan_wb.models import new_project
 p=new_project('figures');p['settings'].update(design_confirmed=True,control_group='A')
 p['samples']=[dict(id=f'S{i}',bio_id=f'B{i}',group=g,kind='biological') for i,g in enumerate(['A','A','B','B','C','C'])]
 p['lanes']=[dict(id=f'L{i}',sample_id=f'S{i}',membrane_id='M1') for i in range(6)]
 p['rois']=[dict(id=f'r{i}',lane_id=f'L{i}',role='target',analyte='蛋白X') for i in range(6)]
 bio=[dict(sample_id=f'S{i}',bio_id=f'B{i}',group=g,analyte='蛋白X',analysis_block='M1',membrane_id='M1',value=v,fold=v/2,pair_id='') for i,(g,v) in enumerate(zip(['A','A','B','B'],[1.,3.,4.,8.]))]
 r=dict(project_id=p['id'],input_revision=0,biological=bio,lane_results=[],multigroup_comparisons=[],statistics=[])
 return p,r

def test_grouped_figure_keeps_empty_group_and_full_precision_summaries():
 p,r=project_and_result();f=validate_figure_settings({});data=figure_data(p,r,f);groups=data['panels'][0]['groups']
 assert [g['key'] for g in groups]==['A','B','C']
 assert [g['n'] for g in groups]==[2,2,0]
 assert groups[0]['mean']==2 and groups[0]['sd']==pytest.approx(2**.5)
 assert groups[2]['mean'] is None and groups[2]['ci95'] is None
 assert data['value_mode']=='normalized'

def test_colors_and_identity_do_not_change_on_filter_or_reordering():
 p,r=project_and_result();config=validate_figure_settings({'colors':{'A':'#112233'},'group_order':['C','A','B'],'display_labels':{'A':'WT'}})
 groups=figure_data(p,r,config)['panels'][0]['groups']
 assert [g['key'] for g in groups]==['C','A','B']
 assert groups[1]['label']=='WT' and groups[1]['color']=='#112233'
 other=figure_data(p,{**r,'biological':[b for b in r['biological'] if b['group']!='A']},config)['panels'][0]['groups']
 assert other[2]['color']==groups[2]['color']

def test_one_panel_cannot_mix_fold_with_raw_or_hide_missing_control():
 p,r=project_and_result();r['biological'][1]['fold']=None
 with pytest.raises(ValueError,match='对照|倍数'):figure_data(p,r,validate_figure_settings({'value_mode':'fold'}))
 r['biological']=[{**v,'fold':None} for v in r['biological']]
 with pytest.raises(ValueError,match='对照|倍数'):figure_data(p,r,validate_figure_settings({'value_mode':'fold'}))

def test_unconfirmed_design_stays_per_lane_and_never_uses_group_means():
 p,r=project_and_result();p['settings']['design_confirmed']=False;r['biological']=[]
 r['lane_results']=[dict(analyte='蛋白X',membrane_id='M1',lane_id='L1',sample_id='S1',normalized=2,status='valid'),dict(analyte='蛋白X',membrane_id='M1',lane_id='L2',sample_id='S2',normalized=None,status='not_detected')]
 data=figure_data(p,r,validate_figure_settings({}))
 assert data['unit']=='lane' and [g['key'] for g in data['panels'][0]['groups']]==['L1/S1','L2/S2']
 assert data['panels'][0]['groups'][1]['status']=='not_detected'

@pytest.mark.parametrize('bad',[{'colors':{'A':'red'}},{'jitter':float('nan')},{'point_size':-1},{'y_min':4,'y_max':3},{'group_order':['A','A']},{'annotations':'madeup'},{'kind':'boxplot'},{'unknown':True}])
def test_invalid_settings_are_rejected_before_render(bad):
 with pytest.raises(ValueError):validate_figure_settings(bad)

def test_jitter_is_deterministic_bounded_and_does_not_change_values():
 first=jitter_positions(7,.2);assert first==jitter_positions(7,.2)
 assert max(first)<=.2 and min(first)>=-.2 and len(set(first))==7
 assert jitter_positions(1,.2)==[0]

def test_labels_render_offline_without_missing_chinese_glyphs(tmp_path):
 from titan_wb.export import plot_results
 p,r=project_and_result()
 with warnings.catch_warnings(record=True) as caught:
  warnings.simplefilter('always')
  plot_results(r,tmp_path,dict(panel_width=3,height=3,font_size=10,dpi=80),figure_settings={'title':'中文蛋白 $ literal','y_label':'归一化表达量'},project=p)
 assert (tmp_path/'plot.png').is_file() and (tmp_path/'plot.svg').is_file()
 assert not any('Glyph' in str(w.message) and 'missing' in str(w.message) for w in caught)

def test_annotations_only_use_selected_adjusted_pairwise_records():
 from titan_wb.figures import comparison_key
 p,r=project_and_result();row=dict(comparison_id='m',analyte='蛋白X',membrane_id='M1',group_a='A',group_b='B',p_adjusted=.04,scale='raw',status='valid',adjustment_method='tukey')
 r['multigroup_comparisons']=[row];r['multigroup_omnibus']=[dict(p_raw=.000001)]
 assert figure_data(p,r,{'annotations':'p'})['panels'][0]['comparisons']==[]
 data=figure_data(p,r,{'annotations':'p','comparison_ids':[comparison_key(row)]})
 assert data['panels'][0]['comparisons'][0]['p_adjusted']==.04

def test_standalone_caption_retains_fold_uncertainty_and_full_comparison_family(tmp_path,monkeypatch):
 from matplotlib.text import Text
 from titan_wb.export import plot_results
 from titan_wb.figures import comparison_key
 p,r=project_and_result()
 for value in r['biological']:value['fold']=value['value']
 row=dict(comparison_id='multi',family_id='multi:X:M1',analyte='蛋白X',membrane_id='M1',group_a='A',group_b='B',p_adjusted=.04,scale='raw',status='valid',adjustment_method='games_howell',family_scope='all_pairs',display_scope='control',groups=['A','B','C'])
 r['multigroup_comparisons']=[row]
 texts=[];original=Text.set_text
 def capture(self,text):texts.append(str(text));return original(self,text)
 monkeypatch.setattr(Text,'set_text',capture)
 plot_results(r,tmp_path,dict(panel_width=5,height=4,font_size=11,dpi=100),{'value_mode':'fold','annotations':'p','comparison_ids':[comparison_key(row)]},p)
 caption=' '.join(' '.join(texts).split())
 assert 'denominator uncertainty' in caption and 'not propagated' in caption
 assert 'multi:X:M1' in caption and 'all pairs' in caption and 'display: control' in caption
 assert 'no across-protein' in caption.lower()

def test_custom_axis_truncation_is_visible_in_figure_metadata():
 p,r=project_and_result();data=figure_data(p,r,{'y_min':1,'y_max':5})
 assert any('零基线' in w for w in data['panels'][0]['warnings'])
 assert any('隐藏' in w for w in data['panels'][0]['warnings'])

def test_merged_analysis_blocks_do_not_create_empty_source_membrane_panels():
 p,r=project_and_result();p['settings']['analysis_blocks']=[dict(id='combined',membrane_ids=['M1','M2'],merge_same_sample=True,pooled_reference_id='pool')]
 for i,lane in enumerate(p['lanes']):lane['membrane_id']='M1' if i<3 else 'M2'
 for row in r['biological']:row.update(analysis_block='combined',membrane_id='M1+M2')
 data=figure_data(p,r,{})
 assert [panel['analysis_block'] for panel in data['panels']]==['combined']
