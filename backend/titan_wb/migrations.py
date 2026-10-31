import copy

def migrate_project(data):
    p=copy.deepcopy(data)
    if p.get('schema_version')==1:
        p.update(schema_version=2,lane_layouts=[],band_sets=[],revision=p['revision']+1)
        for r in p['rois']:r['reviewed_revision']=None
    for a in p.get('images',[]):a.setdefault('display_inverted',False)
    return p
