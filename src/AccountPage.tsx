import {useEffect,useRef,useState} from 'react'
import {ArrowLeft,ArrowUpRight,Check,Folder,LogIn,ShieldCheck,UserRound} from 'lucide-react'
import type {LibraryEntry} from './types'
import {activityCalendar,activitySummary,type ResearchActivity} from './research-activity'

/** Only a server-verified profile may populate these fields when authentication is connected. */
export interface AccountProfile {name:string;email:string;createdAt:string;emailVerified:boolean}
interface Props {
 profile?:AccountProfile|null
 entries:LibraryEntry[]
 libraryError:string
 activity:ResearchActivity|null
 activityError:string
 opening:boolean
 onBack:()=>void
 onOpen:(entry:LibraryEntry)=>void
 onRetry:()=>void
}
const formatDate=(value:string)=>Number.isFinite(Date.parse(value))?new Date(value).toLocaleDateString('zh-CN'):'—'
const number=(value:number|undefined)=>value===undefined?'—':value.toLocaleString('zh-CN')

export default function AccountPage({profile=null,entries,libraryError,activity,activityError,opening,onBack,onOpen,onRetry}:Props){
 const title=useRef<HTMLHeadingElement>(null)
 const [loginInfo,setLoginInfo]=useState(false),[metric,setMetric]=useState<'images'|'bands'>('images')
 useEffect(()=>{title.current?.focus()},[])
 const summary=activity?activitySummary(activity):null
 const calendar=activity?activityCalendar(activity,metric):[]
 const max=Math.max(1,...calendar.map(cell=>cell.count))
 const recent=[...entries].sort((a,b)=>(Date.parse(b.last_opened)||0)-(Date.parse(a.last_opened)||0)).slice(0,3)
 const metrics=[['分析条目',libraryError?undefined:entries.length,'个'],['已分析图像',summary?.images,'张'],['已定量条带',summary?.bands,'条'],['累计分析天数',summary?.days,'天'],['当前连续分析',summary?.streak,'天']] as const
 return <section className="account-page" aria-labelledby="account-page-title">
  <header className="account-topbar"><h1 ref={title} tabIndex={-1} id="account-page-title">账户</h1><button type="button" className="text-btn" onClick={onBack}><ArrowLeft size={15}/>返回工作区</button></header>
  <div className="account-content">
   <div className="account-profile">
    <div className="account-avatar" aria-hidden="true">{profile?profile.name.trim().slice(0,2).toUpperCase():<UserRound size={34}/>}</div>
    <h2>{profile?.name||'本地研究者'}</h2>
    <p className="account-email">{profile?.email||'登录后显示邮箱'}{profile?.emailVerified&&<Check size={15} aria-label="邮箱已验证"/>}</p>
    <p className="account-joined">账户创建日期 · {profile?formatDate(profile.createdAt):'登录后显示'}</p>
    {!profile&&<><button className="btn primary" type="button" aria-expanded={loginInfo} aria-controls="account-login-info" onClick={()=>setLoginInfo(v=>!v)}><LogIn size={16}/>登录 / 注册</button><small>未登录 · 本地功能可正常使用</small></>}
   </div>
   {!profile&&<div id="account-login-info" className="account-login-info" hidden={!loginInfo} role="status"><strong>登录服务尚未开放</strong><p>后续将在系统浏览器中完成邮箱注册与登录。当前可继续使用本地项目，账户资料暂不保存。</p><button type="button" className="text-btn" onClick={()=>setLoginInfo(false)}>知道了</button></div>}
   <section aria-labelledby="research-title">
    <div className="account-section-heading"><h3 id="research-title">研究足迹</h3><span>本机记录 · WB 分析足迹</span></div>
    {libraryError&&<p className="account-error" role="alert">项目库暂不可用，项目数量尚未确认。<button type="button" onClick={onRetry}>重试</button></p>}
    {activityError&&<p className="account-error" role="alert">{activityError}</p>}
    <dl className="account-metrics">{metrics.map(([label,value,unit])=><div key={label}><dt>{label}</dt><dd>{number(value)}<span>{value!==undefined?unit:''}</span></dd></div>)}</dl>
    <div className="account-feedback"><p>{summary?`本月新增分析 ${number(summary.monthImages)} 张图像，完成 ${number(summary.monthBands)} 条条带定量。`:'分析统计暂不可用。'}</p>{activity&&<span>自 {formatDate(activity.startedAt)} 起记录</span>}</div>
   </section>
   <section aria-labelledby="recent-projects-title">
    <div className="account-section-heading"><h3 id="recent-projects-title">最近分析</h3><span>从上次的探索继续</span></div>
    <div className="account-projects">{recent.map(entry=><button key={entry.entry_id} type="button" className="account-project" onClick={()=>onOpen(entry)} disabled={!entry.available||opening} aria-label={`继续项目 ${entry.name}`}><span className="account-project-icon"><Folder size={23}/></span><strong>{entry.name}</strong><span>{entry.available?`${entry.figures.length} 张已归档图表`:'项目需重新定位'}</span><small>最近打开 {formatDate(entry.last_opened)}</small><ArrowUpRight className="account-project-arrow" size={16}/></button>)}</div>
    {!recent.length&&<div className="account-empty"><Folder size={25}/><p>{libraryError?'项目列表暂不可用。':'还没有项目。创建一个实验，开始积累研究足迹。'}</p><button className="text-btn" type="button" onClick={onBack}>前往工作区</button></div>}
   </section>
   <section aria-labelledby="activity-title">
    <div className="account-section-heading"><div><h3 id="activity-title">分析活动</h3><p>每一格，记录一天新增的分析积累。</p></div><div className="account-metric-toggle" role="group" aria-label="活动统计指标"><button type="button" aria-pressed={metric==='images'} onClick={()=>setMetric('images')}>图像数</button><button type="button" aria-pressed={metric==='bands'} onClick={()=>setMetric('bands')}>条带数</button></div></div>
    {activity?<><div className="account-calendar-scroll"><div className="account-calendar" role="list" aria-label="最近二十周的分析活动">{calendar.map(cell=>{const level=cell.count?Math.max(1,Math.ceil(cell.count/max*4)):0;const label=`${cell.day}：${cell.future?'尚未到来':cell.untracked?'未启用统计':`${cell.count} ${metric==='images'?'张新增图像':'条新增条带'}`}`;return <div key={cell.day} role="listitem" title={label} aria-label={label} className={`account-day level-${level}${cell.future?' is-future':''}${cell.untracked?' is-untracked':''}`}/>})}</div><div className="account-calendar-dates"><span>{calendar[0]?.day}</span><span>{calendar.filter(cell=>!cell.future).at(-1)?.day}</span></div></div><div className="account-calendar-footer"><span>少</span>{[0,1,2,3,4].map(level=><i key={level} className={`account-day level-${level}`} aria-hidden="true"/>)}<span>多</span></div>{summary?.days===0&&<p className="account-empty-note">完成首次真实数据分析后，这里会记录你的研究积累。</p>}</>:<p className="account-empty-note">读取研究足迹后显示活动日历。</p>}
    <p className="account-counting-note">仅记录启用统计后完成的 Western blot 分析，合成示例不计入。相同项目中的同一图像与条带重复分析不重复累计；连续天数按有新增记录的日期计算，含今天或昨天。历史活动不回填。</p>
   </section>
   <footer className="account-footer"><ShieldCheck size={15}/><p>研究足迹保存在此设备，尚未绑定账户或跨设备同步。</p></footer>
  </div>
 </section>
}
