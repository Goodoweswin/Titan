import type {ImageAsset} from './types'
export function displayStyle(asset:ImageAsset){return {filter:asset.display_inverted?'invert(1)':'none'}}
