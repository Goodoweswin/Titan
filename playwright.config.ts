import {defineConfig} from '@playwright/test'
export default defineConfig({testDir:'tests/browser',timeout:60000,workers:1,
 use:{baseURL:'http://127.0.0.1:1420',channel:'chromium',viewport:{width:1440,height:1000},trace:'retain-on-failure'},
 webServer:{command:'TITAN_INTEGRATION=1 npm run dev',url:'http://127.0.0.1:1420',reuseExistingServer:false,timeout:30000}})
