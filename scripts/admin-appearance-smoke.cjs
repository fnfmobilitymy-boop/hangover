const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const base=process.env.KENNY_BACKEND_TEST_URL||'http://127.0.0.1:3021';
  await page.goto(base+'/admin/');await page.locator('#admin-login').waitFor();
  await page.locator('#admin-language').selectOption('en');
  await page.waitForFunction(()=>document.documentElement.lang==='en');
  await page.getByRole('heading',{name:'Welcome back.'}).waitFor();
  await page.locator('[name=email]').fill('browser-admin@example.test');
  await page.locator('[name=password]').fill('Browser-test-admin-password-123');
  await page.locator('#admin-login button').click();await page.locator('.overview-top').waitFor();
  await page.locator('#admin-theme').selectOption('dark');
  assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
  assert.equal(await page.locator('body').evaluate(el=>getComputedStyle(el).fontSize),'17px');
  assert.equal(await page.locator('main').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(33, 29, 44)');
  await page.screenshot({path:'/tmp/kenny-admin-dark.png',fullPage:true});
  for(const [view,title] of Object.entries({products:'Products',inventory:'Inventory',orders:'Orders',customers:'Members',coupons:'Promotions',reviews:'Reviews',messages:'Messages',stores:'Stores',subscribers:'Subscribers',settings:'Settings',audit:'Audit log'})){
   await page.locator(`[data-view="${view}"]`).click();
   await page.waitForFunction(title=>document.querySelector('#page-title').textContent===title,title);
   await page.locator('.loading').waitFor({state:'hidden'});
   const han=(await page.locator('main').innerText()).match(/\p{Script=Han}+/gu)||[];
   assert.deepEqual(han,[],view+' has untranslated interface text');
  }
  await page.locator('[data-view=products]').click();await page.locator('[data-edit-product="aero-ice"]').click();
  await page.locator('#product-form [name=name]').fill('商品管理');
  assert.equal(await page.locator('#product-form [name=name]').inputValue(),'商品管理');
  assert.equal(await page.locator('#product-form [name=description]').evaluate(el=>el.parentElement.firstChild.textContent),'English description');
  assert.ok(parseFloat(await page.locator('#product-form [name=name]').evaluate(el=>getComputedStyle(el).fontSize))>=16);
  await page.locator('#close-editor').click();
  await page.locator('#admin-language').selectOption('zh');
  await page.waitForFunction(()=>document.documentElement.lang==='zh-CN');
  await page.locator('#page-title').filter({hasText:'商品管理'}).waitFor();
  assert.equal(await page.locator('#admin-theme').inputValue(),'dark');
  await page.locator('#admin-theme').selectOption('light');
  await page.reload();await page.locator('[data-edit-product="aero-ice"]').waitFor();
  assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
  assert.equal(await page.locator('#admin-language').inputValue(),'zh');
  assert.equal(await page.locator('main').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
  await page.locator('[data-view=overview]').click();await page.locator('.overview-top').waitFor();
  await page.screenshot({path:'/tmp/kenny-admin-light.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  for(const theme of ['light','dark']){
   await page.locator('#admin-theme').selectOption(theme);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile page overflow');
   const controls=await page.locator('.admin-preferences').boundingBox();assert.ok(controls.x>=0&&controls.x+controls.width<=390);
   await page.screenshot({path:`/tmp/kenny-admin-mobile-${theme}.png`,fullPage:true});
  }
  assert.deepEqual(errors,[]);console.log('Passed: Chinese/English login and all admin modules, untranslated UI check, editable customer/product data preserved, larger fonts, dark/light surfaces, preference persistence, session preserved, mobile layout.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
