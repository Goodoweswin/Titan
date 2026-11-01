"""Independent packaged-worker acceptance of synthetic figures/statistics/library.

No backend imports. The fixed pixel fixture gives ratios [1,2,3], [2,3,4],
[4,5,6], with hand-derived ordinary F(2,6)=7, p=.027.
"""
import argparse,base64,copy,hashlib,json,math,os,shutil,subprocess,zipfile
from pathlib import Path
from release_environment import packaged_environment
import numpy as np
import tifffile
from openpyxl import load_workbook


def verify(binary,output):
    output=output.resolve();output.mkdir(parents=True,exist_ok=False)
    session=dict(pid=os.getpid(),token='publication-release',library_root=str(output/'library'))
    diagnostic=(output/'engine-stderr.log').open('w+',encoding='utf-8')
    worker=subprocess.Popen([str(binary.resolve()),'--stdio-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=diagnostic,text=True,encoding='utf-8',cwd=output,env=packaged_environment())
    sequence=0
    def call(command,**payload):
        nonlocal sequence
        sequence+=1;print('Checking bundled command:',command,flush=True);worker.stdin.write(json.dumps(dict(request_id=sequence,command=command,payload=payload,session=session))+'\n');worker.stdin.flush()
        response=json.loads(worker.stdout.readline());assert response.get('request_id')==sequence and response['ok'],response
        return response['data']
    def rows(sheet):
        values=list(sheet.values);return [dict(zip(values[0],r)) for r in values[1:]]
    try:
        health=call('health');assert health['version']==json.loads((Path(__file__).resolve().parents[1]/'package.json').read_text(encoding='utf-8'))['version']
        created=call('library_create',name='三组定量 · 合成验收');p=created['project']
        values=[1,2,3,2,3,4,4,5,6];pixels=np.full((40,100),1000,dtype=np.uint16)
        for i,value in enumerate(values):
            x=2+10*i;pixels[10:12,x:x+2]=3000;pixels[25:27,x:x+2]=1000+2000*value
        source=output/'SYNTHETIC_ONLY.tif';tifffile.imwrite(source,pixels,photometric='minisblack')
        p=call('import_image',project=p,path=str(source));image=p['images'][0];image.update(ceiling=65535,linear_validated=True)
        p['samples']=[dict(id=f'S{i}',bio_id=f'B{i}',group=['A','B','C'][i//3],pair_id='',kind='biological',pool_id='') for i in range(9)]
        p['lanes']=[dict(id=f'L{i}',sample_id=f'S{i}',membrane_id='M1',technical_id='1') for i in range(9)]
        p['rois']=[];p['synthetic']=True
        for i in range(9):
            x=2+10*i
            for role,y,analyte in [('reference',10,'ACTIN'),('target',25,'AKT')]:
                p['rois'].append(dict(id=f'{role}{i}',image_id=image['id'],lane_id=f'L{i}',analyte=analyte,role=role,rect=[x,y,x+2,y+2],backgrounds=[[x,2,x+2,4]],reference_id=f'reference{i}' if role=='target' else None,reviewed_revision=p['revision']))
        spec=dict(id='multi',analyte='AKT',membrane_id='M1',groups=['A','B','C'],control_group='A',method='anova',scope='all',scale='raw')
        p['settings'].update(design_confirmed=True,control_group='A',multigroup_comparisons=[spec])
        p=call('save_project',project=p,path=p['project_path'],expected_revision=0);result=call('analyze',project=p)
        assert [v['value'] for v in result['biological']]==values
        om=result['multigroup_omnibus'][0];assert math.isclose(om['statistic'],7) and math.isclose(om['p_raw'],.027)
        assert len(result['multigroup_comparisons'])==3
        checks={}
        for method,scope,count in [('anova','control',2),('welch_anova','all',3),('welch_anova','control',2)]:
            alternate=copy.deepcopy(p);alternate['settings']['multigroup_comparisons'][0].update(method=method,scope=scope)
            r=call('analyze',project=alternate);assert len(r['multigroup_comparisons'])==count
            if method=='welch_anova':assert math.isclose(r['multigroup_omnibus'][0]['statistic'],6) and math.isclose(r['multigroup_omnibus'][0]['p_raw'],.0625)
            checks[method+'/'+scope]=count
        dimensions=dict(panel_width=5,height=4,font_size=12,dpi=160)
        figure=dict(colors={'A':'#F1D21B','B':'#A7A7AF','C':'#55AA77'},title='蛋白表达 · AKT',y_label='Norm. expression',error='sem',annotations='p',comparison_ids=[json.dumps([r[k] for k in ['comparison_id','analyte','membrane_id','group_a','group_b']],separators=(',',':')) for r in result['multigroup_comparisons']])
        preview=call('export_preview',project=p,result=result,settings=dimensions,figure_settings=figure)
        assert len(preview['figure_data']['panels'][0]['comparisons'])==3
        doc=call('save_figure',project=p,result=result,settings=dimensions,figure_settings=figure,name='三组柱图')
        frozen=call('load_figure',path=p['project_path'],figure_id=doc['id']);assert frozen['result']==result
        exported=call('export',project=frozen['project'],result=frozen['result'],destination=str(output/'export'),settings=dimensions,figure_settings=frozen['figure_settings'])
        assert (output/'export/plot.png').read_bytes()==base64.b64decode(preview['png'].split(',')[1])
        book=load_workbook(output/'export/results.xlsx',data_only=True)
        assert len(book.sheetnames)==12 and rows(book['分组描述'])[0]['n']==3
        assert math.isclose(rows(book['多组总体检验'])[0]['F'],7) and len(rows(book['多重比较']))==3
        assert rows(book['分组描述'])[0]['颜色']=='#F1D21B';book.close()
        with zipfile.ZipFile(output/'export/results.xlsx') as z:assert z.read('xl/media/image1.png')==(output/'export/plot.png').read_bytes()
        for name,digest in exported['outputs'].items():assert hashlib.sha256((output/'export'/name).read_bytes()).hexdigest()==digest
        config=json.loads((output/'export/project.json').read_text());assert config['figure_settings']==exported['figure_settings'] and config['plot_settings']==dimensions
        origin=dict(path=str(output/'export'),png_sha256=exported['outputs']['plot.png'])
        archive=call('save_figure',project=p,result=result,settings=dimensions,figure_settings=figure,name='导出归档',export_origin=origin)
        assert call('load_figure',path=p['project_path'],figure_id=archive['id'])['document']['export_origin']==origin
        restyled=call('save_figure',project=frozen['project'],result=result,settings=dimensions,figure_settings={**figure,'error':'ci95'},name='均值CI图',figure_id=doc['id'],expected_version=doc['current_version'])
        assert len(restyled['versions'])==2
        changed=copy.deepcopy(p);changed['name']='更新实验名';changed['revision']+=1
        for r in changed['rois']:r['reviewed_revision']=changed['revision']
        changed=call('save_project',project=changed,path=p['project_path'],expected_revision=p['saved_revision'])
        assert call('load_figure',path=p['project_path'],figure_id=doc['id'])['project']['name']==p['name']
        copied=call('save_project',project=changed,path=str(output/'portable.titanwb'),expected_revision=None)
        call('library_register',path=copied['project_path']);assert len(call('library_list'))==2
        call('release_project',path=p['project_path']);shutil.rmtree(p['project_path'])
        restored=call('load_figure',path=copied['project_path'],figure_id=doc['id'])
        assert restored['result']==result and len(restored['document']['versions'])==2
        call('release_project',path=copied['project_path']);assert call('health')['worker_pid']==health['worker_pid']
        report=dict(version=health['version'],synthetic_only=True,clean_path=True,worker_starts=1,ratios=values,ordinary_F=7,ordinary_p=.027,welch_F=6,welch_p=.0625,methods=checks,excel_sheets=12,preview_export_excel_png_equal=True,export_settings_match=True,archive_source_frozen=True,archive_export_png_link=True,portable_history_versions=2,library_copies_distinct=True)
        (output/'publication-release-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:
        worker.stdin.close()
        try:worker.wait(timeout=5)
        except subprocess.TimeoutExpired:worker.kill();worker.wait()
        diagnostic.seek(0);stderr=diagnostic.read();diagnostic.close()
        if 'Glyph ' in stderr:raise AssertionError('Bundled offline font has missing glyphs: '+stderr)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args();verify(args.binary,args.output)
