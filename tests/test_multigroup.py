import copy,math
import numpy as np
import pytest
from titan_wb.multigroup import group_summary,compare_multigroup


def units(groups):
 return [dict(value=value,bio_id=f'{g}-{i}',sample_id=f'{g}-{i}',group=g,analyte='X',analysis_block='M1',membrane_id='M1') for g,values in groups.items() for i,value in enumerate(values)]

def spec(**changes):
 return dict(id='multi',analyte='X',membrane_id='M1',groups=['A','B','C'],control_group='A',method='anova',scope='all',scale='raw',**changes)

def test_summary_uses_sample_sd_sem_and_small_sample_t_interval():
 s=group_summary([1,2,3]);assert s['n']==3 and s['mean']==2 and s['sd']==1
 assert s['sem']==pytest.approx(1/math.sqrt(3))
 assert s['ci95']==pytest.approx([-.4841377117,4.4841377117])
 assert group_summary([])==dict(n=0,mean=None,sd=None,sem=None,ci95=None)
 assert group_summary([7])==dict(n=1,mean=7,sd=None,sem=None,ci95=None)

def test_hand_derived_ordinary_and_welch_anova():
 values=units(dict(A=[1,2,3],B=[2,3,4],C=[4,5,6]))
 a=compare_multigroup(values,spec())['omnibus']
 assert (a['df_num'],a['df_den'])==(2,6) and a['statistic']==pytest.approx(7) and a['p_raw']==pytest.approx(.027)
 w=compare_multigroup(values,{**spec(),'method':'welch_anova'})['omnibus']
 assert (w['df_num'],w['df_den'])==pytest.approx((2,4)) and w['statistic']==pytest.approx(6) and w['p_raw']==pytest.approx(.0625)

def test_tukey_published_scipy_medicine_example_has_correct_B_minus_A_direction():
 # Published SciPy tukey_hsd example, independent rounded CI/P oracle.
 values=units(dict(A=[24.5,23.5,26.4,27.1,29.9],B=[28.4,34.2,29.5,32.2,30.1],C=[26.1,28.3,24.3,26.2,27.8]))
 rows=compare_multigroup(values,spec())['comparisons'];ab=next(r for r in rows if (r['group_a'],r['group_b'])==('A','B'))
 assert len(rows)==3 and ab['effect']==pytest.approx(4.6)
 assert ab['p_adjusted']==pytest.approx(.014,abs=.0005)
 assert ab['ci95']==pytest.approx([.951,8.249],abs=.0005)
 assert ab['adjustment_method']=='tukey' and ab['ci_method']=='simultaneous_95'
 assert ab['p_raw'] is None

def test_dunnett_published_example_and_reproducible_integration():
 values=units(dict(A=[2.9,3.0,2.5,2.6,3.2],B=[3.8,2.7,4.0,2.4],C=[2.8,3.4,3.7,2.2,2.0]))
 s={**spec(),'scope':'control'};r=compare_multigroup(values,s);again=compare_multigroup(values,s)
 assert r==again
 rows=r['comparisons'];assert len(rows)==2
 assert [r['statistic'] for r in rows]==pytest.approx([.90874545,-.05007117],abs=1e-7)
 assert [r['p_adjusted'] for r in rows]==pytest.approx([.58325114,.99819341],abs=5e-4)
 assert all(r['rng_seed']==0 and r['adjustment_method']=='dunnett' for r in rows)
 assert all(r['scipy_version'] and any('数值积分' in w for w in r['warnings']) for r in rows)

def test_games_howell_control_display_keeps_full_pairwise_family():
 values=units(dict(A=[1,2,4],B=[2,4,8,9],C=[3,7,15]))
 all_rows=compare_multigroup(values,{**spec(),'method':'welch_anova'})['comparisons']
 control=compare_multigroup(values,{**spec(),'method':'welch_anova','scope':'control'})['comparisons']
 assert len(control)==2
 for row in control:
  other=next(r for r in all_rows if (r['group_a'],r['group_b'])==(row['group_a'],row['group_b']))
  assert row['p_adjusted']==other['p_adjusted'] and row['ci95']==other['ci95']
  assert row['family_scope']=='all_pairs' and row['adjustment_method']=='games_howell'

def test_log2_contrast_and_interval_retransform_consistently():
 values=units(dict(A=[1,2,4],B=[2,4,8],C=[4,8,16]))
 row=compare_multigroup(values,{**spec(),'scale':'log2'})['comparisons'][0]
 assert row['effect']==pytest.approx(1) and row['effect_ratio']==pytest.approx(2)
 assert row['ratio_ci95']==pytest.approx([2**v for v in row['ci95']])

@pytest.mark.parametrize('case',['missing','singleton','duplicate','shared','membrane','nan','control','log_nonpositive','zero_variance','bad_groups'])
def test_unsupported_inputs_block_without_silent_exclusions(case):
 values=units(dict(A=[1,2,3],B=[2,3,4],C=[4,5,6]));s=spec()
 if case=='missing':values=[r for r in values if r['group']!='C']
 if case=='singleton':values=[r for r in values if r['group']!='C']+[values[-1]]
 if case=='duplicate':values.append(copy.deepcopy(values[0]))
 if case=='shared':values[3]['bio_id']=values[0]['bio_id']
 if case=='membrane':values[1]['membrane_id']='M2'
 if case=='nan':values[0]['value']=float('nan')
 if case=='control':s.update(scope='control',control_group='not-a-group')
 if case=='log_nonpositive':s['scale']='log2';values[0]['value']=0
 if case=='zero_variance':s['method']='welch_anova';values[0]['value']=values[1]['value']=values[2]['value']=1
 if case=='bad_groups':s['groups']=['A','A','C']
 with pytest.raises(ValueError):compare_multigroup(values,s)

def test_multigroup_does_not_run_before_explicit_design_confirmation(tmp_path):
 from test_lane_results import fixture
 from titan_wb.analysis import analyze
 p=fixture(tmp_path);p['settings']['multigroup_comparisons']=[{**spec(),'analyte':'AKT'}]
 r=analyze(p)
 assert r['multigroup_omnibus'][0]['status']=='blocked' and r['multigroup_comparisons']==[]
 assert r['statistics']==[]

def test_duplicate_comparison_ids_cannot_ambiguously_identify_annotations():
 from titan_wb.models import new_project,validate_project
 p=new_project('ambiguous');p['settings']['multigroup_comparisons']=[spec(),spec()]
 with pytest.raises(ValueError,match='比较ID'):validate_project(p)

@pytest.mark.parametrize('method',['anova','welch_anova'])
def test_last_group_as_control_keeps_B_minus_A_and_family(method):
 values=units(dict(A=[1,2,3],B=[2,3,4],C=[4,5,6]))
 result=compare_multigroup(values,{**spec(),'method':method,'scope':'control','control_group':'C'})
 assert [(r['group_a'],r['group_b']) for r in result['comparisons']]==[('C','A'),('C','B')]
 assert [r['effect'] for r in result['comparisons']]==pytest.approx([-3,-2])
 assert all(r['ci95'][0]<r['effect']<r['ci95'][1] for r in result['comparisons'])

def test_new_multigroup_pvalues_bypass_existing_Holm_family(monkeypatch):
 from titan_wb.models import new_project
 from titan_wb.analysis import analyze
 from titan_wb.statistics import compare,holm
 import titan_wb.normalization
 values=units(dict(A=[1,2,3],B=[2,3,4],C=[4,5,6]))
 monkeypatch.setattr(titan_wb.normalization,'normalize',lambda *args,**kwargs:([],values))
 p=new_project('family');p['settings'].update(design_confirmed=True,multigroup_comparisons=[spec()])
 p['settings']['comparisons']=[dict(id=f'old-{g}',family_id='legacy',group_a='A',group_b=g,test='welch',scale='raw') for g in ['B','C']]
 result=analyze(p)
 assert [r['p_adjusted'] for r in result['statistics']]==holm([compare(values,s)['p_raw'] for s in p['settings']['comparisons']])
 assert result['multigroup_comparisons']==compare_multigroup(values,spec())['comparisons']
