import {test,expect,type Page} from '@playwright/test';
import {installFixtures} from './fixtures';
const pageErrors=new WeakMap<Page,string[]>();
test.beforeEach(async({page})=>{const errors:string[]=[];pageErrors.set(page,errors);page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error'&&/hydration|useEffect|unhandled/i.test(message.text()))errors.push(message.text())})});
test.afterEach(async({page})=>{expect(pageErrors.get(page)??[]).toEqual([])});
for(const section of ['chat','playground']){
 test(`${section}: four models are selectable when preferences fail`,async({page})=>{
  const state=await installFixtures(page,{preferencesFail:true});
  await page.goto(`/${section}`);
  const model=page.getByRole('combobox',{name:'Model',exact:true});
  await expect(model.locator('option')).toHaveCount(5);
  await model.selectOption(state.models[3].name);
  await expect(model).toHaveValue(state.models[3].name);
  await page.getByRole('textbox',{name:'Message',exact:true}).fill('Browser fixture prompt');
  await page.getByRole('textbox',{name:'Message',exact:true}).press('Enter');
  await expect(page.getByRole('log').getByText(state.reply,{exact:true})).toBeVisible();
  expect(state.conversations.size).toBe(section==='chat'?1:0);
 });
}
test('fixed chat, independent scroll and collapsible right settings work',async({page})=>{
 const state=await installFixtures(page,{longReply:true});
 await page.goto('/chat');
 await expect(page.getByRole('combobox',{name:'Model',exact:true})).toHaveValue(state.models[1].name);
 const composer=page.getByRole('textbox',{name:'Message',exact:true});
 await composer.fill('Long response fixture');await composer.press('Enter');
 await expect(page.getByRole('log').getByText('Fixture paragraph 50:',{exact:false})).toBeVisible();
 const log=page.getByRole('log');
 expect(await log.evaluate(el=>el.scrollHeight>el.clientHeight)).toBe(true);
 await log.evaluate(el=>{el.scrollTop=0});
 await expect(composer).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollHeight<=window.innerHeight+1)).toBe(true);
 await page.getByRole('button',{name:'Open inference settings',exact:true}).click();
 await expect(page.locator('#inference-settings-panel')).toBeVisible();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByRole('button',{name:'Close settings',exact:true}).click();
 await expect(page.locator('#inference-settings-panel')).toBeHidden();
 await expect(composer).toBeVisible();
 expect(await page.evaluate(()=>window.scrollY)).toBe(0);
});
test('Playground saves only when explicitly requested',async({page})=>{
 const state=await installFixtures(page);
 await page.goto('/playground');
 await expect(page.getByRole('combobox',{name:'Model',exact:true})).toHaveValue(state.models[1].name);
 await page.getByRole('textbox',{name:'Message',exact:true}).fill('Temporary prompt');
 await page.getByRole('button',{name:'Send message',exact:true}).click();
 await expect(page.getByRole('log').getByText(state.reply,{exact:true})).toBeVisible();
 expect(state.conversations.size).toBe(0);
 await page.getByRole('button',{name:'Save chat',exact:true}).click();
 await expect(page.getByText('Session saved. Open Chat to continue.')).toBeVisible();
 expect(state.conversations.size).toBe(1);
});
test('monitoring handles missing GPU without fictitious inference results',async({page})=>{
 await installFixtures(page);await page.goto('/monitoring');
 await expect(page.getByRole('heading',{name:'Host utilization'})).toBeVisible();
 await expect(page.getByText('GPU telemetry unavailable. CPU-only operation remains supported.')).toBeVisible();
 await expect(page.getByText('No recorded generations.')).toBeVisible();
});
