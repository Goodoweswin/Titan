import {createProject} from './state'
import type {Project,ROI} from './types'
export function testProject():Project {
 const p=createProject('experiment')
 p.images=[{id:'im',name:'raw.tif',path:'/raw.tif',sha256:'hash',width:100,height:100,dtype:'uint16',preview:'',polarity:'bright',ceiling:4095,exposure:'',linear_validated:false}]
 p.samples=['1','2'].map(n=>({id:'S'+n,bio_id:'B'+n,group:'control',pair_id:'',kind:'biological',pool_id:''}))
 p.lanes=['1','2'].map(n=>({id:'L'+n,sample_id:'S'+n,membrane_id:'M1',technical_id:'1'}))
 p.rois=['1','2'].flatMap((n,i)=>['target','reference'].map((role,j)=>({id:role+n,image_id:'im',lane_id:'L'+n,analyte:role==='target'?'PROTEIN':'ACTIN',role,rect:[10+i*40,20+j*40,30+i*40,30+j*40],backgrounds:[[10+i*40,14+j*40,30+i*40,17+j*40]],reference_id:role==='target'?'reference'+n:null,reviewed_revision:0} as ROI)))
 return p
}
