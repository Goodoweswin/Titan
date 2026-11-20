import {useId,type ComponentProps} from 'react'

type Props=ComponentProps<'image'>&{inverted?:boolean}

export default function WbPreviewImage({inverted,...props}:Props){
 const filterId=useId()
 return <>
  {inverted&&<defs>
   <filter id={filterId} x="0%" y="0%" width="100%" height="100%" colorInterpolationFilters="sRGB">
    <feComponentTransfer>
     <feFuncR type="table" tableValues="1 0"/>
     <feFuncG type="table" tableValues="1 0"/>
     <feFuncB type="table" tableValues="1 0"/>
    </feComponentTransfer>
   </filter>
  </defs>}
  <image {...props} filter={inverted?`url(#${filterId})`:undefined}/>
 </>
}
