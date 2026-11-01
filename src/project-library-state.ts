import type {Project} from './types'
import {mergeSaved} from './state'
export function sameProjectContext(a:Project|null|undefined,b:Project|null|undefined){return !!a&&!!b&&a.id===b.id&&a.project_path===b.project_path}
export function mergeSavedFrom(current:Project|null,base:Project,saved:Project):Project|null{return sameProjectContext(current,base)?mergeSaved(current,saved):current}
