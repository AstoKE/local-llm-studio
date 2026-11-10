import {defineConfig,devices} from '@playwright/test';
import {fileURLToPath} from 'node:url';
export default defineConfig({
 testDir:'.',testMatch:'*.spec.ts',fullyParallel:false,workers:1,forbidOnly:true,
 reporter:[['list'],['html',{open:'never'}]],
 use:{baseURL:'http://127.0.0.1:3005',trace:'retain-on-failure',screenshot:'only-on-failure'},
 projects:[{name:'desktop',use:{...devices['Desktop Chrome'],viewport:{width:1440,height:900}}},{name:'mobile',use:{...devices['iPhone 13'],browserName:'chromium'}}],
 webServer:{command:'npm run start -- --port 3005',cwd:fileURLToPath(new URL('../../apps/web',import.meta.url)),url:'http://127.0.0.1:3005/login',reuseExistingServer:false,timeout:120000,env:{STUDIO_LAN_MODE:'false',STUDIO_WEB_ORIGIN:'http://127.0.0.1:3005',NEXT_TELEMETRY_DISABLED:'1'}}
});
