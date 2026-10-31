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
            elif isinstance(cell.value,(float,int)) and not isinstance(cell.value,bool):cell.number_format='0.######'
            cell.alignment=Alignment(vertical='top',wrap_text=True)
    for cell in ws[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='315D9B')
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    ws.sheet_view.showGridLines=False
    for index,(key,title) in enumerate(columns,1):ws.column_dimensions[get_column_letter(index)].width=42 if key in ('flags','backgrounds','sha256','value') else max(15,min(26,len(title)*2+4))
    return ws


def write_workbook(project,result,root):
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
        dict(key='计算设置',value=project['settings'])])
    common=[('membrane_id','膜'),('lane_id','泳道'),('sample_id','样本ID'),('sample_name','样本名称'),('analyte','蛋白')]
    lanes={l['id']:l for l in project['lanes']};samples={s['id']:s for s in project['samples']};images={a['id']:a for a in project['images']};measurements={m['id']:m for m in result['measurements']}
    def identity(lane_id):
        lane=lanes[lane_id];sample=samples[lane['sample_id']]
        return dict(membrane_id=lane['membrane_id'],sample_id=sample['id'],sample_name=sample.get('name') or sample['id'])
    lane_rows=[{**r,**identity(r['lane_id']), 'status':STATUS.get(r['status'],r['status'])} for r in result.get('lane_results',[])]
    table(book,'泳道结果',common+[('corrected_sum','目标净积分'),('reference_analyte','内参蛋白'),('reference_net','内参净积分'),('normalized','目标/内参'),('status','状态'),('flags','质量标记'),('target_roi_id','目标条带ID'),('reference_roi_id','内参条带ID'),('band_set_id','测量集合ID')],lane_rows)
    raw=[{**r,**identity(r['lane_id']), 'source':images[r['image_id']]['name'],'page':images[r['image_id']].get('page_index',0)+1} for r in result['measurements']]
    table(book,'原始测量',common+[('role','角色'),('area_px','面积 px²'),('raw_sum','原始积分'),('background_mean','背景均值'),('corrected_sum','净积分'),('clipped_fraction','饱和比例'),('source','原图'),('page','页码'),('rect','峰区坐标'),('backgrounds','背景坐标'),('id','条带ID'),('reference_id','内参条带ID'),('reviewed_revision','复核版本'),('flags','质量标记')],raw)
    normalized=[]
    for row in result['normalized']:
        target=measurements[row['id']];reference=measurements.get(target.get('reference_id'))
        normalized.append({**row,**identity(target['lane_id']),'lane_id':target['lane_id'],'reference_id':target.get('reference_id'),'reference_analyte':reference.get('analyte') if reference else None,'reference_net':reference.get('corrected_sum') if reference else None})
    table(book,'参考归一化',common+[('normalized','目标/内参'),('bridged','IBC桥接值'),('reference_analyte','内参蛋白'),('reference_net','内参净积分'),('id','目标条带ID'),('reference_id','内参条带ID'),('bio_id','生物学ID'),('group','组别'),('flags','质量标记')],normalized)
    table(book,'生物学汇总',[('analysis_block','分析块'),('sample_id','样本ID'),('bio_id','生物学ID'),('group','组别'),('analyte','蛋白'),('value','归一化均值'),('fold','相对对照'),('n_technical','技术泳道数'),('flags','质量标记')],result['biological'])
    table(book,'统计结果',[('analyte','蛋白'),('comparison_id','比较ID'),('family_id','多重比较家族'),('test','检验'),('scale','尺度'),('n_a','A组 n'),('n_b','B组 n'),('effect','效应 B−A'),('ci95','95% CI'),('p_raw','原始 p'),('p_adjusted','Holm p'),('warnings','提示')],result['statistics'])
    table(book,'样本信息',[('membrane_id','膜'),('lane_id','泳道'),('sample_id','样本ID'),('sample_name','样本名称'),('bio_id','生物学ID'),('group','组别'),('pair_id','配对ID'),('kind','样本类型'),('technical_id','技术重复ID')],[{**samples[l['sample_id']],**l,'lane_id':l['id'],'sample_name':samples[l['sample_id']].get('name') or l['sample_id']} for l in project['lanes']])
    table(book,'图像来源',[('id','图像ID'),('name','原始文件'),('sha256','SHA256'),('page','页码'),('dtype','像素类型'),('width','宽 px'),('height','高 px'),('polarity','原始信号方向'),('ceiling','有效编码上界'),('display_inverted','显示反色'),('photometric','灰度显示编码'),('exposure','曝光记录'),('linear_validated','线性范围声明')],[{**a,'page':a.get('page_index',0)+1} for a in project['images']])
    chart=book.create_sheet('图表');chart['A1']='与 plot.png 相同的当前结果图；ND=未检出，NA=不可计算。'
    image=Image(root/'plot.png');scale=min(1,1000/image.width);image.width*=scale;image.height*=scale;chart.add_image(image,'A3');chart.sheet_view.showGridLines=False
    book.save(root/'results.xlsx');book.close()
