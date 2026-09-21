import {test,expect} from '@playwright/test';

// Isolate UI checks from agent calls and the optional local demo dataset.
test.use({baseURL:process.env.PULSE_UI_URL || 'http://127.0.0.1:8000'});
const products=['Bank Account Management','Payments','Transfers'];
const health={status:'completed',run_id:'ui-preview',scope:{products,start:'2026-09-01',end:'2026-09-17'},report:{summary:'Review product health.',products:products.map((product_name,i)=>({product_name,status:i===0?'Needs Attention':i===1?'Monitor':'No Significant Issue',summary:i===0?'Some customers could not verify their bank account.':'Product performance is within the review window.',evidence_refs:[],limitations:[],issues:i===0?[{id:'issue-1',finding:'Bank verification failures need a closer look.',date:'2026-09-03',severity:'High',affected_components:[],evidence_refs:[],recommendation:'Review customer verification attempts.',investigate:true}]:[]}))},evidence:{}};
const bootstrap={products,start:'2026-09-01',end:'2026-09-17',signals:[],runs:[],knowledge:null,reviews:{},drafts:{},approved:{},opportunities:[],explored:{},health,health_reviews:{}};

for(const width of [1440,390,320]){
 test(`workspace navigation and detail panels at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  await page.route('**/api/bootstrap',r=>r.fulfill({json:bootstrap}));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Product Health',exact:true})).toBeVisible();
  await expect(page.getByLabel('Product health summary')).toBeVisible();
  await expect(page.getByRole('button',{name:'Run Health Scan',exact:true})).toBeEnabled();
  await page.screenshot({path:`/tmp/pulse-theme-health-${width}.png`,fullPage:true});
  await page.getByRole('button',{name:/Review Signals for/}).first().click();
  await expect(page.getByRole('dialog',{name:'Review finding'})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button',{name:/Review Signals for/}).first()).toBeFocused();
  await page.getByRole('button',{name:'Investigations',exact:true}).click();
  await page.getByRole('button',{name:'New investigation',exact:true}).click();
  await page.getByLabel('Complaint or issue').fill('Verification failed');
  await expect(page.getByRole('button',{name:'Investigate',exact:true})).toBeEnabled();
  await expect(page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).resolves.toBeTruthy();
  await page.screenshot({path:`/tmp/pulse-theme-form-${width}.png`,fullPage:true});
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Knowledge Health',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Ready to check your guidance'})).toBeVisible();
  await page.getByLabel('Product',{exact:true}).selectOption(products[0]);
  await expect(page.getByRole('button',{name:'Check Knowledge Consistency',exact:true})).toBeEnabled();
  await expect(page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).resolves.toBeTruthy();
 });
}
test('health scan empty state preserves the explicit scan action',async({page})=>{
 await page.route('**/api/bootstrap',r=>r.fulfill({json:{...bootstrap,health:null}}));
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'Start with a health scan'})).toBeVisible();
 await expect(page.getByLabel('Product health summary')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Run Health Scan',exact:true})).toBeEnabled();
});

test('completed scan renders metric rows, evidence trends, filters and insights',async({page})=>{
 let scanned=false;
 const evidence={
  old:{evidence_id:'old',product_name:products[0],signal_type:'product_metric',metric_name:'Verification Success Rate',timestamp:'2026-08-30T12:00:00',value:50,baseline:95},
  first:{evidence_id:'first',product_name:products[0],signal_type:'product_metric',metric_name:'Verification Success Rate',timestamp:'2026-09-02T12:00:00',value:80,baseline:95},
  last:{evidence_id:'last',product_name:products[0],signal_type:'product_metric',metric_name:'Verification Success Rate',timestamp:'2026-09-03T12:00:00',value:82,baseline:95},
  api:{evidence_id:'api',product_name:products[0],signal_type:'api_metric',metric_name:'API Error Rate',timestamp:'2026-09-03T12:00:00',value:4.2,baseline:1},
  complaint:{evidence_id:'complaint',product_name:products[0],signal_type:'complaint',timestamp:'2026-09-03T12:00:00',complaint_text:'Verification failed'},
 };
 const result={...health,evidence};
 await page.route('**/api/bootstrap',r=>r.fulfill({json:{...bootstrap,health:scanned?result:null}}));
 await page.route('**/api/jobs',async r=>{expect(r.request().postDataJSON().kind).toBe('health');await r.fulfill({json:{id:'scan-layout'}})});
 await page.route('**/api/jobs/scan-layout',r=>{scanned=true;return r.fulfill({json:{id:'scan-layout',status:'completed',result}})});
 await page.goto('/');
 await page.getByRole('button',{name:'Run Health Scan',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Products (3)'})).toBeVisible();
 const row=page.getByRole('article').filter({has:page.getByRole('button',{name:products[0],exact:true})});
 await expect(row.getByText('Latest: 82% · Sep 3',{exact:true})).toBeVisible();
 await expect(row.getByText('API Health',{exact:true})).toBeVisible();
 await expect(row.getByText('API Error Rate',{exact:true})).toHaveCount(0);

 await expect(page.getByRole('complementary',{name:'Scan insights'})).toBeVisible();
 await page.screenshot({path:'/tmp/pulse-health-rows.png',fullPage:true});
 await page.getByRole('button',{name:'1 Needs Attention',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Products (1)'})).toBeVisible();
 await page.getByRole('button',{name:'Show all',exact:true}).click();
 await page.getByLabel('Sort by').selectOption('name');
 await expect(page.getByRole('article').first()).toContainText(products[0]);
 await page.getByRole('button',{name:'Review Knowledge Health',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Ready to check your guidance'})).toBeVisible();
});

for(const origin of ['health','knowledge'] as const){
 test(`${origin} progress stays on the page where the job started`,async({page})=>{
  let polls=0;
  await page.route('**/api/bootstrap',r=>r.fulfill({json:bootstrap}));
  await page.route('**/api/jobs',r=>r.fulfill({json:{id:'background-job'}}));
  await page.route('**/api/jobs/background-job',r=>{polls++;return r.fulfill({json:{status:'running',step:'Reading product context'}})});
  await page.goto('/#'+origin);
  await page.getByRole('button',{name:origin==='health'?'Run Health Scan':'Check Knowledge Consistency',exact:true}).click();
  const message=page.getByText(origin==='health'?'Reviewing product health…':'Comparing product guidance…',{exact:true});
  await expect(message).toBeVisible();
  await page.getByRole('button',{name:'Investigations',exact:true}).click();
  await expect(message).toHaveCount(0);
  const before=polls;
  await expect.poll(()=>polls).toBeGreaterThan(before);
  await expect(message).toHaveCount(0);
  await page.getByRole('button',{name:origin==='health'?/^Knowledge Health/:/^Product Health/}).click();
  await expect(message).toHaveCount(0);
  await page.getByRole('button',{name:origin==='health'?/^Product Health/:/^Knowledge Health/}).click();
  await expect(message).toBeVisible();
 });
}
