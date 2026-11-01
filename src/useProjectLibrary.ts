import {useCallback,useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import type {LibraryEntry} from './types'
export default function useProjectLibrary(){
 const [entries,setEntries]=useState<LibraryEntry[]>([]),[error,setError]=useState('')
 const generation=useRef(0)
 const refresh=useCallback(async()=>{
  const token=++generation.current
  try{const rows=await callEngine<LibraryEntry[]>('library_list');if(token===generation.current){setEntries(rows);setError('')}}catch(e){if(token===generation.current)setError(String(e))}
 },[])
 const remember=useCallback(async(path:string,entryId?:string)=>{
  try{const entry=await callEngine<LibraryEntry>('library_register',{path,entry_id:entryId});await refresh();return entry}catch(e){setError(String(e));return undefined}
 },[refresh])
 useEffect(()=>{refresh();return()=>{generation.current++}},[refresh])
 return {entries,error,refresh,remember}
}
