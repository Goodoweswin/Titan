import copy,json,shutil,tempfile
from pathlib import Path
from titan_wb.library import (
    copy_registered_analysis, create_managed_analysis, entry_for_path, library_list,
    open_registered_analysis, register_published_export,
)
from titan_wb.projects import release_project
from . import store
from .models import new_project,new_dataset,uid,signature,validate
from .analysis import analyze
from .render import render
from .importers import import_table

def create(name, session, tables=None, *, collection_id=None, new_collection_name=None):
    p = new_project(name)
    if tables:
        p['datasets'] = tables
    return create_managed_analysis(
        p, '.titanstats', store.save, session,
        collection_id=collection_id, new_collection_name=new_collection_name,
    )['project']


def export(d,style,run,destination):
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image
    from .models import prepared
    dest=Path(destination).expanduser().resolve()
    if dest.exists():raise ValueError('导出目录已存在，请选择新目录')
    if d['analysis']['method']!='descriptive' and (not run or run['signature']!=signature(d)):raise ValueError('分析结果已过期，请重新运行再导出')
    dest.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.stats-export-',dir=dest.parent))
    try:
        preview=render(d,style,run,stage);book=Workbook();ws=book.active;ws.title='数据'
        ws.append(['独立单位或配对ID',*[g['label'] for g in d['groups']]])
        for r in d['rows']:ws.append([r['label'],*[None if r['values'].get(g['id']) in [None,''] else float(r['values'][g['id']]) for g in d['groups']]])
        status=book.create_sheet('纳入状态');status.append(['ID','组','排除'])
        for r in d['rows']:
            for g in d['groups']:status.append([r['label'],g['label'],bool(r.get('excluded',{}).get(g['id']))])
        from titan_wb.export import csv_file
        vals,_,_=prepared(d);csv_file(stage/'observations.csv',vals)
        if run:
            for key in ['summaries','comparisons']:
                rows=run[key];sheet=book.create_sheet(key);headers=list(dict.fromkeys(k for r in rows for k in r));sheet.append(headers)
                for row in rows:sheet.append([json.dumps(row.get(k),ensure_ascii=False) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in headers])
            if run['omnibus']:
                sheet=book.create_sheet('总体检验')
                for k,v in run['omnibus'].items():sheet.append([k,json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v])
        sheet=book.create_sheet('图形');sheet.add_image(Image(stage/'plot.png'),'A1')
        sheet=book.create_sheet('方法与图注');sheet.append([preview['caption']]);sheet.append(['；'.join(preview['notes'])])
        # Imported strings are literal text, never executable Excel formulas.
        for sheet in book:
            for row in sheet:
                for cell in row:
                    if cell.data_type=='f':cell.data_type='s'
        book.save(stage/'results.xlsx')
        (stage/'analysis.json').write_text(json.dumps(dict(dataset=d,style=style,run=run,caption=preview['caption'],notes=preview['notes']),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        (stage/'methods.txt').write_text((run['method_text']+'\n' if run else '')+preview['caption']+'\n'+'；'.join(preview['notes']),encoding='utf-8')
        stage.rename(dest)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return dict(path=str(dest),files=[p.name for p in dest.iterdir()])

def same_wb_source(source, wb, entry):
    if not source or source.get('kind') != 'wb' or source.get('project_id') != wb['id']:
        return False
    if source.get('entry_id'):
        return entry is not None and source['entry_id'] == entry['entry_id']
    return source.get('path') == wb.get('project_path')


def dispatch(command,payload,session):
    if command=='stats_new':
        return create(payload.get('name','未命名统计项目'), session,
                      collection_id=payload.get('collection_id'), new_collection_name=payload.get('new_collection_name'))
    if command=='stats_demo':
        d=import_table(text='Control\tTreatment A\tTreatment B\n1\t2\t4\n2\t3\t5\n3\t4\t6')['dataset'];d['name']='合成示例 · 非实验数据';d['confirmed']=True;d['analysis']['method']='anova';d['analysis']['scope']='all'
        return create('统计合成示例',session,[d])
    if command=='stats_open':
        return open_registered_analysis(payload['path'], store.load, session, payload.get('entry_id'))
    if command=='stats_save':
        p = payload['project']
        current = p['project_path']
        path = payload.get('path') or current
        if Path(path).expanduser().resolve() != Path(current).resolve():
            return copy_registered_analysis(p, path, '.titanstats', store.save, session)
        # The manifest owns the title and saved revision. Autosave never needs the index.
        return store.save(p, current, p.get('saved_revision'), session)
    if command=='stats_release':release_project(payload['path'],session);return True
    if command=='stats_import':return import_table(payload.get('text'),payload.get('path'),payload.get('sheet'),payload.get('format','wide'))
    if command=='stats_dataset':return new_dataset(payload.get('name','新数据表'))
    if command=='stats_analyze':return analyze(payload['dataset'])
    if command=='stats_preview':return render(payload['dataset'],payload['style'],payload.get('run'))
    if command=='stats_export':
        project, destination = payload.get('project'), payload['destination']
        dataset, style, run = payload['dataset'], payload['style'], payload.get('run')
        figure = version = None
        revision = project['revision'] if project else None
        if payload.get('figure_id') or payload.get('run_id'):
            if not project or (payload.get('figure_id') and payload.get('run_id')):
                raise ValueError('导出的统计版本无效')
            if payload.get('figure_id'):
                figure = next((f for f in project.get('figures', []) if f['id'] == payload['figure_id']), None)
                if figure is None:
                    raise ValueError('找不到要导出的冻结统计图')
                dataset, style, run = figure['dataset'], figure['style'], figure['run']
                version, revision = figure['id'], figure.get('source_revision')
            else:
                run = next((r for d in project['datasets'] for r in d['runs'] if r['id'] == payload['run_id']), None)
                if run is None:
                    raise ValueError('找不到要导出的历史分析')
                dataset, style = run['dataset'], run['dataset']['style']
                version, revision = run['id'], run.get('source_revision')
        result = export(dataset, style, run, destination)
        if project:
            return register_published_export(
                project, result, destination, 'result_export', (figure or dataset)['name']+' · 统计结果',
                revision, session, version_id=version,
            )
        return result
    if command=='stats_from_wb':
        from titan_wb.stats_adapter import datasets
        from titan_wb.analysis import analyze as wb_analyze
        p = payload['project']
        source = entry_for_path(p.get('project_path'), session)
        if source and (source['project_id'] != p['id'] or source.get('module', 'wb') != 'wb'):
            raise ValueError('WB 来源分析身份不匹配')
        if not payload.get('as_copy') and p.get('project_path'):
            for entry in library_list(session):
                if entry.get('module') != 'stats' or not entry.get('available'):
                    continue
                try:
                    saved = validate(json.loads((Path(entry['path'])/'project.json').read_text(encoding='utf-8')))
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                if any(same_wb_source(t.get('source'), p, source) for t in saved['datasets']):
                    return open_registered_analysis(entry['path'], store.load, session, entry['entry_id'])
        tables = datasets(p, wb_analyze(p))
        if source:
            for table in tables:
                table['source']['entry_id'] = source['entry_id']
        return create(p['name']+' · 统计', session, tables, collection_id=source and source.get('collection_id'))
    if command in ('stats_source_catalog', 'stats_from_source', 'stats_source_status', 'stats_resolve_source', 'stats_update_source'):
        from . import sources
        if command == 'stats_source_catalog':
            return sources.catalog(payload['path'], session)
        if command == 'stats_from_source':
            return sources.transfer(payload, session)
        if command == 'stats_source_status':
            return sources.status(payload['source'], session)
        if command == 'stats_resolve_source':
            return sources.resolve(payload.get('source'), session)
        return sources.update(payload, session)
    raise ValueError('不支持的统计命令')
