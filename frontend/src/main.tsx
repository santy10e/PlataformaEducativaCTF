import React from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './app/App'
import './style.css'
import './workspace.css'
import './education.css'

const root = document.getElementById('root')
if (root) createRoot(root).render(<React.StrictMode><App /></React.StrictMode>)
