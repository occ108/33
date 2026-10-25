const {chromium}=require('/opt/codex/cua_node/lib/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});global.qaPage=page;page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://localhost:8503/?lang=es');await page.getByRole('button',{name:'Comprobar mediciones',exact:true}).waitFor();
 await page.getByRole('combobox',{name:'Componente',exact:true}).click();await page.getByRole('option',{name:'Neumáticos',exact:true}).click();
 await page.getByRole('spinbutton',{name:'Profundidad de dibujo [mm]',exact:true}).waitFor();await page.waitForTimeout(1200);
 await page.getByRole('textbox',{name:'Marca',exact:true}).fill('Tesla');
 await page.getByRole('textbox',{name:'Modelo',exact:true}).fill('Model 3');
 await page.getByRole('textbox',{name:'Versión / motor / generación',exact:true}).fill('2024+');
 await page.getByText('Estados Unidos',{exact:true}).click();
 await page.getByText('Circulación con lluvia o calzada mojada',{exact:true}).click();
 await page.getByText(/^He comprobado en el enlace/).click();
 await page.getByRole('spinbutton',{name:'Profundidad de dibujo [mm]',exact:true}).fill('2.5');
 await page.screenshot({path:'/tmp/manual-before-submit.png',fullPage:true});await page.getByRole('button',{name:'Comprobar mediciones',exact:true}).click();
 await page.getByText('Por debajo de la recomendación del fabricante para estas condiciones.',{exact:false}).waitFor();
 const results=[];
 for(const lang of ['es','en','de']){
  await page.getByText(({es:'Español',en:'English',de:'Deutsch'})[lang],{exact:true}).click();
  await page.getByRole('button',{name:({es:'Comprobar mediciones',en:'Check measurements',de:'Messwerte prüfen'})[lang],exact:true}).waitFor();
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});
   await page.locator('[data-testid="stMain"]').evaluate(el=>el.scrollTop=0);await page.screenshot({path:`reports/manual-fabricantes/${lang}-${width}.png`,fullPage:true});
   await page.getByRole('heading',{name:({es:'Resultado de tus mediciones',en:'Your measurement results',de:'Ergebnisse Ihrer Messungen'})[lang],exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:`reports/manual-fabricantes/${lang}-${width}-results.png`,fullPage:true});
   results.push({lang,width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),uploaders:await page.locator('[data-testid="stFileUploader"]').count(),reading:await page.getByRole('spinbutton',{name:({es:'Profundidad de dibujo [mm]',en:'Tyre tread depth [mm]',de:'Reifenprofiltiefe [mm]'})[lang],exact:true}).inputValue()});
  }
 }
 require('fs').writeFileSync('reports/manual-fabricantes/browser.json',JSON.stringify({results,errors},null,2));await browser.close();
})().catch(async e=>{console.error(e);if(global.qaPage)await global.qaPage.screenshot({path:'/tmp/manual-error.png',fullPage:true});process.exit(1)});
