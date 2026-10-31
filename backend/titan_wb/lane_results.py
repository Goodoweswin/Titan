def lane_result_rows(project,measurements,normalized):
    layouts={l['id']:l for l in project['lane_layouts']};sets={g['id']:g for g in project['band_sets']}
    lanes={l['id']:l for l in project['lanes']};measures={r['id']:r for r in measurements};ratios={r['id']:r for r in normalized}
    samples={s['id']:s for s in project['samples']};rows=[]
    for group in project['band_sets']:
        if group['role']!='target':continue
        layout=layouts[group['layout_id']];ref=sets.get(group.get('reference_set_id'))
        for assignment in group['assignments']:
            lane=lanes[assignment['lane_id']];target=measures.get(assignment.get('roi_id'));ratio=ratios.get(assignment.get('roi_id'))
            reference=next((a for a in ref['assignments'] if a['lane_id']==lane['id']),None) if ref else None
            reference_measure=measures.get(reference.get('roi_id')) if reference else None
            status=assignment['status']
            if status=='accepted':status='valid' if ratio and ratio['normalized'] is not None else 'blocked'
            rows.append(dict(membrane_id=layout['membrane_id'],lane_id=lane['id'],sample_id=lane['sample_id'],sample_name=samples[lane['sample_id']].get('name') or lane['sample_id'],analyte=group['analyte'],band_set_id=group['id'],
                corrected_sum=target.get('corrected_sum') if target else None,reference_analyte=ref['analyte'] if ref else None,
                reference_net=reference_measure.get('corrected_sum') if reference_measure else None,normalized=ratio['normalized'] if ratio else None,status=status,
                flags=ratio['flags'] if ratio else ['target_not_detected' if status=='not_detected' else 'review_required'],
                target_roi_id=assignment.get('roi_id'),reference_roi_id=reference.get('roi_id') if reference else None))
    return rows
