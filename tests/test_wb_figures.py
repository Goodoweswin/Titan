import base64, copy, io, json, os, shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pytest
from PIL import Image
from titan_wb.models import new_project
from titan_wb.images import import_image, file_hash
from titan_wb.projects import save_project
from titan_wb.wb_figures import new_document, preview_document, save_document, load_document, list_documents, export_document


def fixture(tmp_path):
    raw=np.tile(np.arange(120,dtype=np.uint8),(60,1)); raw[20:30,10:110]=200
    path=tmp_path/'source.png';Image.fromarray(raw).save(path)
    p=import_image(new_project('WB'),str(path));s=dict(pid=os.getpid(),token='wb')
    p=save_project(p,str(tmp_path/'exp.titanwb'),None,s)
    d=new_document(p);d['rows'][0].update(protein='AKT',crop=[10,20,110,30],confirmed=True,expected_mw='60')
    return p,d,s


def test_chinese_wb_documents_round_trip_with_non_utf8_default(tmp_path,monkeypatch):
    p,d,s=fixture(tmp_path)
    p['name']='中文实验'
    p=save_project(p,p['project_path'],p['saved_revision'],s)
    d['name']='中文条带组图';d['rows'][0]['protein']='蛋白 AKT'
    original=Path.read_text
    def locale_read(path,encoding=None,errors=None):
        return original(path,encoding=encoding or 'cp1252',errors=errors)
    monkeypatch.setattr(Path,'read_text',locale_read)
    saved=save_document(p,d,s)
    assert saved['name']=='中文条带组图'
    assert load_document(p,saved['id'])['rows'][0]['protein']=='蛋白 AKT'
    assert list_documents(p)[0]['name']=='中文条带组图'
    saved['name']='修订后的组图'
    updated=save_document(p,saved,s,expected_version=saved['version'])
    assert updated['name']=='修订后的组图'
    assert load_document(p,saved['id'],saved['version'])['name']=='中文条带组图'


def test_crop_pixels_layout_svg_text_and_dpi_share_one_definition(tmp_path):
    p,d,s=fixture(tmp_path);d['labels']=[dict(text='Ctrl < &',x=.25)]
    preview=preview_document(p,d)
    assert preview['width_mm']==85
    row=preview['layout']['rows'][0]
    assert row['height_pt']/row['width_pt']==pytest.approx(.1)
    image=Image.open(io.BytesIO(base64.b64decode(preview['png'].split(',')[1])))
    assert image.width==round(85/25.4*300)
    assert image.info['dpi'][0]==pytest.approx(300,abs=.1)
    output=tmp_path/'export';export_document(p,d,str(output))
    svg=ET.parse(output/'figure.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
    assert any(t.text=='Ctrl < &' for t in svg.findall('.//s:text',ns))
    embedded=svg.find('.//s:image',ns).get('href')
    crop=np.array(Image.open(io.BytesIO(base64.b64decode(embedded.split(',')[1]))))
    assert crop.shape==(10,100) and np.all(crop==255)
    assert '非实验数据' not in (output/'figure.svg').read_text()
    assert json.loads((output/'source.json').read_text())['document']['rows'][0]['source']['sha256']==p['images'][0]['sha256']
    with pytest.raises(ValueError,match='存在'):export_document(p,d,str(output))


def test_save_without_analysis_preserves_old_sources_copy_and_versions(tmp_path):
    p,d,s=fixture(tmp_path);before=copy.deepcopy(p);saved=save_document(p,d,s)
    assert p==before and len(list_documents(p))==1
    loaded=load_document(p,saved['id']);assert loaded['rows'][0]['crop']==[10,20,110,30]
    loaded['name']='修订';second=save_document(p,loaded,s,expected_version=loaded['version'])
    assert second['version']!=loaded['version']
    with pytest.raises(ValueError,match='版本'):save_document(p,loaded,s,expected_version=loaded['version'])
    assert load_document(p,saved['id'],saved['version'])['name']==saved['name']
    empty=copy.deepcopy(p);empty['images']=[];empty['revision']+=1
    empty=save_project(empty,p['project_path'],p['saved_revision'],s)
    copied=save_project(empty,str(tmp_path/'copy.titanwb'),None,s);shutil.rmtree(p['project_path'])
    reopened=load_document(copied,saved['id']);assert preview_document(copied,reopened)['png'].startswith('data:image/png')
    assert all(not str(row['source']['path']).startswith(str(tmp_path/'exp.titanwb')) for row in reopened['rows'])


@pytest.mark.parametrize('field,value', [('crop',[-1,0,10,10]),('crop',[0,0,121,10]),('crop',[0,0,0,2]),('confirmed',False)])
def test_invalid_or_unconfirmed_crops_cannot_export(tmp_path,field,value):
    p,d,s=fixture(tmp_path);d['rows'][0][field]=value
    with pytest.raises(ValueError):export_document(p,d,str(tmp_path/'bad'))
    assert not (tmp_path/'bad').exists()


def test_sources_limits_marker_positions_readonly_and_corrupt_catalog(tmp_path):
    p,d,s=fixture(tmp_path);d['rows'][0]['markers']=[dict(text='75',y=40)]
    with pytest.raises(ValueError,match='marker|范围'):preview_document(p,d)
    d['rows'][0]['markers']=[];d['settings']['width_mm']=float('nan')
    with pytest.raises(ValueError):preview_document(p,d)
    d['settings']['width_mm']=85
    with pytest.raises(ValueError,match='只读'):save_document(dict(p,read_only=True),d,s)
    export_document(dict(p,read_only=True),d,str(tmp_path/'readonly'))
    saved=save_document(p,d,s);root=Path(p['project_path'])
    (root/'figures/wb/catalog.json').write_text('{bad')
    with pytest.raises(ValueError,match='索引'):list_documents(p)
    with pytest.raises(ValueError):save_document(p,d,s)
    assert (root/'figures/wb/catalog.json').read_text()=='{bad'
    Path(p['images'][0]['path']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash|原图'):preview_document(p,d)


def test_rotated_multipage_miniswhite_source_display_is_whole_image(tmp_path):
    import tifffile
    from titan_wb.image_rotation import rotate_image
    raw=np.arange(1200,dtype=np.uint16).reshape(30,40)
    path=tmp_path/'two.tif'
    with tifffile.TiffWriter(path) as w:
        w.write(raw,photometric='miniswhite');w.write(raw+1000,photometric='miniswhite')
    p=import_image(new_project('pages'),str(path),page_index=1)
    rotated=rotate_image(p,p['images'][0]['id'],90);p['images']=[rotated]
    d=new_document(p);d['rows'][0].update(crop=[0,0,30,40],confirmed=True)
    export_document(p,d,str(tmp_path/'rotated'))
    svg=ET.parse(tmp_path/'rotated/figure.svg').getroot();node=svg.find('{http://www.w3.org/2000/svg}image')
    rendered=np.array(Image.open(io.BytesIO(base64.b64decode(node.get('href').split(',')[1]))))
    assert rendered.shape==(40,30)
    assert rendered[0,0]<rendered[0,-1]  # whole frame inversion after clockwise rotation
    assert json.loads((tmp_path/'rotated/source.json').read_text())['document']['rows'][0]['source']['page_index']==1


def test_large_layout_and_synthetic_exports_are_explicit(tmp_path):
    p,d,s=fixture(tmp_path);p['synthetic']=True
    export_document(p,d,str(tmp_path/'demo'))
    assert '非实验数据' in (tmp_path/'demo/figure.svg').read_text()
    d['settings'].update(width_mm=180,dpi=600)
    d['rows']=[dict(copy.deepcopy(d['rows'][0]),id=str(i),crop=[0,0,120,60]) for i in range(40)]
    with pytest.raises(ValueError,match='像素|尺寸|行数'):preview_document(p,d)


def test_raster_uses_regular_font_matching_editable_svg_default_weight():
    from titan_wb.wb_render import font
    from PIL import ImageFont
    path=Path(__file__).parents[1]/'backend/titan_wb/assets/NotoSansSC.ttf'
    reference=ImageFont.truetype(str(path),32);reference.set_variation_by_name('Regular')
    assert bytes(font(32).getmask('AKT 蛋白'))==bytes(reference.getmask('AKT 蛋白'))


@pytest.mark.parametrize('inverted',[False,True])
def test_rotated_grayscale_palette_maps_intensity_before_resampling(tmp_path,inverted):
    import tifffile
    from titan_wb.image_rotation import rotate_image,rotate_pixels
    raw=np.tile(np.arange(40,dtype=np.uint8),(30,1))
    lut=np.asarray([int((i/255)**2*65535) for i in range(256)],dtype=np.uint16)
    if inverted:lut=lut[::-1].copy()
    path=tmp_path/'palette.tif';tifffile.imwrite(path,raw,photometric='palette',colormap=np.stack([lut]*3))
    p=import_image(new_project('palette'),str(path));p['images']=[rotate_image(p,p['images'][0]['id'],5)]
    d=new_document(p);d['rows'][0]['confirmed']=True
    from titan_wb.wb_render import display_pixels
    source=d['rows'][0]['source'];rendered=display_pixels(source)
    mapped=rotate_pixels(lut[raw],5);low,high=np.percentile(mapped,[.5,99.5]);high=max(high,low+1)
    expected=np.uint8(np.clip((mapped-low)/(high-low),0,1)*255)
    assert np.array_equal(rendered,expected)
    assert preview_document(p,d)['png'].startswith('data:image/png')
    d['rows'][0]['crop']=[3,4,30,25]
    export_document(p,d,str(tmp_path/'cropped'))
    svg=ET.parse(tmp_path/'cropped/figure.svg').getroot()
    node=svg.find('{http://www.w3.org/2000/svg}image')
    actual=np.array(Image.open(io.BytesIO(base64.b64decode(node.get('href').split(',')[1]))))
    assert np.array_equal(actual,expected[4:25,3:30])
