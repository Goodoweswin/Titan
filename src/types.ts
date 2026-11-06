export type Rect=[number,number,number,number]
export interface ImageAsset{rotation_degrees?:number;source_image_id?:string;source_name?:string;id:string;name:string;path:string;sha256:string;page_index?:number;page_count?:number;display_inverted?:boolean;photometric?:string;gray_lut?:number[];width:number;height:number;dtype:string;preview:string;polarity:'bright'|'dark';ceiling:number|null;exposure:string;linear_validated:boolean}
export interface ImageInspection{name:string;sha256:string;page_count:number;pages:{page_index:number;width:number;height:number;dtype:string;error:string|null;display_inverted?:boolean}[]}
export interface Sample{id:string;name?:string;bio_id:string;group:string;pair_id:string;kind:'biological'|'ibc';pool_id:string}
export interface Lane{id:string;membrane_id:string;sample_id:string;technical_id:string}
export interface ROI{id:string;image_id:string;lane_id:string;analyte:string;role:'target'|'reference';rect:Rect;backgrounds:Rect[];reference_id:string|null;reviewed_revision:number|null;lane_layout_id?:string;band_set_id?:string}
export interface ComparisonSpec{id:string;family_id:string;group_a:string;group_b:string;test:'descriptive'|'welch'|'paired';scale:'raw'|'log2'}
export interface Project{id:string;demo?:boolean;name:string;schema_version:2;revision:number;lane_layouts:LaneLayout[];band_sets:BandSet[];figure_settings?:FigureSettings;plot_settings?:PlotSettings;upgrade_from?:string;images:ImageAsset[];samples:Sample[];lanes:Lane[];rois:ROI[];settings:{design_confirmed?:boolean;control_group:string;normalization_mode:'within'|'ibc';ibc_by_membrane:Record<string,Record<string,string>>;analysis_blocks:{id:string;membrane_ids:string[];pooled_reference_id:string;merge_same_sample:boolean}[];comparisons:ComparisonSpec[];multigroup_comparisons?:MultiGroupSpec[]};saved_revision?:number;project_path?:string;read_only?:boolean}
export interface Measurement{id:string;image_id:string;lane_id:string;analyte:string;role:string;area_px:number;raw_sum:number;background_mean:number;corrected_sum:number;clipped_fraction:number|null;flags:string[]}
export interface Normalized{id:string;sample_id:string;bio_id:string;pair_id:string;group:string;membrane_id:string;analyte:string;normalized:number|null;bridged:number|null;flags:string[];kind:string}
export interface BioValue{sample_id:string;bio_id:string;pair_id:string;group:string;analyte:string;membrane_id:string;analysis_block:string;value:number;n_technical:number;fold:number|null;flags:string[]}
export interface StatsResult{analyte?:string;comparison_id:string;test:string;scale:string;n_a:number;n_b:number;effect:number|null;statistic:number|null;df:number|null;p_raw:number|null;p_adjusted:number|null;ci95:[number,number]|null;warnings:string[]}
export interface AnalysisResult{project_id:string;input_revision:number;source_signature?:string;measurements:Measurement[];normalized:Normalized[];biological:BioValue[];statistics:StatsResult[];lane_results?:LaneResult[];multigroup_omnibus?:MultiGroupOmnibus[];multigroup_comparisons?:MultiGroupComparison[]}
export interface LaneResult{membrane_id:string;lane_id:string;sample_id:string;analyte:string;band_set_id:string;corrected_sum:number|null;reference_analyte:string|null;reference_net:number|null;normalized:number|null;status:string;flags:string[];target_roi_id:string|null;reference_roi_id:string|null}
export interface SignalProfileData{project_id:string;input_revision:number;roi_id:string;rect:Rect;height:number;samples:{y:number;mean:number;min:number;max:number}[];background_mean:number|null;measurement:{raw_sum:number;corrected_sum:number;area_px:number}|null;warning:string|null}
export interface PlotSettings{panel_width:number;height:number;font_size:number;dpi:number}
export interface PlotPreview{png:string;width:number;height:number;settings:PlotSettings;figure_settings?:FigureSettings;figure_data?:FigureData}
export interface DetectionPreview{projectId:string;revision:number;imageId:string;analyte:string;role:'target'|'reference';boxes:Rect[];included:number[]}

export interface LaneColumn{lane_id:string;rect:Rect}
export interface LaneLayout{id:string;image_id:string;membrane_id:string;window:Rect;columns:LaneColumn[];excluded_regions:Rect[];source_layout_id:string|null;confirmed_revision:number|null}
export interface BandAssignment{lane_id:string;roi_id:string|null;status:'pending'|'accepted'|'not_detected'|'excluded'}
export interface BandSet{id:string;layout_id:string;analyte:string;role:'target'|'reference';window:Rect;reference_set_id:string|null;assignments:BandAssignment[]}
export interface LaneProposal{project_id:string;input_revision:number;image_id:string;window:Rect;columns:{proposal_id:string;rect:Rect;confidence:'high'|'low';reasons:string[]}[];expected_count:number|null;requires_review:boolean}
export interface BandCandidate{rect:Rect;backgrounds:Rect[]}
export interface BandProposal{lane_id:string;status:'proposed'|'ambiguous'|'not_detected';candidates:BandCandidate[];reasons:string[]}
export interface LaneProfileData{project_id:string;input_revision:number;layout_id:string;lane_id:string;window:Rect;width:number;total:number;samples:{y:number;sum:number;mean:number;min:number;max:number}[]}

export interface MultiGroupSpec{id:string;analyte:string;membrane_id:string;groups:string[];control_group:string|null;method:'descriptive'|'anova'|'welch_anova';scope:'control'|'all';scale:'raw'|'log2'}
export interface MultiGroupOmnibus{comparison_id:string;analyte:string;membrane_id:string;method:string;scale:string;status:string;n_by_group?:Record<string,number>;statistic:number|null;df_num:number|null;df_den:number|null;p_raw:number|null;warnings:string[]}
export interface MultiGroupComparison{comparison_id:string;analyte:string;membrane_id:string;scale:string;group_a:string;group_b:string;effect:number;statistic:number|null;p_adjusted:number;ci95:[number,number];adjustment_method:string;family_scope:string;display_scope:string;family_id:string;ci_method:string;effect_ratio:number|null;ratio_ci95:[number,number]|null;status:string;warnings:string[]}

export interface FigureSettings{kind:'bar_points'|'bar'|'scatter';value_mode:'normalized'|'fold';error:'none'|'sd'|'sem'|'ci95';error_direction:'both'|'above';colors:Record<string,string>;borders:Record<string,string>;display_labels:Record<string,string>;group_order:string[];point_marker:'circle'|'square'|'triangle';hollow:boolean;point_size:number;jitter:number;error_width:number;error_cap:number;bar_width:number;bar_gap:number;axis_width:number;title:string;title_italic:boolean;x_label:string;y_label:string;label_angle:number;y_min:number|null;y_max:number|null;y_step:number|null;annotations:'none'|'p'|'stars';comparison_ids:string[];panel_key:string;show_n:boolean}
export interface FigureGroup{key:string;label:string;color:string;border:string;values:number[];status:string;n:number;mean:number|null;sd:number|null;sem:number|null;ci95:[number,number]|null}
export interface FigureData{unit:'lane'|'biological';value_mode:string;error:string;notes:string[];group_registry?:{key:string;label:string;color:string}[];panels:{key:string;analyte:string;analysis_block:string;groups:FigureGroup[];comparisons:MultiGroupComparison[];warnings:string[];limits:number[]}[]}

export interface FigureDocumentMetadata{id:string;name:string;current_version:string;selected_version:string;source_revision:number;source_signature:string;source_stale:boolean;created_at:string;updated_at:string;kind:FigureSettings['kind'];panel_key:string;default_key?:string|null;export_origin?:{path:string;png_sha256:string}|null;versions:{version_id:string;source_revision:number;created_at:string;name:string}[]}
export interface LibraryEntry{module?:'wb'|'if'|'stats';collection_id?:string|null;resume?:LibraryResume;entry_id:string;project_id:string;name:string;path:string;last_opened:string;created_at:string;available:boolean;revision?:number;error?:string;figure_error?:string;artifacts?:LibraryArtifact[];figures:FigureDocumentMetadata[]}
export interface FrozenFigure{document:FigureDocumentMetadata;project:Project;result:AnalysisResult;figure_settings:FigureSettings;settings:PlotSettings;png:string}

export interface LibraryCollection {
 id: string
 name: string
 pinned: boolean
 created_at: string
}

export interface LibraryResume {
 view: 'workspace' | 'results' | 'figure'
 artifact_id?: string
 version_id?: string
 dataset_id?: string
}

export interface LibraryWorkspace {
 projects: LibraryCollection[]
 entries: LibraryEntry[]
}

export interface LibraryArtifact {
 id:string
 entry_id:string
 title:string
 kind:'stats_plot'|'wb_plot'|'wb_figure'|'wb_figure_export'|'if_figure_export'|'result_export'
 source_revision:number|null
 document_id?:string
 version_id?:string
 destination?:string
 files?:string[]
 available:boolean
}

export interface LibraryExportReceipt {
 library_export_retry?:{
  project_path:string
  project_id:string
  record:Pick<LibraryArtifact,'destination'|'files'|'title'|'kind'|'source_revision'|'version_id'>
 }
 library_export_error?:string
}

export interface CloseActions{prepare:()=>Promise<boolean>;finish:()=>Promise<void>}
