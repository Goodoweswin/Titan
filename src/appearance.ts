export const interfaceColors = [
 {id:'neutral',name:'默认灰',color:'#555753'},
 {id:'blue',name:'雾蓝',color:'#4167c4'},
 {id:'green',name:'松绿',color:'#28735b'},
 {id:'violet',name:'鸢紫',color:'#7354ad'},
 {id:'rose',name:'暖玫',color:'#a44969'},
] as const
export type InterfaceColor = typeof interfaceColors[number]['id']
const storageKey = 'titan-interface-color'

export function readInterfaceColor(): InterfaceColor {
 try {
  const saved = localStorage.getItem(storageKey)
  return interfaceColors.find(color => color.id === saved)?.id ?? 'neutral'
 } catch { return 'neutral' }
}

export function applyInterfaceColor(color: InterfaceColor) {
 document.documentElement.dataset.interfaceColor = color
}

export function saveInterfaceColor(color: InterfaceColor): boolean {
 applyInterfaceColor(color)
 try { localStorage.setItem(storageKey, color); return true }
 catch { return false }
}
