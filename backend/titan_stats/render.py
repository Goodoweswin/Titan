"""One renderer for previews and PNG/SVG/PDF exports."""
import base64,io,math,re,copy,os,tempfile
from pathlib import Path
import numpy as np
from .models import prepared,signature
from .core import group_summary

PALETTE=['#88B8D0','#E29EB6','#D4B483','#879CA6','#BD998B','#A9B9BF']

def render(d,style,run=None,folder=None):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'titan-stats-mpl'))
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt,font_manager
    font=Path(__file__).parents[1]/'titan_wb/assets/NotoSansSC.ttf'
    if font.exists():font_manager.fontManager.addfont(str(font))
    original_signature=signature(d)
    d=copy.deepcopy(d)
    order=style.get('group_order',[]);known={g['id'] for g in d['groups']}
    if len(order)!=len(set(order)) or any(key not in known for key in order):raise ValueError('显示顺序包含未知组或重复组')
    d['groups'].sort(key=lambda g:order.index(g['id']) if g['id'] in order else len(order))
    vals,missing,excluded=prepared(d)
    def number(key,lo,hi):
        v=style.get(key)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError(f'{key} 必须在 {lo}–{hi} 之间')
        return v
    width=number('width_mm',30,300);height=number('height_mm',30,300);size=number('font_size',5,30);dpi=number('dpi',72,600)
    if width/25.4*height/25.4*dpi*dpi>24_000_000:raise ValueError('输出超过2400万像素，请减小尺寸或DPI')
    kind=style.get('kind');error=style.get('error');annotation=style.get('annotations')
    if kind not in ['bar_points','bar','scatter','paired'] or error not in ['sd','sem','ci95','none'] or annotation not in ['none','p','stars']:raise ValueError('图形设置无效')
    if style.get('text_mode') not in ['editable','outline']:raise ValueError('文字模式无效')
    for color in style.get('colors',{}).values():
        if not re.fullmatch('#[0-9a-fA-F]{6}',color):raise ValueError('颜色必须是六位 HEX')
    if annotation!='none' and (not run or run['signature']!=original_signature):raise ValueError('统计结果已过期，请先运行当前分析')
    if kind=='paired':
        pairs={}
        for v in vals:
            key=(v['pair_id'],v['group'])
            if key in pairs:raise ValueError('配对 ID 重复，不能生成配对图')
            pairs[key]=v['value']
        if any(sum((pid,g['id']) in pairs for g in d['groups'])!=len(d['groups']) for pid,_ in pairs):raise ValueError('存在不完整配对，请核对缺失及排除记录')
    point=style.get('point_size',4);marker=style.get('point_marker','circle');hollow=style.get('hollow',False)
    for key,default,lo,hi in [('point_size',4,1,14),('axis_width',.8,.2,4),('error_width',.8,.2,4),('error_cap',3,0,12),('bar_width',.6,.1,.95),('label_angle',30,-90,90)]:
        number_value=style.get(key,default)
        if isinstance(number_value,bool) or not isinstance(number_value,(int,float)) or not math.isfinite(number_value) or not lo<=number_value<=hi:raise ValueError(key+' 超出范围')
    if marker not in ['circle','square','triangle']:raise ValueError('点形无效')
    rc={'font.family':['DejaVu Sans','Noto Sans SC'],'font.size':size,'axes.unicode_minus':False,'svg.fonttype':'none' if style['text_mode']=='editable' else 'path','pdf.fonttype':42,'text.parse_math':False}
    with plt.rc_context(rc):
        fig,ax=plt.subplots(figsize=(width/25.4,height/25.4));limits=[0.0];notes=[]
        try:
            for i,g in enumerate(d['groups']):
                y=[v['value'] for v in vals if v['group']==g['id']];s=group_summary(y);color=style.get('colors',{}).get(g['id'],PALETTE[i%len(PALETTE)])
                if not y:ax.text(i,.04,'NA',transform=ax.get_xaxis_transform(),ha='center');continue
                limits+=y
                if kind in ['bar','bar_points']:ax.bar(i,s['mean'],style.get('bar_width',.6),color=color,edgecolor='#333',linewidth=.7)
                else:ax.hlines(s['mean'],i-.2,i+.2,color='#333',linewidth=1)
                if kind!='bar':
                    jitter=np.zeros(len(y)) if kind=='paired' else np.random.default_rng(i).uniform(-.09,.09,len(y))
                    ax.scatter(i+jitter,y,s=point**2,marker={'circle':'o','square':'s','triangle':'^'}[marker],facecolors='white' if hollow else color,edgecolors='#333',linewidths=.5,zorder=3)
                if len(y)>1 and error!='none':
                    lo,hi=s['ci95'] if error=='ci95' else (s['mean']-s[error],s['mean']+s[error])
                    limits.extend([lo,hi]);ax.errorbar(i,s['mean'],yerr=[[s['mean']-lo],[hi-s['mean']]],fmt='none',color='#333',capsize=style.get('error_cap',3),linewidth=style.get('error_width',.8))
            if kind=='paired':
                for pid in sorted({v['pair_id'] for v in vals}):ax.plot(range(len(d['groups'])),[pairs[(pid,g['id'])] for g in d['groups']],color='#929BA3',alpha=.6,linewidth=.7,zorder=0)
            ax.set_xticks(range(len(d['groups'])),[style.get('labels',{}).get(g['id']) or g['label'] for g in d['groups']],rotation=style.get('label_angle',30),ha='right')
            ax.set_ylabel(style.get('y_label','Value'));ax.set_title(style.get('title') or d['name'])
            ax.spines[['top','right']].set_visible(False)
            for spine in ax.spines.values():spine.set_linewidth(style.get('axis_width',.8))
            span=max(max(limits)-min(limits),1e-8);top=max(limits)
            comparisons=run['comparisons'] if run and annotation!='none' else []
            if style.get('comparison_keys') is not None:
                keys=style['comparison_keys'];available={row['group_a']+':'+row['group_b'] for row in comparisons}
                if annotation!='none' and any(key not in available for key in keys):raise ValueError('所选对比已改变，请重新选择标注')
                comparisons=[row for row in comparisons if row['group_a']+':'+row['group_b'] in keys]
            low=style.get('y_min');high=style.get('y_max')
            for v in [low,high]:
                if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)):raise ValueError('坐标轴范围无效')
            lower=low if low is not None else min(limits)-(.08*span if min(limits)<0 else 0)
            ax.set_ylim(lower,top+span*.2);fig.tight_layout(pad=1)
            axes_points=ax.get_position().height*height/25.4*72
            annotation_size=max(6,size*.85);step=annotation_size*1.8/axes_points
            headroom=(len(comparisons)*step+.06) if comparisons else .12
            if headroom>.8:raise ValueError('比较标注过多，请增加图形高度或减少显示的组对')
            upper=high if high is not None else lower+(top-lower+span*.03)/(1-headroom)
            if lower>=upper:raise ValueError('Y轴上限必须大于下限')
            if min(limits)<lower or max(limits)>upper or (comparisons and top+(upper-lower)*headroom>upper):notes.append('自定义范围截断了数据、误差线或比较标注')
            if kind in ['bar','bar_points'] and lower>0:notes.append('Y轴截断柱形零基线')
            ax.set_ylim(lower,upper)
            for j,row in enumerate(comparisons):
                ids=[g['id'] for g in d['groups']];a=ids.index(row['group_a']);b=ids.index(row['group_b']);y=top+(upper-lower)*(.025+step*j);cap=(upper-lower)*.012
                p=row['p_adjusted'];label=f'p={p:.3g}' if annotation=='p' else ('****' if p<.0001 else '***' if p<.001 else '**' if p<.01 else '*' if p<.05 else 'ns')
                ax.plot([a,a,b,b],[y,y+cap,y+cap,y],color='#333',linewidth=.7);ax.text((a+b)/2,y+cap*1.3,label,ha='center',va='bottom',fontsize=annotation_size)
            buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=dpi)
            if folder:
                root=Path(folder);(root/'plot.png').write_bytes(buffer.getvalue())
                fig.savefig(root/'plot.svg',format='svg');fig.savefig(root/'plot.pdf',format='pdf')
            caption=f"每点代表一个独立单位；配对图按明确 ID 连线。误差线：{error}。缺失 {missing}，排除 {excluded}。"
            if comparisons:caption+=' '+run['method_text']
            if annotation=='stars':caption+=' 星号：* P<0.05，** P<0.01，*** P<0.001，**** P<0.0001；ns P≥0.05。'
            return dict(png='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode(),caption=caption,notes=notes)
        finally:plt.close(fig)
