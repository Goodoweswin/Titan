import type {BioValue} from './types'
export function plotSeries(values:BioValue[],analyte:string,block:string){return values.filter(b=>b.analyte===analyte&&b.analysis_block===block)}
