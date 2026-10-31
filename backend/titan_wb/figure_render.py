"""A single offline PNG/SVG renderer shared by preview, Excel and archived figures."""
import math
from pathlib import Path
import numpy as np
from .figures import resolve_figure_settings,figure_data,jitter_positions

_FONT_READY=False


def _fonts():
    global _FONT_READY
    if not _FONT_READY:
        from matplotlib import font_manager
        font=Path(__file__).parent/'assets/NotoSansSC.ttf'
        if font.is_file():font_manager.fontManager.addfont(str(font))
        _FONT_READY=True


def render_figure(result,root,plot_settings,figure_settings=None,project=None):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    _fonts();f=resolve_figure_settings(project,figure_settings);data=figure_data(project,result,f)
    for group in data['group_registry']:
        f['colors'].setdefault(group['key'],group['color'])
        if group['key'] not in f['group_order']:f['group_order'].append(group['key'])
    panels=data['panels'];width=plot_settings['panel_width']*max(1,len(panels));height=plot_settings['height']
    if width*height*plot_settings['dpi']**2>20_000_000:raise ValueError('图表超过2000万像素，请减少面板或降低尺寸/DPI')
    style={'font.family':['DejaVu Sans','Noto Sans SC'],'axes.unicode_minus':False,'text.parse_math':False,'svg.fonttype':'path','font.size':plot_settings['font_size']}
    with plt.rc_context(style):
        fig,axs=plt.subplots(1,max(1,len(panels)),figsize=(width,height),squeeze=False)
        try:
            for ax,panel in zip(axs[0],panels):
                positions=np.arange(len(panel['groups']))*(1+f['bar_gap']);labels=[]
                for x,group in zip(positions,panel['groups']):
                    labels.append(group['label']+(' / n='+str(group['n']) if f['show_n'] and data['unit']=='biological' else ''))
                    if group['n']==0:
                        ax.text(x,.04,'ND' if group['status']=='not_detected' else 'NA',transform=ax.get_xaxis_transform(),ha='center',color='#68758b');continue
                    if f['kind']!='scatter':ax.bar(x,group['mean'],width=f['bar_width'],color=group['color'],edgecolor=group['border'],linewidth=f['axis_width'],zorder=1)
                    else:ax.hlines(group['mean'],x-f['bar_width']/2,x+f['bar_width']/2,color=group['border'],linewidth=f['axis_width'],zorder=2)
                    if f['kind']!='bar':
                        jitter=jitter_positions(group['n'],f['jitter'])
                        ax.scatter(x+np.asarray(jitter),group['values'],s=f['point_size']**2,marker={'circle':'o','square':'s','triangle':'^'}[f['point_marker']],facecolors='white' if f['hollow'] else group['color'],edgecolors=group['border'],linewidths=.8,zorder=4)
                    if data['unit']=='biological' and group['n']>1 and f['error']!='none':
                        lo,hi=group['ci95'] if f['error']=='ci95' else (group['mean']-group[f['error']],group['mean']+group[f['error']])
                        yerr=[[0 if f['error_direction']=='above' else group['mean']-lo],[hi-group['mean']]]
                        ax.errorbar(x,group['mean'],yerr=yerr,fmt='none',ecolor=group['border'],elinewidth=f['error_width'],capsize=f['error_cap'],capthick=f['error_width'],zorder=3)
                ax.set_xticks(positions,labels,rotation=f['label_angle'],ha='right' if f['label_angle']>0 else 'center')
                ax.set_ylabel(f['y_label'] or ('Target / reference ratio' if f['value_mode']=='normalized' else 'Relative to control (fold)'))
                ax.set_xlabel(f['x_label']);ax.set_title(f['title'] or panel['analyte'],fontstyle='italic' if f['title_italic'] else 'normal')
                ax.spines[['top','right']].set_visible(False)
                for spine in ax.spines.values():spine.set_linewidth(f['axis_width'])
                ax.tick_params(width=f['axis_width']);ax.grid(False)
                limits=panel['limits'];lo=min([0,*limits]);hi=max([1,*limits]);span=max(hi-lo,1e-12)
                lower=f['y_min'] if f['y_min'] is not None else (lo-span*.06 if lo<0 else 0)
                upper=f['y_max'] if f['y_max'] is not None else hi+span*(.12+.12*len(panel['comparisons']))
                if lower>=upper:raise ValueError('Y轴范围无法容纳当前数据')
                if f['y_step']:
                    if (upper-lower)/f['y_step']>50:raise ValueError('Y轴刻度过密，请增大刻度间隔')
                    start=math.ceil(lower/f['y_step'])*f['y_step'];ax.set_yticks(np.arange(start,upper+f['y_step']*.01,f['y_step']))
                ax.set_ylim(lower,upper)
                keys=[g['key'] for g in panel['groups']]
                for i,row in enumerate(panel['comparisons']):
                    a=positions[keys.index(row['group_a'])];b=positions[keys.index(row['group_b'])];y=hi+span*(.08+.12*i);cap=span*.025
                    ax.plot([a,a,b,b],[y,y+cap,y+cap,y],color='#202020',linewidth=.8,clip_on=False)
                    p=row['p_adjusted'];text=('****' if p<.0001 else '***' if p<.001 else '**' if p<.01 else '*' if p<.05 else 'ns') if f['annotations']=='stars' else 'p_adj='+format(p,'.3g')
                    ax.text((a+b)/2,y+cap*1.2,text,ha='center',va='bottom',fontsize=plot_settings['font_size']*.8)
                    if f['y_max'] is not None and y+cap>upper and '显著性括号超出自定义Y轴范围' not in panel['warnings']:panel['warnings'].append('显著性括号超出自定义Y轴范围')
                legend=('per-lane ratios' if data['unit']=='lane' else 'mean'+(' +/- '+f['error'].upper() if f['error']!='none' else ''))+'; '+panel['analysis_block']
                if panel['comparisons']:
                    methods=sorted({r['adjustment_method']+'/'+r['scale'] for r in panel['comparisons']});legend+='; adjusted p: '+', '.join(methods)
                    if f['annotations']=='stars':legend+='; *<.05, **<.01, ***<.001, ****<.0001'
                if panel['warnings']:legend+='\n'+'; '.join(panel['warnings'])
                ax.text(.5,-.38,legend,transform=ax.transAxes,ha='center',va='top',fontsize=max(6,plot_settings['font_size']*.65),wrap=True)
            if not panels:axs[0,0].text(.5,.5,'No eligible values',ha='center');axs[0,0].set_axis_off()
            fig.tight_layout()
            fig.savefig(root/'plot.png',dpi=plot_settings['dpi'])
            fig.savefig(root/'plot.svg')
        finally:plt.close(fig)
    return data,f
