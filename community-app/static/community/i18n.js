/* One shared catalog for public UI, quiz content and transactional messages. */
const catalogs = JSON.parse(document.getElementById('translations').textContent);
let language = document.documentElement.lang || 'it';
const reverseTranslations = new Map();
for (const catalog of Object.values(catalogs)) for (const [source, translated] of Object.entries(catalog)) reverseTranslations.set(translated, source);
const patterns = [
 [/^Esci \((.*)\)$/,'Esci ({name})',['name']],
 [/^Ciao, (.*)\.$/,'Ciao, {name}.',['name']],
 [/^(\d+) quiz completati$/,'{count} quiz completati',['count']],
 [/^Completato · (\d+) punti$/,'Completato · {score} punti',['score']],
 [/^Inizia (.*)$/,'Inizia {title}',['title']],
 [/^Domanda (\d+) di 3$/,'Domanda {number} di 3',['number']],
 [/^Hai risposto correttamente a (\d+) domande su 3\.$/,'Hai risposto correttamente a {count} domande su 3.',['count']],
 [/^Il tuo profilo: (.*)$/,'Il tuo profilo: {name}',['name']],
];
function t(source, values={}) {
 let key = reverseTranslations.get(source) || source;
 if (!catalogs.en[key]) {
  for (const [pattern, template, fields] of patterns) {
   const match=key.match(pattern);
   if(match){key=template; values=Object.fromEntries(fields.map((f,i)=>[f,f==='title'?t(match[i+1]):match[i+1]]));break;}
  }
 }
 let translated=(catalogs[language] || {})[key] || key;
 for(const [name,value] of Object.entries(values)) translated=translated.replaceAll('{'+name+'}',value);
 return translated;
}
function translateText(text) {
 const source=text.trim(); if(!source)return text;
 let output=t(source);
 // Decorations and score units outside elements retain the original layout.
 if(output===source && source.endsWith(' ↗'))output=t(source.slice(0,-2))+' ↗';
 if(output===source && source.endsWith(' →'))output=t(source.slice(0,-2))+' →';
 if(output===source && /^(?:\d+\s*)?\/ 30 punti$/.test(source))output=source.replace('punti',t('punti'));
 if(output===source){const key=Object.keys(catalogs.en).find(k=>k.toUpperCase()===source);if(key)output=t(key).toUpperCase();}
 return text.replace(source,output);
}
function translateTree(root) {
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
 for(const node of nodes)if(!['SCRIPT','STYLE'].includes(node.parentElement?.tagName))node.textContent=translateText(node.textContent);
 root.querySelectorAll('[aria-label],[title],[placeholder],[alt]').forEach(el=>{
  for(const attr of ['aria-label','title','placeholder','alt'])if(el.hasAttribute(attr))el.setAttribute(attr,t(el.getAttribute(attr)));
 });
}
function translateHTML(html){const template=document.createElement('template');template.innerHTML=html;translateTree(template.content);return template.innerHTML;}
// Keep canonical copies of static chrome; changing language never translates user input.
const chromeNodes=[];
const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
while(walker.nextNode()){const node=walker.currentNode;if(!['SCRIPT','STYLE'].includes(node.parentElement?.tagName)&&node.textContent.trim())chromeNodes.push([node,node.textContent]);}
const chromeAttrs=[...document.querySelectorAll('[aria-label],[title]')].flatMap(el=>['aria-label','title'].filter(a=>el.hasAttribute(a)).map(a=>[el,a,el.getAttribute(a)]));
function translateChrome(){
 document.documentElement.lang=language;
 for(const [node,source] of chromeNodes)if(node.isConnected)node.textContent=translateText(source);
 for(const [el,attr,source] of chromeAttrs)el.setAttribute(attr,t(source));
 document.querySelectorAll('[data-lang]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.lang===language)));
 document.querySelector('[data-site-return]').href='https://ernest-project.eu/'+(language==='en'?'':language+'/')+'index.html';
 document.querySelector('[data-cookie-policy]').href='https://ernest-project.eu/'+(language==='en'?'':language+'/')+'cookie-policy-eu.html';
}
translateChrome();
