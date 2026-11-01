"""Human-readable Excel tables from the same immutable analysis snapshot."""
import json
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment,Font,PatternFill
from openpyxl.utils import get_column_letter
from . import __version__

STATUS={'valid':'已计算','accepted':'已确认','pending':'待确认','not_detected':'未检出','excluded':'已排除','blocked':'需处理'}


def table(book,name,columns,rows):
    ws=book.create_sheet(name);ws.append([title for key,title in columns])
    for row in rows:
        values=[]
        for key,title in columns:
            value=row.get(key)
            values.append(json.dumps(value,ensure_ascii=False) if isinstance(value,(list,dict)) else value)
        ws.append(values)
    for row in ws:
        for cell in row:
            if isinstance(cell.value,str):cell.data_type='s'
            elif isinstance(cell.value,(float,int)) and not isinstance(cell.value,bool):
                cell.number_format='0.000000E+00' if cell.value!=0 and (abs(cell.value)<1e-4 or abs(cell.value)>=1e10) else '0.######'
            cell.alignment=Alignment(vertical='top',wrap_text=True)
    for cell in ws[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='315D9B')
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    ws.sheet_view.showGridLines=False
    for index,(key,title) in enumerate(columns,1):ws.column_dimensions[get_column_letter(index)].width=42 if key in ('flags','backgrounds','sha256','value') else max(15,min(26,len(title)*2+4))
    return ws


def group_rows(data):
    return [dict(analyte=p['analyte'],analysis_block=p['analysis_block'],unit=data['unit'],value_mode=data['value_mode'],**g,ci_low=(g['ci95'] or [None,None])[0],ci_high=(g['ci95'] or [None,None])[1]) for p in data['panels'] for g in p['groups']]


def write_workbook(project,result,root,figure_data):
    book=Workbook();book.remove(book.active)
    book.properties.creator='Titan WB';book.properties.title=project['name']
    table(book,'说明',[('key','项目'),('value','内容')],[
        dict(key='实验名称',value=project['name']),dict(key='软件版本',value=__version__),
        dict(key='项目ID',value=project['id']),dict(key='输入版本',value=result['input_revision']),
        dict(key='净积分',value='确认区域内的方向校正积分 − 面积 × 局部背景并集均值；计算使用原始像素，不使用预览亮度。'),
        dict(key='目标/内参',value='明确关联的同膜同泳道目标净积分 / 内参净积分；空白表示未检出、未确认或不满足计算条件，不能当作 0。'),
        dict(key='汇总与统计',value='逐泳道结果不代表独立生物学 n；生物学汇总、分组和统计按确认的实验设计生成。空表表示没有当前可用记录。'),
        dict(key='可视化',value='图表工作表嵌入与 plot.png 相同的图像；PNG 与 SVG 另存。图例 ND=未检出，NA=不可计算。'),
        dict(key='完整追溯',value='坐标为原图像素，页码从 1 起。CSV/JSON、原图与标注、设置和 SHA256 审计同时导出。'),
        dict(key='计算设置',value=project['settings']),dict(key='分析源签名',value=result.get('source_signature')),
        dict(key='图形设置',value=project.get('figure_settings')),dict(key='图形尺寸',value=project.get('plot_settings')),
        dict(key='图形单位与误差',value={'unit':figure_data['unit'],'value_mode':figure_data['value_mode'],'error':figure_data['error'],'notes':figure_data['notes']}),
        dict(key='多组检验',value='独立单因素设计。普通ANOVA后Dunnett对照或Tukey全两两；Welch后Games–Howell，显示对照组对时仍使用全两两家族。每个比较设置/蛋白/分析膜单独校正，不自动跨蛋白。'),
        dict(key='区间与p',value='分组描述的CI为每组均值t区间；多重比较CI为同时95%区间；旧两组CI为未作多重校正的边际区间，p按显式Holm家族校正。p=0表示计算数值分辨率下溢，不能解释为概率精确为零。'),
        dict(key='图形提示',value=[w for panel in figure_data['panels'] for w in panel['warnings']])])
    common=[('membrane_id','膜'),('lane_id','泳道'),('sample_id','样本ID'),('sample_name','样本名称'),('analyte','蛋白')]
    lanes={l['id']:l for l in project['lanes']};samples={s['id']:s for s in project['samples']};images={a['id']:a for a in project['images']};measurements={m['id']:m for m in result['measurements']}
    def identity(lane_id):
        lane=lanes[lane_id];sample=samples[lane['sample_id']]
        return dict(membrane_id=lane['membrane_id'],sample_id=sample['id'],sample_name=sample.get('name') or sample['id'])
    lane_rows=[{**r,**identity(r['lane_id']), 'status':STATUS.get(r['status'],r['status'])} for r in result.get('lane_results',[])]
    table(book,'泳道结果',common+[('corrected_sum','目标净积分'),('reference_analyte','内参蛋白'),('reference_net','内参净积分'),('normalized','目标/内参'),('status','状态'),('flags','质量标记'),('target_roi_id','目标条带ID'),('reference_roi_id','内参条带ID'),('band_set_id','测量集合ID')],lane_rows)
    raw=[{**r,**identity(r['lane_id']), 'source':images[r['image_id']]['name'],'page':images[r['image_id']].get('page_index',0)+1} for r in result['measurements']]
    table(book,'原始测量',common+[('role','角色'),('area_px','面积 px²'),('raw_sum','原始积分'),('background_mean','背景均值'),('corrected_sum','净积分'),('clipped_fraction','饱和比例'),('image_id','图像ID'),('source','原图'),('page','页码'),('rect','峰区坐标'),('backgrounds','背景坐标'),('id','条带ID'),('reference_id','内参条带ID'),('reviewed_revision','复核版本'),('flags','质量标记')],raw)
    normalized=[]
    for row in result['normalized']:
        target=measurements[row['id']];reference=measurements.get(target.get('reference_id'))
        normalized.append({**row,**identity(target['lane_id']),'lane_id':target['lane_id'],'reference_id':target.get('reference_id'),'reference_analyte':reference.get('analyte') if reference else None,'reference_net':reference.get('corrected_sum') if reference else None})
    table(book,'参考归一化',common+[('normalized','目标/内参'),('bridged','IBC桥接值'),('reference_analyte','内参蛋白'),('reference_net','内参净积分'),('id','目标条带ID'),('reference_id','内参条带ID'),('bio_id','生物学ID'),('group','组别'),('flags','质量标记')],normalized)
    table(book,'生物学汇总',[('analysis_block','分析块'),('sample_id','样本ID'),('bio_id','生物学ID'),('group','组别'),('analyte','蛋白'),('value','归一化均值'),('fold','相对对照'),('n_technical','技术泳道数'),('flags','质量标记')],result['biological'])
    table(book,'统计结果',[('analyte','蛋白'),('comparison_id','比较ID'),('family_id','多重比较家族'),('test','检验'),('scale','尺度'),('n_a','A组 n'),('n_b','B组 n'),('effect','效应 B−A'),('ci95','95% CI'),('p_raw','原始 p'),('p_adjusted','Holm p'),('warnings','提示')],result['statistics'])
    table(book,'分组描述',[('analyte','蛋白'),('analysis_block','分析块'),('key','组别'),('label','显示名称'),('unit','单位'),('value_mode','数值模式'),('n','n'),('mean','均值'),('sd','SD'),('sem','SEM'),('ci_low','均值95% CI下界'),('ci_high','均值95% CI上界'),('color','颜色'),('status','状态')],group_rows(figure_data))
    table(book,'多组总体检验',[('analyte','蛋白'),('analysis_block','分析块'),('comparison_id','比较ID'),('family_id','多重比较家族'),('method','方法'),('scipy_version','SciPy版本'),('scale','尺度'),('groups','所选组'),('n_by_group','各组n'),('statistic','F'),('df_num','分子自由度'),('df_den','分母自由度'),('p_raw','总体 p'),('status','状态'),('warnings','提示')],result.get('multigroup_omnibus',[]))
    pairs=[dict(r,ci_low=(r.get('ci95') or [None,None])[0],ci_high=(r.get('ci95') or [None,None])[1],ratio_low=(r.get('ratio_ci95') or [None,None])[0],ratio_high=(r.get('ratio_ci95') or [None,None])[1]) for r in result.get('multigroup_comparisons',[])]
    table(book,'多重比较',[('analyte','蛋白'),('analysis_block','分析块'),('comparison_id','比较ID'),('family_id','多重比较家族'),('group_a','A组'),('group_b','B组'),('n_by_group','各组n'),('scale','尺度'),('effect','效应 B−A'),('ci_low','同时95% CI下界'),('ci_high','同时95% CI上界'),('ci_method','区间方法'),('p_adjusted','调整后 p'),('adjustment_method','校正方法'),('scipy_version','SciPy版本'),('family_scope','校正家族范围'),('display_scope','显示范围'),('effect_ratio','反变换比值'),('ratio_low','比值CI下界'),('ratio_high','比值CI上界'),('rng_seed','数值积分随机种子'),('warnings','提示')],pairs)
    table(book,'样本信息',[('membrane_id','膜'),('lane_id','泳道'),('sample_id','样本ID'),('sample_name','样本名称'),('bio_id','生物学ID'),('group','组别'),('pair_id','配对ID'),('kind','样本类型'),('technical_id','技术重复ID')],[{**samples[l['sample_id']],**l,'lane_id':l['id'],'sample_name':samples[l['sample_id']].get('name') or l['sample_id']} for l in project['lanes']])
    table(book,'图像来源',[('id','图像ID'),('name','原始文件'),('sha256','SHA256'),('page','页码'),('dtype','像素类型'),('width','宽 px'),('height','高 px'),('polarity','原始信号方向'),('ceiling','有效编码上界'),('display_inverted','显示反色'),('photometric','灰度显示编码'),('exposure','曝光记录'),('linear_validated','线性范围声明')],[{**a,'page':a.get('page_index',0)+1} for a in project['images']])
    chart=book.create_sheet('图表');chart['A1']='与 plot.png 相同的当前结果图；ND=未检出，NA=不可计算。'
    image=Image(root/'plot.png');scale=min(1,1000/image.width);image.width*=scale;image.height*=scale;chart.add_image(image,'A3');chart.sheet_view.showGridLines=False
    book.save(root/'results.xlsx');book.close()
