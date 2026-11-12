import React from 'react'
import {createRoot} from 'react-dom/client'
import App from './App'
import './style.css'
import './chrome.css'
import './sidebar.css'
import './appearance.css'
import './workspace-navigation.css'
import './account-appearance.css'
import './account.css'
import {applyInterfaceColor,readInterfaceColor} from './appearance'
applyInterfaceColor(readInterfaceColor())
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
