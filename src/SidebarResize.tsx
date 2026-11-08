import {useEffect, useLayoutEffect, useRef, useState} from 'react'

const storageKey = 'titan-sidebar-width'
const minWidth = 200
const maxWidth = 420
const compactWidth = 220
const wideWidth = 232
const keyboardStep = 16

type Drag = {pointerId: number; startX: number; startWidth: number; width: number}

// Keep these bounds aligned with the desktop rules in project-workspace.css.
function limitFor(viewport: number) {
 return Math.max(compactWidth, Math.min(maxWidth, viewport - 780))
}

function widthFor(requested: number | null, viewport: number) {
 const defaultWidth = viewport <= 1100 ? compactWidth : wideWidth
 return Math.max(minWidth, Math.min(limitFor(viewport), requested ?? defaultWidth))
}

function readWidth() {
 try {
  const width = Number(localStorage.getItem(storageKey))
  if (Number.isInteger(width) && width >= minWidth && width <= maxWidth) return width
 } catch {
  // Resizing is still available when preferences cannot be read.
 }
 return null
}

export default function SidebarResize({sidebarId}: {sidebarId: string}) {
 const handle = useRef<HTMLDivElement>(null)
 const drag = useRef<Drag | null>(null)
 const [preference, setPreference] = useState(readWidth)
 const [dragWidth, setDragWidth] = useState<number | null>(null)
 const [viewport, setViewport] = useState(() => window.innerWidth)
 const requestedWidth = dragWidth ?? preference
 const width = widthFor(requestedWidth, viewport)

 useEffect(() => {
  const measure = () => setViewport(window.innerWidth)
  window.addEventListener('resize', measure)
  return () => window.removeEventListener('resize', measure)
 }, [])

 useLayoutEffect(() => {
  const workspace = handle.current?.closest<HTMLElement>('.titan-workspace')
  if (!workspace || requestedWidth === null) return
  workspace.style.setProperty('--sidebar-user-width', `${requestedWidth}px`)
  return () => { workspace.style.removeProperty('--sidebar-user-width') }
 }, [requestedWidth])

 function remember(value: number | null) {
  setPreference(value)
  try {
   if (value === null) localStorage.removeItem(storageKey)
   else localStorage.setItem(storageKey, String(value))
  } catch {
   // Keep the in-memory width for this window.
  }
 }

 function finish(pointerId: number, save: boolean) {
  const active = drag.current
  if (!active || active.pointerId !== pointerId) return
  drag.current = null
  setDragWidth(null)
  if (save && active.width !== active.startWidth) remember(widthFor(active.width, window.innerWidth))
 }

 return <div
  ref={handle}
  className="sidebar-resize"
  data-dragging={dragWidth === null ? undefined : true}
  role="separator"
  tabIndex={0}
  aria-label="调整左栏宽度"
  aria-controls={sidebarId}
  aria-orientation="vertical"
  aria-valuemin={minWidth}
  aria-valuemax={limitFor(viewport)}
  aria-valuenow={width}
  aria-valuetext={`${width} 像素`}
  title="拖动调整左栏宽度，双击恢复默认"
  onPointerDown={event => {
   if (event.button !== 0 || drag.current) return
   event.preventDefault()
   event.currentTarget.focus({preventScroll:true})
   event.currentTarget.setPointerCapture(event.pointerId)
   const startWidth = widthFor(preference, window.innerWidth)
   drag.current = {pointerId:event.pointerId, startX:event.clientX, startWidth, width:startWidth}
   setDragWidth(startWidth)
  }}
  onPointerMove={event => {
   const active = drag.current
   if (!active || active.pointerId !== event.pointerId) return
   active.width = widthFor(active.startWidth + event.clientX - active.startX, window.innerWidth)
   setDragWidth(active.width)
  }}
  onPointerUp={event => finish(event.pointerId, true)}
  onPointerCancel={event => finish(event.pointerId, false)}
  onLostPointerCapture={event => finish(event.pointerId, false)}
  onDoubleClick={() => remember(null)}
  onKeyDown={event => {
   if (drag.current) {
    if (event.key === 'Escape') {
     event.preventDefault()
     const {pointerId} = drag.current
     finish(pointerId, false)
     if (event.currentTarget.hasPointerCapture(pointerId)) event.currentTarget.releasePointerCapture(pointerId)
    }
    return
   }
   const currentViewport = window.innerWidth
   const currentWidth = widthFor(preference, currentViewport)
   const steps: Record<string, number> = {
    ArrowLeft:currentWidth-keyboardStep, ArrowRight:currentWidth+keyboardStep,
    Home:minWidth, End:limitFor(currentViewport),
   }
   if (event.key === 'Enter') {
    event.preventDefault()
    remember(null)
   } else if (Object.hasOwn(steps,event.key)) {
    event.preventDefault()
    const next = widthFor(steps[event.key], currentViewport)
    if (next !== currentWidth) remember(next)
   }
  }}
 />
}
