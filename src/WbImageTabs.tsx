import {useId, useLayoutEffect, useRef} from 'react'
import type {KeyboardEvent, ReactNode} from 'react'
import type {ImageAsset} from './types'
import './wb-image-tabs.css'

interface Props {
 images: ImageAsset[]
 activeId?: string
 onSelect: (id: string) => void
 disabled?: boolean
 children: ReactNode
}

export default function WbImageTabs({images, activeId, onSelect, disabled, children}: Props) {
 const id = useId()
 const panelId = `${id}-panel`
 const tabId = (imageId: string) => `${id}-tab-${imageId}`
 const strip = useRef<HTMLDivElement>(null)
 const activeTab = useRef<HTMLButtonElement>(null)

 useLayoutEffect(() => {
  const container = strip.current
  const button = activeTab.current
  if (!container || !button) return
  const range = container.getBoundingClientRect()
  const tab = button.getBoundingClientRect()
  // Reveal the selected tab without moving the surrounding workspace.
  if (tab.left < range.left) container.scrollLeft += tab.left - range.left
  else if (tab.right > range.right) container.scrollLeft += tab.right - range.right
 }, [activeId, images.length])

 function switchWithKeyboard(event: KeyboardEvent<HTMLButtonElement>, index: number) {
  if (event.altKey || event.ctrlKey || event.metaKey) return
  let next: number
  if (event.key === 'ArrowLeft') next = (index + images.length - 1) % images.length
  else if (event.key === 'ArrowRight') next = (index + 1) % images.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = images.length - 1
  else return
  event.preventDefault()
  if (index === next) return
  const imageId = images[next].id
  onSelect(imageId)
  event.currentTarget.ownerDocument.getElementById(tabId(imageId))?.focus({preventScroll: true})
 }

 return <>
  {images.length > 0 && <div className="wb-image-tabs" role="tablist" aria-label="原始图像" ref={strip}>
   {images.map((image, index) => {
    const selected = image.id === activeId
    const pageLabel = image.name.match(/^(.*) · (第 \d+ 页)$/)
    return <button type="button" className="wb-image-tab" key={image.id} id={tabId(image.id)}
     ref={selected ? activeTab : undefined} role="tab" aria-selected={selected} aria-controls={panelId}
     aria-label={image.name} title={image.name} disabled={disabled} tabIndex={selected ? 0 : -1}
     onClick={() => {if (!selected) onSelect(image.id)}} onKeyDown={event => switchWithKeyboard(event, index)}>
     <span className="wb-image-tab-name">{pageLabel?.[1] ?? image.name}</span>
     {pageLabel && <span className="wb-image-tab-page">{pageLabel[2]}</span>}
    </button>
   })}
  </div>}
  <div id={panelId} role={activeId ? 'tabpanel' : undefined} aria-labelledby={activeId ? tabId(activeId) : undefined}>
   {children}
  </div>
 </>
}
