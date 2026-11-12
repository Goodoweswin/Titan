import {createContext,useCallback,useContext,useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react'
import type {KeyboardEvent,ReactNode} from 'react'
import {createPortal} from 'react-dom'

export interface ActionMenuItem {id:string;label:string;disabled?:boolean;onSelect:()=>void}
interface MenuRequest {
 id?:string
 items:ActionMenuItem[]
 origin:HTMLElement
 position:{x:number;y:number}
 label:string
}
interface MenuState extends MenuRequest {generation:number}
interface MenuApi {openMenu:(request:MenuRequest)=>void;closeMenu:()=>void;activeId:string|null}
const MenuContext=createContext<MenuApi|null>(null)

export function useActionMenu(){
 const api=useContext(MenuContext)
 if(!api)throw new Error('ActionMenuProvider is required')
 return api
}

export function ActionMenuProvider({children}:{children:ReactNode}){
 const [menu,setMenu]=useState<MenuState|null>(null),current=useRef(menu),generation=useRef(0)
 const element=useRef<HTMLDivElement>(null)
 const [position,setPosition]=useState({x:0,y:0,ready:false})
 const dismiss=useCallback((restoreFocus:boolean)=>{
  const origin=current.current?.origin
  current.current=null;setMenu(null)
  if(restoreFocus&&origin?.isConnected&&!origin.closest('[inert]')&&!origin.matches(':disabled'))origin.focus({preventScroll:true})
 },[])
 const closeMenu=useCallback(()=>dismiss(true),[dismiss])
 const openMenu=useCallback((request:MenuRequest)=>{
  if(!request.items.length||!request.origin.isConnected||request.origin.closest('[inert]'))return
  const next={...request,generation:++generation.current}
  current.current=next;setPosition({x:0,y:0,ready:false});setMenu(next)
 },[])
 useLayoutEffect(()=>{
  const node=element.current;if(!menu||!node)return
  const box=node.getBoundingClientRect()
  setPosition({x:Math.max(8,Math.min(menu.position.x,window.innerWidth-box.width-8)),
   y:Math.max(8,Math.min(menu.position.y,window.innerHeight-box.height-8)),ready:true})
  ;(node.querySelector<HTMLButtonElement>('button:not(:disabled)')??node).focus({preventScroll:true})
 },[menu])
 useEffect(()=>{
  if(!menu)return
  const outside=(event:Event)=>{if(!element.current?.contains(event.target as Node))dismiss(false)}
  const windowChanged=()=>dismiss(false)
  const invalidated=new MutationObserver(()=>{
   const origin=current.current?.origin
   if(origin&&(!origin.isConnected||origin.closest('[inert]')||origin.matches(':disabled')))dismiss(false)
  })
  document.addEventListener('pointerdown',outside,true)
  document.addEventListener('scroll',outside,true)
  window.addEventListener('resize',windowChanged)
  window.addEventListener('blur',windowChanged)
  invalidated.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['inert','disabled']})
  return ()=>{
   document.removeEventListener('pointerdown',outside,true);document.removeEventListener('scroll',outside,true)
   window.removeEventListener('resize',windowChanged);window.removeEventListener('blur',windowChanged);invalidated.disconnect()
  }
 },[!!menu,dismiss])
 function choose(item:ActionMenuItem){
  const live=current.current
  if(!live||live.generation!==menu?.generation||item.disabled)return
  if(!live.origin.isConnected||live.origin.closest('[inert]')||live.origin.matches(':disabled')){dismiss(false);return}
  dismiss(true);item.onSelect()
 }
 function keyboard(event:KeyboardEvent){
  if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeMenu();return}
  if(event.key==='Tab'){closeMenu();return}
  if(event.altKey||event.metaKey||event.ctrlKey)return
  const items=[...element.current!.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')]
  const index=items.indexOf(document.activeElement as HTMLButtonElement)
  if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
   event.preventDefault();event.stopPropagation()
   if(!items.length)return
   const next=event.key==='Home'?0:event.key==='End'?items.length-1:
    (index+(event.key==='ArrowDown'?1:-1)+items.length)%items.length
   items[next].focus();return
  }
  if((event.key==='Enter'||event.key===' ')&&index>=0){event.preventDefault();event.stopPropagation();choose(menu!.items.find(item=>item.id===items[index].dataset.actionId)!)}
 }
 const api=useMemo(()=>({openMenu,closeMenu,activeId:menu?.id??null}),[openMenu,closeMenu,menu?.id])
 return <MenuContext.Provider value={api}>{children}{menu&&createPortal(
  <div ref={element} className="action-menu" role="menu" aria-label={menu.label} tabIndex={-1}
   style={{left:position.x,top:position.y,visibility:position.ready?'visible':'hidden'}}
   onKeyDown={keyboard} onContextMenu={event=>event.preventDefault()}>
   {menu.items.map(item=><button key={item.id} type="button" role="menuitem" tabIndex={-1}
    data-action-id={item.id} className="action-menu-item" disabled={item.disabled}
    onClick={()=>choose(item)}>{item.label}</button>)}
  </div>,document.body)}</MenuContext.Provider>
}
