# Titan 二维免疫荧光模块

用户在本聊天批准的设计是实现依据：二维 TIFF/OME-TIFF/分通道文件，区域强度、阳性面积、DAPI 核分割与人工修正、核内阳性率、批处理、独立论文组图。IF 与 WB 分别建项目，共用项目库。原始像素、分析数据、显示参数分离；人工 mask 正式持久保存。Fiji 是独立测量参考，不内嵌 JVM。AI/3D/WSI/共定位不在首版。

## Scientific contract

Mean=sum/N; corrected_sum=sum-N*mean(background), negative values retained; physical area=N*pixel_size_x*pixel_size_y. Measurement always uses original channels and confirmed masks, not display/segmentation images. Positive thresholds require an explicit numeric value and provenance, are frozen per comparable batch. DAPI represents nuclei only. Sample summaries pool numerator/denominator and never treat fields/cells as biological n. No inferential tests in v1.

## Shared implementation contract

All dictionaries use snake_case. IDs are stable random hex strings. File paths in active projects are absolute; persisted originals/artifacts are relative to project root and resolved safely on open. JSON never contains pixel arrays. Image labels are uint32 TIFF files with zero background.

```json
{
 "module":"if","schema_version":1,"id":"id","name":"实验","revision":0,
 "fields":[],
 "figure":{"field_ids":[],"channel_ids":[],"include_merge":true,"crop":null,"inset":null,"width_mm":180,"dpi":300,"font_pt":9,"scale_bar_um":null,"locked_ranges":{}},
 "project_path":"/.../id.titanif","saved_revision":0,"read_only":false
}
```

Field:
```json
{
 "id":"field-id","name":"视野 1","sample_id":"S1","bio_id":"B1","group":"control","batch_id":"batch1",
 "width":512,"height":512,"pixel_size_um":[0.5,0.5],"quantitative":true,
 "channels":[{"id":"c1","name":"DAPI","color":"#4090ff","display_min":0,"display_max":65535,
   "source":{"path":"/x.ome.tif","sha256":"digest","series_index":0,"axes":"CYX","indexers":{"C":0}}}],
 "rois":[{"id":"r1","name":"区域","role":"signal","shape":"rectangle","points":[[0,0],[100,100]]}],
 "recipe":{"mode":"region","nuclear_channel_id":"c1","target_channel_ids":["c1"],
   "thresholds":{},"threshold_source":"","thresholds_frozen":false,
   "segmentation":{"sigma":1,"threshold_method":"otsu","threshold":null,"min_area":20,"max_area":100000,"min_distance":5,"exclude_border":true,"rolling_ball_radius":0}},
 "mask":null,"result":null
}
```

ROI shape=rectangle|ellipse|polygon, role=signal|background, coordinates in original pixels. Rectangle/ellipse uses two opposite box corners; polygon uses >=3 vertices. Pixel-center inclusion applies consistently.
mask={path,sha256,version,segmentation_signature,confirmed}; mask edits retain immutable earlier artifacts.
result={field_id,input_signature,objects,summary,warnings}; mask and measurement signatures supplied by models.py.
objects rows: object_id,channel_id,area_px,area_um2,raw_sum,mean,background_mean,corrected_sum,positive_pixels,positive (nullable).
summary rows: field_id,channel_id,object_count,area_px,area_um2,raw_sum,mean,background_mean,corrected_sum,positive_pixels,positive_area_fraction,positive_count,positive_fraction. Null for unavailable metrics. A failed field remains failed, never becomes zero.

### Python subsystem interfaces

- images.inspect_image(path)->{name,size_bytes,series:[{index,axes,shape,dtype,width,height,channel_count,channel_names,pixel_size_um,quantitative,requires_axes_mapping}]}; metadata only, no whole-file hash.
- images.import_field(selections, metadata=None)->field. selections=[{path,series_index:0,indexers:{Z:0,T:0},axes_override:null,channel_indices:[0,1]}]. Metadata includes name/sample_id/bio_id/group/batch_id/pixel_size_um. Stream hashes. Require explicit axes override for ambiguous Q/I axes; never guess pages as channels.
- images.load_channels(field)->dict[channel_id,np.ndarray]; verify source hash and selected plane; images.preview_field(field, channel_id=None, max_size=1200)->PNG data URL, null channel_id means merged.
- analysis.roi_mask(roi,shape)->bool ndarray; analysis.segment_nuclei(field)->uint32 ndarray; analysis.measure_field(field,labels=None)->result.
- analysis.edit_labels(labels,action)->new labels. action={kind:add|delete|merge|split, ids?:[int], roi?:ROI, points?:[[x,y],[x,y]]}; add fills ROI with next ID, delete clears IDs, merge takes lowest ID, split partitions selected ID by a line between points.
- analysis.aggregate_results(project)->{objects,fields,samples}; rejects stale results. sample rows group by bio_id/group/batch/channel and preserve positive numerators/denominators.
- figures.preview_figure(project)->{png,width,height,warnings}; figures.export_figure(project,destination)->{files:[absolute paths]}; independent of quantification, exports PNG/TIFF/SVG, text remains SVG text; figures.export_results(project,destination)->{files}; CSV/XLSX and biological sample scatter PNG.
- models.new_project(name), models.validate_project(p), models.analysis_signature(field), models.segmentation_signature(field).
- projects.save_project(project,path,expected_revision,session)->project; projects.open_project(path,session,read_only=False)->project.
- jobs.start(project,operation,options,session)->{job_id,status}; jobs.status(job_id,session)->job status, jobs.cancel(job_id,session). Jobs persisted under session library_root and executed in spawned child processes; small engine commands return immediately.

### Engine API consumed by UI

- if_new {name} -> saved IFProject (registered in library)
- if_demo {} -> saved synthetic IFProject with channels/regions/metadata, clearly synthetic.
- if_open {path,read_only?}; if_save {project,expected_revision?}; if_release {path}
- if_inspect {path}; if_preview {field,channel_id?}
- if_figure_preview {project}; if_export_figure {project,destination}; if_export_results {project,destination}
- if_start_job {project,operation:import|segment|measure|batch|edit_mask,options}
  import options={selections,metadata}; segment/measure options={field_id}; batch options={field_ids,recipe}; edit_mask options={field_id,action}.
- if_job_status {job_id}-> {job_id,status:queued|running|completed|cancelled|failed,completed,total,message,error?,project?}
- if_cancel_job {job_id}
- if_accept_job {project,job_id}->updated project; verifies project identity and relevant input signatures, retains display-only edits; only accepted results become active.
- library_list includes module:wb|if; missing old entries default wb. IF results never enter WB figure catalogs.

## Resource and verification constraints

Max four channels, 4096² pixels/plane, file <=2 GiB, raw decode <=256 MiB, estimated work <=1 GiB. Metadata first, decode selected planes; stream hash/copy. Background ROI explicit and non-overlapping. Missing calibration means pixel units and no physical scale bar. RGB allowed for figures only. Z/T>1 requires explicit plane selection. Same marker/batch display ranges can be locked, without changing measurement signatures.
Validate hand-derived numerical fixtures and Fiji same-mask Mean/RawIntDen references; integers exact, floats reltol 1e-6. Real-image scientific claim requires >=20 representative fields from >=3 biological samples and independently annotated nuclei; IoU>=0.5 and P/R>=0.90 initial gate. No such private dataset has been supplied; this remains an explicit external validation gap.
