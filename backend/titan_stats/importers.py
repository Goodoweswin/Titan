import csv,io,hashlib
from pathlib import Path
from .models import new_dataset,uid

def import_table(text=None,path=None,sheet=None,format="wide"):
    sheets=[];source=None
    if path:
        file=Path(path)
        if file.stat().st_size>20*1024*1024:raise ValueError('导入文件不能超过20MB')
        source=dict(kind='file',path=str(file.resolve()),sha256=hashlib.sha256(file.read_bytes()).hexdigest())
        if file.suffix.lower()=='.xlsx':
            from openpyxl import load_workbook
            book=load_workbook(file,read_only=True,data_only=True);formulas=load_workbook(file,read_only=True,data_only=False)
            try:
                sheets=book.sheetnames;name=sheet or sheets[0];ws=book[name];fs=formulas[name]
                if ws.max_row>10001 or ws.max_column>31:raise ValueError('表格超出10000行/30组，请选择数据区域')
                matrix=list(ws.values)
                for i,row in enumerate(fs.values):
                    for j,v in enumerate(row):
                        if isinstance(v,str) and v.startswith('=') and matrix[i][j] is None:raise ValueError('公式没有缓存值，请在 Excel 中计算并保存或粘贴数值')
                source['sheet']=name
            finally:book.close();formulas.close()
        elif file.suffix.lower() in ['.csv','.tsv','.txt']:text=file.read_text(encoding='utf-8-sig')
        else:raise ValueError('支持 CSV、TSV、TXT 和 XLSX')
    if text is not None:
        delimiter='\t' if '\t' in text else ','
        matrix=list(csv.reader(io.StringIO(text.lstrip('\ufeff')),delimiter=delimiter))
    if not matrix or len(matrix)<2:raise ValueError('首行填写组名，后续行填写数值')
    headers=[str(v or '').strip() for v in matrix[0]]
    if format=='long':
        names={h.lower():i for i,h in enumerate(headers)}
        def column(*aliases):
            return next((names[a] for a in aliases if a in names),None)
        group_col=column('group','组别');value_col=column('value','数值');unit_col=column('unit_id','bio_id','id','样本id');pair_col=column('pair_id','配对id')
        if None in [group_col,value_col,unit_col]:raise ValueError('长表需要 group、value、unit_id 三列；配对可增加 pair_id')
        d=new_dataset(Path(path).stem if path else '导入数据');d['groups']=[];d['rows']=[];d['source']=source;groups={};rows={};units=set()
        for line in matrix[1:]:
            if all(v is None or str(v).strip()=='' for v in line):continue
            if len(line)!=len(headers):raise ValueError('长表列数必须与表头一致')
            group=str(line[group_col] or '').strip();unit=str(line[unit_col] or '').strip();pair=str(line[pair_col] or '').strip() if pair_col is not None else unit
            if not group or not unit or not pair:raise ValueError('组别、独立单位或配对 ID 不能为空')
            if (group,unit) in units:raise ValueError('同一独立单位在同组重复，请先明确汇总技术重复')
            units.add((group,unit))
            if group not in groups:groups[group]=uid();d['groups'].append(dict(id=groups[group],label=group))
            gid=groups[group]
            if pair not in rows:rows[pair]=dict(id=uid(),label=pair,values={},excluded={},units={})
            if gid in rows[pair]['values']:raise ValueError('同一配对 ID 在同组重复')
            rows[pair]['values'][gid]='' if line[value_col] is None else str(line[value_col]);rows[pair]['units'][gid]=unit
        d['rows']=list(rows.values())
        if not d['groups'] or len(d['groups'])>30 or len(d['rows'])>10000:raise ValueError('组数或行数超出限制')
        d['analysis']['control_group']=d['groups'][0]['id']
        from .models import prepared
        prepared(d)
        return dict(dataset=d,sheets=sheets)
    if format!='wide':raise ValueError('请选择宽表或长表')
    has_id=headers[0].lower() in ['id','sample','pair_id','样本','配对id','样本id']
    labels=headers[1:] if has_id else headers
    if not labels or any(not v for v in labels) or len(set(labels))!=len(labels) or len(labels)>30:raise ValueError('组名必须非空、不重复，最多30组')
    d=new_dataset(Path(path).stem if path else '导入数据');d['groups']=[dict(id=uid(),label=v) for v in labels];d['rows']=[];d['source']=source
    for i,row in enumerate(matrix[1:]):
        if all(v is None or str(v).strip()=='' for v in row):continue
        if len(row)>len(headers):raise ValueError(f'第{i+2}行列数超过表头')
        vals=row[1:] if has_id else row
        d['rows'].append(dict(id=uid(),label=str(row[0]) if has_id else str(i+1),values={g['id']:'' if j>=len(vals) or vals[j] is None else str(vals[j]) for j,g in enumerate(d['groups'])},excluded={}))
    if len(d['rows'])>10000:raise ValueError('最多10000行')
    d['analysis']['control_group']=d['groups'][0]['id']
    from .models import prepared
    prepared(d)
    return dict(dataset=d,sheets=sheets)
