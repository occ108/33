const {chromium}=require('/opt/codex/cua_node/lib/node_modules/playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox'],headless:true});const results=[];const errors=[];
 for(const lang of ['es','en','de']){
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://localhost:8504/?lang='+lang);
  const label={es:'Parque europeo y estadounidense: cobertura verificada',en:'European and US fleet: verified coverage',de:'Europäischer und US-Fahrzeugmarkt: verifizierte Abdeckung'}[lang];
  await page.getByText(label,{exact:true}).click();await page.getByText('Renault Kangoo VAN',{exact:true}).waitFor();
  const captions=await page.getByTestId('stCaptionContainer').allTextContents();const country={es:'Francia',en:'France',de:'Frankreich'}[lang];
  if(!captions.some(s=>s.includes(country)&&s.includes(lang==='en'?'24,405':'24.405')))throw Error('France sales attribution missing '+lang);
  if(await page.getByTestId('stException').count())throw Error('Streamlit exception');
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});await page.getByText(label,{exact:true}).scrollIntoViewIfNeeded();
   await page.screenshot({path:`reports/fleet2025/${lang}-${width}.png`});
   results.push({lang,width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),uploaders:await page.getByTestId('stFileUploader').count(),correctFranceAttribution:true});
  }
  await page.close();
 }
 await browser.close();if(results.some(r=>r.overflow||r.uploaders)||errors.length)throw Error('UI QA failed');fs.writeFileSync('reports/fleet2025/browser.json',JSON.stringify({results,errors},null,2));
})().catch(e=>{console.error(e);process.exit(1)});
