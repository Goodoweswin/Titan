"""Read-only WB/IF result adapters and explicit, version-checked transfers."""
import copy
import hashlib
import json
import math
from pathlib import Path

from titan_wb.library import entry_for_path, resolve_analysis_source

from .models import new_dataset, prepared, uid

IF_METRICS = {
    'mean': ('原始平均强度', 'a.u.', 1),
    'corrected_sum': ('扣背景总强度', 'a.u. × px', 1),
    'positive_area_fraction': ('阳性面积比例', '%', 100),
    'positive_fraction': ('核阳性率', '%', 100),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def selector(source):
    return source.get('selector') or {k: source[k] for k in ('endpoint', 'block')}


def source_key(source):
    return json.dumps(selector(source), sort_keys=True, ensure_ascii=False)


def load_source(path, session):
    root = Path(path).expanduser().resolve()
    before = (root / 'project.json').read_bytes()
    if root.suffix == '.titanwb':
        from titan_wb.projects import open_project
    elif root.suffix == '.titanif':
        from titan_if.projects import open_project
    else:
        raise ValueError('请选择已保存的 .titanwb 或 .titanif 项目目录')
    project = open_project(str(root), session, read_only=True)
    if before != (root / 'project.json').read_bytes():
        raise ValueError('来源在读取期间发生变化，请重新读取')
    return project, hashlib.sha256(before).hexdigest()


def wb_tables(project):
    from titan_wb.analysis import analyze
    from titan_wb.stats_adapter import datasets
    tables = datasets(project, analyze(project))
    for d in tables:
        d['source'].update(project_name=project['name'], selector=selector(d['source']),
                           unit='Target / reference ratio', notes=['按已确认的生物学单位汇总技术重复；跨膜限制继续保留。'])
    return tables


def if_tables(project, *, legacy_signature=False):
    from titan_if.analysis import aggregate_results
    from titan_if.models import analysis_signature, json_safe_integers
    # A batch/marker is the smallest supported comparable family. Never pool batches.
    families = {}
    views_by_sample = {}
    for f in project['fields']:
        if not f.get('quantitative', True):
            continue
        sample = (f.get('batch_id', ''), f.get('bio_id', ''), f.get('group', ''))
        views_by_sample.setdefault(sample, []).append(f)
        targets = f.get('recipe', {}).get('target_channel_ids', [])
        for channel in f['channels']:
            if channel['id'] in targets:
                families.setdefault((f.get('batch_id', ''), channel['name']), []).append(f)
    tables = []
    for (batch, channel), fields in sorted(families.items()):
        issue = ''
        if not str(batch).strip() or any(not str(f.get(k, '')).strip() for f in fields for k in ('bio_id', 'group')):
            issue = '请先在 IF 中补全生物学样本编号、分组和采集批次'
        samples = []
        try:
            if any(f.get('result') and f['recipe']['mode'] == 'nuclei' and
                   (not f.get('mask') or not f['mask'].get('confirmed')) for f in fields):
                raise ValueError('核模式结果需要已确认的分割')
            pooled = aggregate_results({'fields': fields}, channel_name=channel)
            samples = [r for r in pooled['samples'] if r['channel_name'] == channel]
        except (ValueError, OSError, KeyError) as e:
            issue = 'IF 结果不可用，请返回复核或重新测量：' + str(e)
        grouped = {}
        for f in fields:
            key = (f.get('bio_id', ''), f.get('group', ''))
            grouped[key] = views_by_sample[(batch, *key)]
        lookup = {(r['bio_id'], r['group']): r for r in samples}
        expected_fields = [f for members in grouped.values() for f in members]
        use_legacy = legacy_signature and len(expected_fields) == len(fields)
        fingerprint = []
        for f in fields if use_legacy else sorted(expected_fields, key=lambda f: f['id']):
            result = f.get('result')
            artifact = result.get('artifact') if result else None
            if artifact and not use_legacy:
                result = {'artifact_sha256': artifact['sha256']}
            fingerprint.append(dict(id=f['id'], inputs=analysis_signature(f),
                                    metadata={k: f.get(k) for k in ('bio_id', 'group', 'batch_id', 'sample_id')},
                                    result=result))
        sig = digest(fingerprint)
        selected_ids = {f['id'] for f in fields}
        for metric, (label, unit, factor) in IF_METRICS.items():
            d = new_dataset(f'{channel} · {label} · {batch or "未填写批次"}')
            names = list(dict.fromkeys(f.get('group', '') or '未填写分组' for f in fields))
            d['groups'] = [dict(id=uid(), label=g) for g in names]
            group_ids = {g['label']: g['id'] for g in d['groups']}
            d['analysis']['control_group'] = d['groups'][0]['id']
            rows, records = {}, []
            for (bio, group), members in grouped.items():
                pooled = lookup.get((bio, group))
                reason = ''
                if any(f['id'] not in selected_ids for f in members):
                    reason = '该样本有视野未选择对应通道，未使用部分视野代替完整样本'
                elif any(not f.get('result') or f.get('error') for f in members):
                    reason = '该样本有未测量或失败视野，未使用部分视野代替完整样本'
                elif any(len([r for r in f['result'].get('summary', [])
                              if r['channel_id'] in {c['id'] for c in f['channels'] if c['name'] == channel}]) != 1
                         for f in members):
                    reason = '该样本有视野缺少对应通道结果，未使用部分视野代替完整样本'
                value = pooled.get(metric) if pooled else None
                if metric == 'positive_fraction' and any(f['recipe']['mode'] != 'nuclei' for f in members):
                    value = None
                    reason = '核阳性率需要核模式、已确认分割和阳性阈值'
                if value is None and not reason:
                    reason = '指标缺失或分母为零，请检查背景、阈值和测量结果'
                if issue:
                    value, reason = None, issue
                if reason:
                    value = None
                elif not isinstance(value, (int, float)) or not math.isfinite(value):
                    value, reason = None, '指标不是有限数值'
                if value is not None:
                    value *= factor
                gid = group_ids[group or '未填写分组']
                row = rows.setdefault(bio, dict(id=uid(), label=bio or '缺失样本编号', values={}, units={}, excluded={}))
                row['values'][gid] = '' if value is None else str(value)
                row['units'][gid] = bio
                records.append(json_safe_integers(dict(
                    bio_id=bio, group=group, batch_id=batch, channel=channel, metric=metric,
                    value=value, missing_reason=reason, field_ids=[f['id'] for f in members],
                    field_count=len(members), pooled=pooled,
                )))
            d['rows'] = list(rows.values())
            d['confirmed'] = False  # The transfer dialog must explicitly confirm the experimental unit.
            d['style']['y_label'] = f'{channel} · {label} ({unit})'
            notes = ['每格代表一个生物学样本；多个视野合并总量与分母，不平均视野百分比。',
                     '不同采集批次分表；只有相同生物学样本编号才跨组对齐，不按行序推断配对。']
            if factor == 100:
                notes.append('比例已乘以 100，数值单位为 %。')
            d['source'] = dict(kind='if', path=project['project_path'], project_id=project['id'],
                               project_name=project['name'], revision=project['revision'], signature=sig,
                               signature_version=1 if use_legacy else 2,
                               endpoint=f'{channel} · {label}', block=batch, unit=unit,
                               selector=dict(channel=channel, batch=batch, metric=metric), locked=True,
                               blocked=issue, notes=notes, records=records)
            tables.append(d)
    return tables


def tables(project, *, legacy_if_signature=False):
    return if_tables(project, legacy_signature=legacy_if_signature) if project.get('module') == 'if' else wb_tables(project)


def describe(d):
    source = d['source']
    values, _, _ = prepared(d)
    records = source['records']
    missing = sum(r.get('value') is None for r in records)
    unavailable = not values or bool(source.get('blocked') and source['kind'] == 'if')
    return dict(key=source_key(source), label=d['name'], endpoint=source['endpoint'], block=source['block'],
                unit=source.get('unit', ''), n=len(values), missing=missing,
                groups=[dict(name=g['label'], n=sum(v['group'] == g['id'] for v in values)) for g in d['groups']],
                unavailable=unavailable, reason=source.get('blocked') or ('暂无有效样本值' if not values else ''),
                notes=source.get('notes', []),
                preview=[dict(bio_id=r['bio_id'], group=r['group'], value=r.get('value'),
                              missing_reason=r.get('missing_reason', '')) for r in records[:8]])


def registered_source(project, session):
    entry = entry_for_path(project['project_path'], session)
    if entry and (entry['project_id'] != project['id'] or entry.get('module', 'wb') != project.get('module', 'wb')):
        raise ValueError('来源分析身份不匹配，路径指向不同项目')
    return entry


def resolve(source, session):
    if not source or source.get('kind') not in ('wb', 'if'):
        raise ValueError('找不到 WB 或 IF 来源分析')
    return resolve_analysis_source(
        source.get('path'), source.get('entry_id'), source.get('project_id'), source['kind'], session,
    )


def same_analysis(left, right):
    if left.get('kind') != right.get('kind') or left.get('project_id') != right.get('project_id'):
        return False
    if left.get('entry_id') and right.get('entry_id'):
        return left['entry_id'] == right['entry_id']
    return left.get('path') == right.get('path')


def catalog(path, session):
    p, token = load_source(path, session)
    entry = registered_source(p, session)
    return dict(path=p['project_path'], project_id=p['id'], name=p['name'], kind=p.get('module', 'wb'),
                entry_id=entry and entry['entry_id'], revision=p['revision'], signature=token,
                choices=[describe(d) for d in tables(p)])


def transfer(payload, session):
    from .service import create
    from . import store
    if payload.get('confirmed') is not True:
        raise ValueError('请确认统计单位、分组及缺失样本后读取')
    p, token = load_source(payload['path'], session)
    if token != payload.get('expected_signature'):
        raise ValueError('来源已改变，请重新读取指标并确认')
    entry = registered_source(p, session)
    if payload.get('entry_id') and (not entry or payload['entry_id'] != entry['entry_id']):
        raise ValueError('来源分析登记已变化，请重新读取指标并确认')
    choices = {source_key(d['source']): d for d in tables(p)}
    keys = payload.get('keys', [])
    if not keys or len(set(keys)) != len(keys) or any(k not in choices for k in keys):
        raise ValueError('请选择有效且不重复的指标')
    selected = [choices[k] for k in keys]
    for d in selected:
        info = describe(d)
        if info['unavailable']:
            raise ValueError(info['reason'])
        d['confirmed'] = True
        if entry:
            d['source']['entry_id'] = entry['entry_id']
    if not payload.get('project'):
        return create(p['name'] + ' · 统计', session, selected, collection_id=payload.get('collection_id', entry and entry.get('collection_id')))
    target = copy.deepcopy(payload['project'])
    # Selecting an already linked endpoint never silently refreshes its snapshot.
    for d in selected:
        source = d['source']
        if not any(other.get('source') and same_analysis(other['source'], source)
                   and source_key(other['source']) == source_key(source) for other in target['datasets']):
            target['datasets'].append(d)
    target['revision'] += 1
    return store.save(target, target['project_path'], target['saved_revision'], session)


def current_table(source, session, *, compare_legacy=False):
    resolved = resolve(source, session)
    p, _ = load_source(resolved['path'], session)
    if p['id'] != resolved['project_id'] or p.get('module', 'wb') != source['kind']:
        raise ValueError('来源分析身份不匹配，路径指向不同项目')
    candidates = tables(p, legacy_if_signature=compare_legacy and not source.get('signature_version'))
    found = next((d for d in candidates if source_key(d['source']) == source_key(source)), None)
    if found is None:
        raise ValueError('来源中已不存在此指标或批次')
    if describe(found)['unavailable']:
        raise ValueError(describe(found)['reason'])
    if resolved['entry_id']:
        found['source']['entry_id'] = resolved['entry_id']
    return found


def status(source, session):
    try:
        fresh = current_table(source, session, compare_legacy=True)
        changed = fresh['source']['signature'] != source['signature']
        return dict(state='changed' if changed else 'current', revision=fresh['source']['revision'],
                    message='来源已变化；当前仍为已保存快照，更新后需重新分析。' if changed else '与已保存的来源结果一致。')
    except (OSError, ValueError, KeyError) as e:
        return dict(state='unavailable', message='来源暂不可读取，已保存快照仍可使用。' + str(e))


def update(payload, session):
    from . import store
    p = copy.deepcopy(payload['project'])
    old = next(d for d in p['datasets'] if d['id'] == payload['dataset_id'])
    fresh = current_table(old['source'], session)
    # Stable group identities preserve colors, names, and comparison settings.
    old_ids = {g['label']: g['id'] for g in old['groups']}
    remap = {g['id']: old_ids.get(g['label'], g['id']) for g in fresh['groups']}
    for g in fresh['groups']:
        g['id'] = remap[g['id']]
    for r in fresh['rows']:
        for key in ('values', 'units', 'excluded'):
            r[key] = {remap[k]: v for k, v in r.get(key, {}).items()}
    fresh.update(id=old['id'], name=old['name'], runs=old['runs'], style=copy.deepcopy(old['style']), confirmed=old['confirmed'])
    valid = {g['id'] for g in fresh['groups']}
    for key in ('colors', 'labels'):
        fresh['style'][key] = {k: v for k, v in fresh['style'].get(key, {}).items() if k in valid}
    if fresh['style'].get('group_order'):
        order = [k for k in fresh['style']['group_order'] if k in valid]
        fresh['style']['group_order'] = order + [g['id'] for g in fresh['groups'] if g['id'] not in order]
    if 'comparison_keys' in fresh['style']:
        fresh['style']['comparison_keys'] = [k for k in fresh['style']['comparison_keys'] if all(g in valid for g in k.split(':'))]
    fresh['analysis'] = copy.deepcopy(old['analysis'])
    if fresh['analysis']['control_group'] not in {g['id'] for g in fresh['groups']}:
        fresh['analysis']['control_group'] = fresh['groups'][0]['id']
    if len(fresh['groups']) != len(old['groups']):
        fresh['analysis']['method'] = 'descriptive'
    p['datasets'] = [fresh if d['id'] == old['id'] else d for d in p['datasets']]
    p['revision'] += 1
    return store.save(p, p['project_path'], p['saved_revision'], {**session, 'stats_source_update': True})
