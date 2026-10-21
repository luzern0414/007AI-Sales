async page => {
 const base='http://127.0.0.1:8765';const check=(v,m)=>{if(!v)throw Error(m)};
 const projects=await(await page.request.get(base+'/api/projects')).json();
 const project=projects.find(p=>/科创|KeChuang/i.test(p.name))||projects[0];
 const screens=[];
 for(const width of [320,390,1280]){
  await page.setViewportSize({width,height:844});
  for(const route of ['home','projects','projects/'+project.id,'projects/'+project.id+'/files','products','workspace']){
   await page.goto(base+'/#'+route);await page.reload();
   await page.waitForFunction(()=>document.querySelector('main')?.textContent.trim().length>0);
   await page.locator('.loading').waitFor({state:'hidden'}).catch(()=>{});
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow '+width+' '+route);
   check(await page.getByRole('button',{name:'返回上一级'}).count()===1,'back button');
   await page.screenshot({path:'output/playwright/workflow/normal-dense-'+route.replaceAll('/','-')+'-'+width+'.png'});
   screens.push(width+' '+route);
  }
 }
 await page.setViewportSize({width:390,height:844});
 await page.goto(base+'/#projects/'+project.id);await page.locator('.timeline-entry').first().waitFor();
 const heights=await page.locator('.timeline-entry').evaluateAll(es=>es.slice(0,5).map(e=>Math.round(e.getBoundingClientRect().height)));
 const attachments=page.locator('.timeline-detail > summary');
 if(await attachments.count()){
  await attachments.first().click();
  const source=page.locator('.timeline-detail[open] .attachment').first();
  if(await source.count()){await source.click();await page.locator('dialog .preview-toolbar').waitFor();await page.screenshot({path:'output/playwright/workflow/normal-dense-preview.png'});await page.getByRole('button',{name:'关闭',exact:true}).click();}
 }
 return {projects:projects.length,screens,first_timeline_heights:heights,mode:'read-only'};
}
