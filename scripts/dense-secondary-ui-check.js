async page => {
 const base='http://127.0.0.1:18767',pid='7df6a62d5da4468ea8a84e69dc56d753';
 const check=(v,m)=>{if(!v)throw Error(m)};
 let products=await(await page.request.get(base+'/api/products')).json();
 let product=products.find(p=>p.name==='验收产品 · 审批协同');
 if(!product){
  product=await(await page.request.post(base+'/api/products',{data:{name:'验收产品 · 审批协同',summary:'验收环境：展示已交付的审批及权限能力。'}})).json();
  await page.request.post(base+'/api/products/'+product.id+'/files',{multipart:{file:{name:'产品介绍.md',mimeType:'text/markdown',buffer:Buffer.from('# 产品介绍\n\n**审批协同**已交付。')}}});
 }
 const checks=[];
 for(const width of [320,390,1280]){
  await page.setViewportSize({width,height:844});
  for(const route of ['home','projects','products','workspace','projects/'+pid+'/files','projects/'+pid+'/issues']){
   await page.goto(base+'/#'+route);await page.reload();
   await page.locator('.loading').waitFor({state:'hidden'}).catch(()=>{});
   await page.waitForFunction(()=>document.querySelector('main')?.textContent.trim().length>0);
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow '+width+' '+route);
   check(await page.getByRole('button',{name:'返回上一级',exact:true}).count()===1,'single back '+route);
   await page.screenshot({path:'output/playwright/workflow/dense-'+route.replaceAll('/','-')+'-'+width+'.png'});
   checks.push(width+' '+route);
  }
 }
 await page.setViewportSize({width:390,height:844});
 await page.goto(base+'/#products');await page.getByRole('button',{name:'产品介绍.md'}).first().click();
 await page.locator('dialog .markdown h1').waitFor();
 check(await page.locator('dialog .markdown strong').innerText()==='审批协同','product markdown');
 await page.screenshot({path:'output/playwright/workflow/dense-product-preview.png'});
 await page.getByRole('button',{name:'关闭',exact:true}).click();
 await page.goto(base+'/#workspace');await page.getByRole('button',{name:'刷新',exact:true}).click();
 await page.getByRole('heading',{name:'开发日报',exact:true}).waitFor();
 check(!(await page.locator('main').innerText()).includes('代码扫描未完成'),'workspace development scan');
 return {screens:checks,product_markdown:true,workspace_scan:true};
}
