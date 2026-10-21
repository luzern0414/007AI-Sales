import {createRequire} from 'node:module';
import {writeFile,rename,unlink} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
const require=createRequire(new URL('../web/package.json',import.meta.url));
const {chromium}=require('playwright');
let source='';for await(const chunk of process.stdin)source+=chunk;
const browser=await chromium.launch({channel:process.env.PDF_BROWSER_CHANNEL||'chrome',headless:true});
const temporary=process.argv[2]+'.'+randomUUID()+'.tmp';
try{const page=await browser.newPage();await page.route('**/*',route=>route.abort());await page.setContent(source,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);await page.pdf({path:temporary,format:'A4',printBackground:true,displayHeaderFooter:true,headerTemplate:'<span></span>',footerTemplate:'<div style="font-size:9px;width:100%;text-align:center;color:#666"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',preferCSSPageSize:true});await rename(temporary,process.argv[2])}finally{await browser.close();await unlink(temporary).catch(()=>{})}
