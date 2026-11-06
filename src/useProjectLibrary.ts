import {useCallback,useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import type {LibraryEntry,LibraryResume,LibraryWorkspace} from './types'

export default function useProjectLibrary(){
 const [workspace,setWorkspace]=useState<LibraryWorkspace>({projects:[],entries:[]})
 const [error,setError]=useState('')
 const generation=useRef(0)
 const refresh=useCallback(async()=>{
  const token=++generation.current
  try{
   const next=await callEngine<LibraryWorkspace>('library_workspace')
   if(token===generation.current){setWorkspace(next);setError('')}
  }catch(e){if(token===generation.current)setError(String(e))}
 },[])
 const change=useCallback(async <T,>(command:string,payload:object):Promise<T>=>{
  const result=await callEngine<T>(command,payload)
  await refresh()
  return result
 },[refresh])
 const remember=useCallback(async(path:string,options:{entry_id?:string;source_entry_id?:string;touch_opened?:boolean}={})=>{
  try{return await change<LibraryEntry>('library_register',{path,...options})}
  catch(e){setError(String(e));return undefined}
 },[change])
 const resume=useCallback(async(entryId:string,value:LibraryResume)=>{
  try{await change('library_set_resume',{entry_id:entryId,resume:value})}
  catch(e){setError(String(e))}
 },[change])
 useEffect(()=>{void refresh();return()=>{generation.current++}},[refresh])
 return {...workspace,error,refresh,remember,change,resume}
}

export type ProjectLibraryModel=ReturnType<typeof useProjectLibrary>
