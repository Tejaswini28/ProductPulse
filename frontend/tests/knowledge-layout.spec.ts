import {test,expect} from '@playwright/test';
import fixture from './knowledge.json' with {type:'json'};
const gap=fixture.gaps[0];
const second={...gap,id:'faq-gap',product:'Balance Assist Plan',file:'product_faq.md',title:'Activation timing guidance',kind:'Missing guidance'};
const products=['Bank Account Management','Balance Assist Plan'];
const knowledge={...fixture,checked_at:'2026-09-17T15:42:00-04:00',scope:{products},gaps:[gap,second]};
for(const width of [1440,390]){
 test(`knowledge groups, filters, sources and review at ${width}px`,async({page})=>{
  let confirmed=false;
  await page.setViewportSize({width,height:1100});
  await page.route('**/api/bootstrap',r=>r.fulfill({json:{products,start:'2026-09-01',end:'2026-09-17',signals:[],runs:[],health:null,health_reviews:{},knowledge,reviews:confirmed?{[gap.id]:'Confirmed'}:{},drafts:{},approved:{},opportunities:[],explored:{}}}));
  await page.route('**/api/documents/*',r=>r.fulfill({json:{text:'Document context for review.'}}));
  await page.route('**/api/gaps/*/review',r=>{confirmed=true;return r.fulfill({json:{decision:'Confirmed'}})});
  await page.goto('/#knowledge');
  await expect(page.getByLabel('Knowledge summary')).toHaveText('4 docs checked · 2 potential gaps · 0 confirmed');
  await expect(page.getByText(/Last checked: Sep 17/)).toBeVisible();
  await expect(page.getByRole('region',{name:products[0],exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Sources checked',exact:true})).toBeVisible();
  await expect(page.getByText('Conflict',{exact:true})).toBeVisible();
  await expect(page.getByText('Missing Guidance',{exact:true})).toBeVisible();
  await page.screenshot({path:`/tmp/pulse-knowledge-layout-${width}.png`,fullPage:true});
  await page.getByLabel('Product',{exact:true}).selectOption(products[0]);
  await expect(page.getByRole('article')).toHaveCount(1);
  await expect(page.getByRole('region',{name:products[0],exact:true})).toHaveCount(0);
  await page.getByRole('article').getByRole('button',{name:'Agent Procedures',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Supporting evidence'})).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Review gap',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Review knowledge gap'})).toBeVisible();
  await page.getByRole('button',{name:'Confirm Gap',exact:true}).click();
  await expect(page.getByRole('button',{name:'Draft Update',exact:true})).toBeEnabled();
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('Knowledge summary')).toHaveText('4 docs checked · 0 potential gaps · 1 confirmed');
  await expect(page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).resolves.toBeTruthy();
  await page.getByRole('button',{name:'API Documentation',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Supporting evidence'})).toBeVisible();
 });
}

test('rewrite actions update wording and tiles track approval and rejection',async({page})=>{
 let wording='',approved='';const reviews:Record<string,string>={};
 const draft=()=>({proposed_wording:wording,reason:'Align with verified rules.',truth_ref:gap.truth_ref});
 await page.route('**/api/bootstrap',r=>r.fulfill({json:{products,start:'2026-09-01',end:'2026-09-17',signals:[],runs:[],health:null,health_reviews:{},knowledge,reviews,drafts:wording?{[gap.id]:draft()}:{},approved:approved?{[gap.id]:approved}:{},opportunities:[],explored:{}}}));
 await page.route('**/api/gaps/*/review',r=>{const id=r.request().url().split('/').at(-2)!;reviews[id]=r.request().postDataJSON().decision;return r.fulfill({json:{}})});
 await page.route('**/api/jobs',r=>{
  const body=r.request().postDataJSON();
  expect(body.gap_id).toBe(gap.id);
  if(body.feedback)expect(body.wording).toBe(wording);
  wording=body.feedback?.includes('Shorten')?'Verify before payment.':body.feedback?.includes('customers')?'Please verify your account before you pay.':body.feedback?.includes('formal')?'Verification is required prior to payment.':'You must complete verification of your bank account before making a payment.';
  approved='';return r.fulfill({json:{id:'draft-test'}});
 });
 await page.route('**/api/jobs/draft-test',r=>r.fulfill({json:{status:'completed',result:draft()}}));
 await page.route('**/api/gaps/*/approve',r=>{approved=r.request().postDataJSON().wording;return r.fulfill({json:{preview:approved}})});
 const tile=page.getByRole('article').filter({has:page.getByRole('button',{name:gap.title,exact:true})});
 const otherTile=page.getByRole('article').filter({has:page.getByRole('button',{name:second.title,exact:true})});
 await page.goto('/#knowledge');
 await expect(page.getByText('Potential gap → PM reviews',{exact:false})).toHaveCount(0);
 await expect(page.getByText('AI-powered product intelligence for Product Managers',{exact:false})).toHaveCount(0);
 await tile.getByRole('button',{name:'Review gap'}).click();
 await expect(page.getByText('Technical details',{exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Confirm Gap',exact:true}).click();
 await page.getByRole('button',{name:'Draft Update',exact:true}).click();
 await expect(page.getByLabel('Proposed replacement wording')).toHaveValue(/You must complete/);
 for(const [button,expected] of [['Shorter','Verify before payment.'],['Customer-friendly','Please verify your account before you pay.'],['More formal','Verification is required prior to payment.']]){
  await page.getByRole('button',{name:button,exact:true}).click();
  await expect(page.getByLabel('Proposed replacement wording')).toHaveValue(expected);
 }
 await page.keyboard.press('Escape');
 await expect(tile).toContainText('Draft ready');
 await tile.getByRole('button',{name:'Review gap'}).click();
 await page.getByRole('button',{name:'Approve wording',exact:true}).click();
 await page.keyboard.press('Escape');
 await expect(tile).toContainText('Update approved');
 await otherTile.getByRole('button',{name:'Review gap'}).click();
 await page.getByRole('button',{name:'Reject Gap',exact:true}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(otherTile).toContainText('Rejected');
});

for(const width of [1440,390]){
 test(`approved gap reopens with visible handoff controls at ${width}px`,async({page})=>{
  const wording='Verification is required before payment. '.repeat(80);
  await page.setViewportSize({width,height:844});
  await page.route('**/api/bootstrap',r=>r.fulfill({json:{products,start:'2026-09-01',end:'2026-09-17',signals:[],runs:[],health:null,health_reviews:{},knowledge,reviews:{[gap.id]:'Confirmed'},drafts:{[gap.id]:{proposed_wording:wording,reason:'Verification required',truth_ref:gap.truth_ref}},approved:{[gap.id]:wording},opportunities:[],explored:{}}}));
  await page.goto('/#knowledge');
  const tile=page.getByRole('article').filter({has:page.getByRole('button',{name:gap.title,exact:true})});
  await tile.getByRole('button',{name:'Review gap'}).click();
  const dialog=page.getByRole('dialog');
  await expect(dialog.getByText('Approved — ready for handoff',{exact:true})).toBeInViewport();
  await expect(dialog.getByRole('button',{name:'Download Word',exact:true})).toBeInViewport();
  await expect(dialog.getByLabel('Proposed replacement wording')).toHaveCount(0);
  await dialog.evaluate(el=>el.scrollTo(0,el.scrollHeight));
  await expect(dialog.getByRole('button',{name:'Download Word',exact:true})).toBeInViewport();
  await page.keyboard.press('Escape');
  await tile.getByRole('button',{name:'Review gap'}).click();
  await expect(dialog.getByText('Approved — ready for handoff',{exact:true})).toBeInViewport();
  await dialog.getByRole('button',{name:'Make changes',exact:true}).click();
  await dialog.getByLabel('Proposed replacement wording').fill('Edited wording requires another approval.');
  await expect(dialog.getByText('Approved — ready for handoff',{exact:true})).toHaveCount(0);
  await expect(dialog.getByRole('button',{name:'Approve wording',exact:true})).toBeInViewport();
 });
}
