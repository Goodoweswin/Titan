import {it,expect} from 'vitest'
import {plotSeries} from './plot'
it('does not pool endpoints or blots when displaying biological n',()=>{
 const units=[{analyte:'A',analysis_block:'M1',bio_id:'1'},{analyte:'B',analysis_block:'M1',bio_id:'1'},{analyte:'A',analysis_block:'M2',bio_id:'2'}] as any
 expect(plotSeries(units,'A','M1')).toHaveLength(1)
})
