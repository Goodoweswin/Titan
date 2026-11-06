export interface Group{id:string;label:string}
export interface Row{id:string;label:string;values:Record<string,string>;excluded:Record<string,boolean>;units?:Record<string,string>}
export interface Style{comparison_keys?:string[];point_size:number;point_marker:string;hollow:boolean;axis_width:number;error_width:number;error_cap:number;bar_width:number;label_angle:number;group_order:string[];labels:Record<string,string>;kind:string;error:string;width_mm:number;height_mm:number;font_size:number;dpi:number;title:string;y_label:string;annotations:string;colors:Record<string,string>;y_min:number|null;y_max:number|null;text_mode:string}
export interface Dataset{id:string;name:string;groups:Group[];rows:Row[];confirmed:boolean;source:null|{kind:string;path?:string;locked?:boolean;blocked?:string;revision?:number;endpoint?:string;block?:string;signature?:string;project_name?:string;project_id?:string;selector?:Record<string,string>;notes?:string[]};analysis:{method:string;scale:string;scope:string;control_group:string};style:Style;runs:Run[]}
export interface Run{id:string;signature:string;created_at:string;dataset:Dataset;summaries:{group:string;label:string;n:number;mean:number|null;sd:number|null;sem:number|null;ci95:[number,number]|null}[];comparisons:Record<string,any>[];omnibus:Record<string,any>|null;method_text:string;scipy_version:string}
export interface Figure{id:string;name:string;dataset:Dataset;style:Style;run:Run|null}
export interface StatsProject{id:string;module:'stats';schema_version:1;name:string;revision:number;saved_revision:number;project_path:string;datasets:Dataset[];figures:Figure[]}
export const inputKey=(d:Dataset)=>JSON.stringify([d.id,d.groups.map(g=>g.id),d.rows,d.confirmed,d.source,d.analysis])
export const currentRun=(d:Dataset)=>[...d.runs].reverse().find(r=>inputKey(r.dataset)===inputKey(d))??null

export interface SourceChoice{key:string;label:string;endpoint:string;block:string;unit:string;n:number;missing:number;groups:{name:string;n:number}[];unavailable:boolean;reason:string;notes:string[];preview:{bio_id:string;group:string;value:number|null;missing_reason:string}[]}
export interface SourceCatalog{path:string;project_id:string;name:string;kind:"wb"|"if";revision:number;signature:string;choices:SourceChoice[]}
