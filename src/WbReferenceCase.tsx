import type {Project} from './types'

export type CaseMode='annotated'|'practice'|'tutorial'
export interface WbExampleCase {
 id:string;mode:CaseMode;source_name:string;source_sha256:string;page_index:number
 uint16_max_pixels:number;source_note:string;suggested_window:[number,number,number,number];suggested_lane_count:number
}

export function WbReferenceCaseGuide({project}:{project:Project}){
 const info=project.example_case
 if(!info)return null
 const image=project.images[0]
 return <aside className="reference-case-guide" aria-label="WB 案例练习指引">
  <div><strong>{project.synthetic?'合成图像操作示范':'真实图像操作示范'}</strong><span>{info.source_name} · 第 {info.page_index+1} 页{image?.dtype==='uint16'?' · 16 位灰度':''}</span></div>
  <ol><li>内参：导入并确认配套内参</li><li>目标：复用泳道，检查峰区与背景</li><li>结果：核对样本、缺失提示与图表</li><li>WB 组图：裁剪后导出 PNG / PDF / SVG</li></ol>
  <details><summary>原图与测量说明</summary><p>{info.source_note}。{info.suggested_lane_count} 条泳道是教学标注。缺少内参时，结果页会提示缺少参考并将比值留空。</p>{!project.synthetic&&<p>本页有 {info.uint16_max_pixels.toLocaleString()} 个像素等于 65535。采集编码上界与线性范围尚未确认。</p>}</details>
 </aside>
}
