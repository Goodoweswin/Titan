import copy,json,shutil,tempfile
from pathlib import Path
from titan_wb.library import (
    create_managed_analysis, entry_for_path, library_list, library_register,
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
        p=payload['project'];path=payload.get('path') or p['project_path'];expected=p.get('saved_revision') if path==p.get('project_path') else None
        source = entry_for_path(p.get('project_path'), session) if path != p.get('project_path') else None
        p = store.save(p, path, expected, session)
        library_register(p['project_path'], session, source_entry_id=source and source['entry_id'], touch_opened=source is not None)
        return p
    if command=='stats_release':release_project(payload['path'],session);return True
    if command=='stats_import':return import_table(payload.get('text'),payload.get('path'),payload.get('sheet'),payload.get('format','wide'))
    if command=='stats_dataset':return new_dataset(payload.get('name','新数据表'))
    if command=='stats_analyze':return analyze(payload['dataset'])
    if command=='stats_preview':return render(payload['dataset'],payload['style'],payload.get('run'))
    if command=='stats_export':
        project, destination = payload.get('project'), payload['destination']
        dataset, style, run = payload['dataset'], payload['style'], payload.get('run')
        figure = None
        if project and payload.get('figure_id'):
            figure = next((item for item in project['figures'] if item['id'] == payload['figure_id']), None)
            if figure is None:
                raise ValueError('找不到要导出的冻结统计图')
            dataset, style, run = figure['dataset'], figure['style'], figure['run']
        result = export(dataset, style, run, destination)
        if project:
            return register_published_export(
                project, result, destination, 'result_export', (figure or dataset)['name']+' · 统计结果',
                figure.get('source_revision') if figure else project['revision'], session,
                version_id=figure['id'] if figure else None,
            )
        return result
    if command=='stats_from_wb':
        from titan_wb.stats_adapter import datasets
        from titan_wb.analysis import analyze as wb_analyze
        p=payload['project']
        if not payload.get('as_copy') and p.get('project_path'):
            for entry in library_list(session):
                if entry.get('module')!='stats' or not entry.get('available'):continue
                saved=json.loads((Path(entry['path'])/'project.json').read_text(encoding='utf-8'))
                if any(t.get('source') and t['source'].get('kind')=='wb' and t['source'].get('path')==p['project_path'] and t['source'].get('project_id')==p['id'] for t in saved['datasets']):
                    return store.load(entry['path'],session)
        tables=datasets(p,wb_analyze(p))
        source = entry_for_path(p.get('project_path'), session)
        return create(p['name']+' · 统计', session, tables, collection_id=source and source.get('collection_id'))
    if command=='stats_update_source':
        from titan_wb.projects import open_project
        from titan_wb.analysis import analyze as wb_analyze
        from titan_wb.stats_adapter import datasets
        p=payload['project'];d=next(d for d in p['datasets'] if d['id']==payload['dataset_id']);source=d['source']
        wb=open_project(source['path'],session,read_only=True);fresh=next((t for t in datasets(wb,wb_analyze(wb)) if t['source']['endpoint']==source['endpoint'] and t['source']['block']==source['block']),None)
        if not fresh:raise ValueError('当前来源中已不存在该终点/分析块')
        # Explicitly reset analysis configuration when group identities change.
        fresh.update(id=d['id'],name=d['name'],runs=d['runs'],style={**d['style'],'colors':{}});p=copy.deepcopy(p);p['datasets']=[fresh if t['id']==d['id'] else t for t in p['datasets']];p['revision']+=1
        return store.save(p,p['project_path'],p['saved_revision'],{**session,'stats_source_update':True})
    raise ValueError('不支持的统计命令')
