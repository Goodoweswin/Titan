from .models import validate_project
from .images import read_pixels
from .quantify import measure


def measure_project(project):
    validate_project(project)
    assets={a['id']:a for a in project['images']}
    pixels={k:read_pixels(a) for k,a in assets.items()}
    rows=[]
    for r in project['rois']:
        a=assets[r['image_id']]
        try:
            m=measure(pixels[a['id']],r['rect'],r['backgrounds'],polarity=a['polarity'],ceiling=a.get('ceiling'))
        except ValueError as e:
            m=dict(area_px=0,raw_sum=None,background_mean=None,corrected_sum=None,clipped_fraction=None,flags=['measurement_error:'+str(e)])
        if r.get('reviewed_revision')!=project['revision']:m['flags'].append('review_required')
        if not a.get('linear_validated'):m['flags'].append('linearity_not_validated')
        rows.append({**r,**m})
    return rows


def analyze(project):
    from .normalization import normalize
    measurements=measure_project(project)
    rows,bio=normalize(project,measurements)
    statistics=[]
    from .statistics import compare,holm
    for spec in project['settings'].get('comparisons',[]):
        if spec['test']=='descriptive':continue
        # Each endpoint is its own result; all preselected comparisons in a
        # named family are corrected together, including multiple endpoints.
        for analyte in sorted({b['analyte'] for b in bio}):
            try:r=compare([b for b in bio if b['analyte']==analyte],spec)
            except ValueError as e:
                r=dict(comparison_id=spec['id'],family_id=spec.get('family_id','default'),test=spec['test'],scale=spec['scale'],n_a=0,n_b=0,effect=None,statistic=None,df=None,p_raw=None,p_adjusted=None,ci95=None,warnings=[str(e)])
            r['analyte']=analyte;statistics.append(r)
    for family in {r['family_id'] for r in statistics}:
        valid=[r for r in statistics if r['family_id']==family and r['p_raw'] is not None]
        for r,p in zip(valid,holm([r['p_raw'] for r in valid])):r['p_adjusted']=p
    return dict(project_id=project['id'],input_revision=project['revision'],measurements=measurements,
                normalized=rows,biological=bio,statistics=statistics)
