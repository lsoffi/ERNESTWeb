let quizzes=[], passport=[], accountsEnabled=true;
let passportOpen=false, passportSound=true, pageAudioContext=null;
let filter='Tutti',name='',completed={},current=null,index=0,selected=null,checked=false,points=0;
const app=document.querySelector('#app'),auth=document.querySelector('#auth');
const escapeHTML=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const total=()=>Object.values(completed).reduce((a,b)=>a+b,0);
let mode='login', attempt=null, busy=false;
async function api(path,data){
 const csrf=document.cookie.split('; ').find(v=>v.startsWith('csrftoken='))?.split('=')[1];
 const response=await fetch('/api/'+path+'/',{method:data?'POST':'GET',credentials:'same-origin',headers:data?{'Content-Type':'application/json','X-CSRFToken':csrf}: {},body:data?JSON.stringify(data):undefined});
 let value;try{value=await response.json()}catch{throw Error(t('Connessione non disponibile. Riprova.'))}
 if(!response.ok)throw Error(value.error||t('Operazione non riuscita. Riprova.'));return value;
}
function sync(value){if(value.passport)passport=value.passport;if(name!==value.name)passportOpen=false;name=value.name;completed=value.completed;document.querySelector('[data-nav=leaderboard]').hidden=!name;document.querySelector('#access').textContent=name?t('Esci ({name})',{name}):t('Accedi')+' ↗'}
function openAuth(){document.querySelector('#auth-fields').hidden=false;document.querySelector('#registration-success').hidden=true;if(!accountsEnabled){alert(t('Gli account saranno disponibili prossimamente. Intanto puoi provare tutti i quiz.'));return;}document.querySelector('#auth-error').textContent='';document.querySelector('#mail-preview').hidden=true;auth.showModal()}
document.querySelector('#access').onclick=async()=>{if(!name)return openAuth();try{sync(await api('logout',{}));current=null;location.hash='home';render()}catch(e){alert(e.message)}};
document.querySelector('.close').onclick=()=>auth.close();
for(const m of ['login','register'])document.querySelector('#'+m+'-tab').onclick=()=>{mode=m;document.querySelector('#nickname-label').hidden=m!=='register';document.querySelector('#nickname').required=m==='register';document.querySelector('#auth-error').textContent='';document.querySelector('#mail-preview').hidden=true;document.querySelector('#auth-title').textContent=t(m==='login'?'Che bello ritrovarti.':'La tua prossima scoperta.');document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('selected',b.id===m+'-tab'));document.querySelector('#confirm-label').hidden=m!=='register';document.querySelector('#password-confirm').required=m==='register';document.querySelector('#password').autocomplete=m==='register'?'new-password':'current-password';document.querySelector('#auth-form .primary').textContent=t(m==='login'?'Accedi →':'Crea il profilo →')};
function showMail(value){document.querySelector('#auth-error').textContent=value.message;const link=document.querySelector('#mail-preview');link.hidden=!value.preview_url;if(value.preview_url)link.href=value.preview_url}
document.querySelector('#auth-form').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;document.querySelector('#mail-preview').hidden=true;try{const value=await api('auth/'+mode,{email:document.querySelector('#email').value,username:document.querySelector('#nickname').value,password:document.querySelector('#password').value,password2:document.querySelector('#password-confirm').value});if(value.message){if(mode==='register')registrationSuccess(value);else showMail(value);document.querySelector('#password').value='';document.querySelector('#password-confirm').value=''}else{sync(value);auth.close();e.target.reset();location.hash='profile';render()}}catch(err){document.querySelector('#auth-error').textContent=err.message}finally{button.disabled=false}};
for(const [id,purpose] of [['forgot','reset'],['resend','verify']])document.querySelector('#'+id).onclick=async e=>{const email=document.querySelector('#email');if(!email.reportValidity())return;e.target.disabled=true;document.querySelector('#mail-preview').hidden=true;try{showMail(await api('mail/'+purpose,{email:email.value}))}catch(err){document.querySelector('#auth-error').textContent=err.message}finally{e.target.disabled=false}};
async function render(){document.querySelectorAll('[data-nav]').forEach(a=>a.classList.toggle('active',a.dataset.nav===(location.hash==='#passport'?'passport':location.hash==='#profile'?'profile':location.hash==='#leaderboard'?'leaderboard':'home')));if(location.hash==='#passport')showPassport();else if(location.hash==='#leaderboard')leaderboard();else if(location.hash==='#profile')profile();else if(location.hash.startsWith('#quiz/')){const q=quizzes.find(q=>'#quiz/'+q.id===location.hash);if(q){if(current!==q){current=q;index=0;selected=null;checked=false;points=0;try{attempt=(await api("start",{quiz:q.id})).attempt}catch(e){current=null;app.textContent=e.message;return}}question()}else home()}else home()}
function home(){current=null;app.innerHTML=translateHTML(`<section class="intro"><div class="hero"><div class="eyebrow">ERNEST COMMUNITY / ESPLORA E GIOCA</div><h1>La scienza comincia<br>con una domanda.</h1><p>Segui gli indizi, prova i quiz e scopri qualcosa di nuovo. Non servono conoscenze specialistiche: basta la curiosità.</p><button class="primary" id="first">Scegli la tua prima sfida ↗</button><span class="index" aria-hidden="true">?</span></div><aside class="journey"><div class="eyebrow">IL TUO PERCORSO</div><h2>${name?'Ciao, '+escapeHTML(name)+'.':'Ogni scoperta conta.'}</h2><div class="progress-row"><div class="ring"><strong>${total()}</strong><small>PUNTI</small></div><div><strong>${Object.keys(completed).length} quiz completati</strong><p>Un passo alla volta,<br>una scoperta in più.</p></div></div><p>Parti senza account. Accedi per conservare i tuoi progressi.</p><a class="text-link" href="#passport">Apri il tuo passaporto →</a></aside></section><section id="quizzes"><div class="section-head"><div><h2>Scegli cosa scoprire</h2><p>Piccole sfide per mettere in moto le idee.</p></div><span class="quiet">QUIZ DIMOSTRATIVI</span></div><div class="filters" aria-label="Argomenti">${['Tutti',...new Set(quizzes.map(q=>q.topic))].map(f=>`<button class="chip ${filter===f?'selected':''}" data-filter="${f}" aria-pressed="${filter===f}">${f}</button>`).join('')}</div><div class="grid">${quizzes.filter(q=>filter==='Tutti'||q.topic===filter).map(q=>`<article class="card"><div class="photo"><img src="/static/community/${q.image}" alt="Attività scientifica ERNEST"><span class="tag">${q.topic.toUpperCase()}</span></div><div class="card-body"><div class="meta"><span>3 domande · circa 2 min</span><span>Spazio alla curiosità</span></div><h3>${q.title}</h3><p>${q.desc}</p><div class="card-bottom"><span>${q.id in completed?'Completato · '+completed[q.id]+' punti':'Fino a 30 punti'}</span><button data-quiz="${q.id}" aria-label="Inizia ${q.title}">↗</button></div></div></article>`).join('')}</div></section><div class="strip"><div><strong>Il tuo passaporto per nuove scoperte.</strong><p>Con un profilo conservi i risultati e continui il tuo percorso.</p></div><button class="outline" id="join">Esplora il profilo →</button></div>`);document.querySelector('#first').onclick=()=>document.querySelector('#quizzes').scrollIntoView({behavior:'smooth'});document.querySelector('#join').onclick=()=>location.hash='profile';document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;home()});document.querySelectorAll('[data-quiz]').forEach(b=>b.onclick=()=>{location.hash='quiz/'+b.dataset.quiz;window.scrollTo(0,0)})}
function question(){const q=current.questions[index];app.innerHTML=translateHTML(`<div class="quiz-shell"><button class="back" id="back">← Tutti i quiz</button><div class="eyebrow">${current.topic.toUpperCase()}</div><div class="quiz-top"><strong>${current.title}</strong><span>Domanda ${index+1} di 3</span></div><div class="bar"><i style="width:${(index+1)/3*100}%"></i></div><section class="question"><span class="quiet">SEGUI LA TUA CURIOSITÀ</span><h1>${q[0]}</h1><div class="answers">${q[1].map((a,i)=>`<button class="answer ${selected===i?'selected':''} ${checked&&i===q[2]?'correct':''} ${checked&&i===selected&&i!==q[2]?'wrong':''}" data-answer="${i}" ${checked?'disabled':''}><b>${'ABC'[i]}</b>${a}</button>`).join('')}</div>${checked?`<div class="feedback" role="status"><strong>${selected===q[2]?'Esatto! +10 punti':'Una nuova cosa da scoprire.'}</strong><br>${q[3]}</div>`:''}<button class="primary" id="next" ${selected===null?'disabled':''}>${checked?(index===2?'Guarda il risultato →':'Prossima domanda →'):'Conferma risposta →'}</button></section><p class="quiet">${name?"Il risultato sarà salvato nel tuo profilo.":"Prova senza account · accedi per conservare i risultati."}</p></div>`);document.querySelector('#back').onclick=()=>location.hash='home';document.querySelectorAll('[data-answer]').forEach(b=>b.onclick=()=>{selected=+b.dataset.answer;question()});document.querySelector('#next').onclick=async()=>{if(busy)return;if(!checked){busy=true;document.querySelector('#next').disabled=true;try{const result=await api('answer',{attempt,index,answer:selected});q[2]=result.correct;q[3]=result.explanation;points=result.score;sync(result);checked=true;question()}catch(e){alert(e.message);document.querySelector('#next').disabled=false}finally{busy=false}}else if(index<2){index++;selected=null;checked=false;question()}else{completed[current.id]=Math.max(points,completed[current.id]||0);result()}}}
function result(){app.innerHTML=translateHTML(`<section class="quiz-shell question result"><div class="eyebrow">SFIDA COMPLETATA</div><h1>Una scoperta tira l’altra.</h1><div class="score">${points}<small> / 30 punti</small></div><p>Hai risposto correttamente a ${points/10} domande su 3.<br>Ogni risposta è un’occasione per imparare.</p>${resultStamp()}<button class="primary" id="more">Esplora altri quiz →</button> <button class="outline" id="path">Il tuo percorso</button><p class="note">${name?"Risultato salvato nel tuo profilo.":"Accedi o registrati per conservare questo risultato."}</p></section>`);document.querySelector('#more').onclick=()=>location.hash='home';document.querySelector('#path').onclick=()=>location.hash='profile'}
// Fixed point thresholds: adding quizzes does not lower an earned phase.
const explorationPhases=[{minimum:0,label:'Curiosità'},{minimum:40,label:'Scoperta'},{minimum:90,label:'Esplorazione'},{minimum:140,label:'Nuove frontiere'}];
function phaseFor(score){return explorationPhases.filter(phase=>score>=phase.minimum).at(-1)||explorationPhases[0]}
function phaseGuide(){
 const score=total(),phase=phaseFor(score),index=explorationPhases.indexOf(phase),next=explorationPhases[index+1];
 return `<section class="phase-guide" aria-labelledby="phase-title"><h2 id="phase-title">A che punto sei?</h2><p>Ogni quiz aggiunge una scoperta al tuo percorso.</p><div class="phase-table-wrap"><table class="phase-table"><caption>Le quattro fasi</caption><thead><tr><th scope="col">Fase</th><th scope="col">Punti</th></tr></thead><tbody>${explorationPhases.map((item,i)=>`<tr class="${item===phase?'current-phase':''}"><th scope="row">${item.label}${item===phase?' <span class="phase-marker">✓ <span>La tua fase</span></span>':''}</th><td>${explorationPhases[i+1]?item.minimum+'–'+(explorationPhases[i+1].minimum-1):item.minimum+'+'}</td></tr>`).join('')}</tbody></table></div><p class="phase-next">${next?escapeHTML(t('Ti mancano {points} punti alla prossima fase.',{points:next.minimum-score})):'Hai raggiunto Nuove frontiere. Continua a scoprire!'}</p><p class="note">Le soglie sono fisse. Il totale somma il miglior risultato di ogni quiz.</p></section>`;
}
function profile(){current=null;app.innerHTML=translateHTML(`<section class="profile-head"><div class="eyebrow">IL TUO PERCORSO</div><h1>${name?'Ciao, '+escapeHTML(name)+'.':'La tua curiosità, in viaggio.'}</h1><p>${name?"Qui ritrovi i tuoi migliori risultati salvati.":"Qui ritrovi i risultati di questa sessione. Accedi per conservarli."}</p><div class="stats"><div class="stat"><strong>${total()}</strong><span>Punti raccolti</span></div><div class="stat"><strong>${Object.keys(completed).length} / ${quizzes.length}</strong><span>Quiz completati</span></div><div class="stat"><strong>${phaseFor(total()).label}</strong><span>La tua fase</span></div></div>${phaseGuide()}<p><a class="text-link" href="#passport">Apri il tuo passaporto →</a></p><div class="section-head"><h2>Le tue scoperte</h2><a href="#home">Esplora i quiz ↗</a></div>${Object.keys(completed).length?Object.keys(completed).map(id=>`<div class="history"><strong>${quizzes.find(q=>q.id===id).title}</strong><span>${completed[id]} / 30 punti</span></div>`).join(''):'<div class="empty"><h3>Il primo indizio ti aspetta.</h3><p>Completa un quiz e vedrai qui il tuo risultato.</p><a href="#home" class="text-link">Scegli un quiz →</a></div>'}<div class="strip"><div><strong>${name?'Il tuo profilo: '+escapeHTML(name):'Dai un nome al tuo profilo.'}</strong><p>${name?"I punti totali sommano il risultato migliore di ogni quiz.":"Registrati con email, nickname e password. L’email resta privata."}</p></div><button class="outline" id="profile-auth">${name?'Esplora altri quiz':'Accedi o registrati'} →</button></div></section>`);document.querySelector('#profile-auth').onclick=()=>name?location.hash='home':openAuth()}
window.addEventListener('hashchange',render);api('state').then(value=>{quizzes=value.quizzes;accountsEnabled=value.accounts_enabled;sync(value);render()}).catch(e=>{app.textContent=e.message});

document.querySelectorAll('[data-lang]').forEach(button=>button.onclick=()=>{
 if(busy)return;
 language=button.dataset.lang;
 const url=new URL(location.href);url.searchParams.delete("lang");history.replaceState(null,"",url);
 document.cookie='django_language='+language+'; Path=/; Max-Age=31536000; SameSite=Lax'+(location.protocol==='https:'?'; Secure':'');
 translateChrome();sync({name,completed});
 document.querySelector('#auth-title').textContent=t(mode==='login'?'Che bello ritrovarti.':'La tua prossima scoperta.');
 document.querySelector('#auth-form .primary').textContent=t(mode==='login'?'Accedi →':'Crea il profilo →');
 document.querySelector('#auth-error').textContent='';
 if(current && checked && index===2 && document.querySelector('.result'))result();else render();
});


async function leaderboard(){
 current=null;
 if(!name){app.innerHTML=translateHTML('<section class="profile-head"><h1>Classifica</h1><p>Accedi per vedere la classifica.</p><button class="primary" id="ranking-login">Accedi →</button></section>');document.querySelector('#ranking-login').onclick=openAuth;return;}

 app.textContent=t('Caricamento classifica…');
 try{
  const value=await api('leaderboard');
  if(location.hash!=='#leaderboard')return;
  const highest=Math.max(1,...value.bands.map(b=>b.count));
  app.innerHTML=translateHTML(`<section class="profile-head"><div class="eyebrow">ERNEST COMMUNITY</div><h1>Classifica</h1><p>Ogni scoperta fa punti.</p><p class="note">La distribuzione mostra quante persone hanno raggiunto ogni fascia di punteggio, senza pubblicare i nickname.</p>${value.mine?`<div class="stats"><div class="stat"><strong>${value.mine.score}</strong><span>Il tuo punteggio</span></div><div class="stat"><strong>${value.mine.rank} / ${value.participants}</strong><span>La tua posizione</span></div></div><p class="note">La tua fascia è evidenziata. A parità di punti, la posizione è condivisa.</p>`:'<p>Completa un quiz e accedi con un account confermato per vedere la tua posizione.</p>'}${value.participants?`<div class="ranking-wrap"><table class="ranking"><caption>Distribuzione dei punteggi</caption><thead><tr><th scope="col">Punti</th><th scope="col">Persone partecipanti</th></tr></thead><tbody>${value.bands.map(b=>`<tr ${value.mine&&value.mine.score>=b.minimum&&value.mine.score<=b.maximum?'class="my-rank"':''}><th scope="row">${b.minimum}–${b.maximum}</th><td><div class="histogram-cell"><span class="histogram-bar" style="width:${b.count/highest*100}%" aria-hidden="true"></span><strong>${b.count}</strong></div></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty"><h2>La classifica aspetta la prima scoperta.</h2></div>'}<p class="note">Il totale somma il miglior risultato di ogni quiz. Sono inclusi gli account attivi con email confermata e almeno un quiz completato.</p><a href="#home" class="text-link">Esplora i quiz ↗</a></section>`);
 }catch(error){if(location.hash==='#leaderboard')app.textContent=error.message;}
}

function registrationSuccess(value){
 document.querySelector('#registration-email').textContent=document.querySelector('#email').value;
 document.querySelector('#auth-fields').hidden=true;
 document.querySelector('#registration-success').hidden=false;
 const preview=document.querySelector('#success-preview');preview.hidden=true;
 document.querySelector('#registration-success-title').focus();
}
document.querySelector('#success-login').onclick=()=>{document.querySelector('#auth-fields').hidden=false;document.querySelector('#registration-success').hidden=true;document.querySelector('#login-tab').click();document.querySelector('#password').focus()};
document.querySelector('#success-close').onclick=()=>auth.close();


// Original artwork from ERNEST-icone.zip (31.png); viewBox selects each icon.
const passportFrames={experiment:[98,126,450,450],think:[651,121,450,450],idea:[1175,111,450,450],observe:[96,667,450,450],collaborate:[648,667,450,450],europe:[1179,667,450,450]};
function stampIcon(id){const frame=passportFrames[id];return frame?`<svg viewBox="${frame.join(' ')}" aria-hidden="true" focusable="false"><image href="/static/community/passport-official.png" width="1748" height="1240" /></svg>`:''}
function resultStamp(){const icon=passport.find(i=>i.id===current?.stamp&&i.earned);return icon?`<div class="result-stamp">${stampIcon(icon.id)}<div><strong>Timbro nel passaporto</strong><p>${escapeHTML(icon.label)}</p><a class="text-link" href="#passport">Apri il tuo passaporto →</a></div></div>`:''}
function showPassport(){
 current=null;
 const earned=passport.filter(i=>i.earned).length,available=passport.filter(i=>i.quizzes.length).length;
 app.innerHTML=translateHTML(`<div class="passport-intro"><div class="eyebrow">ERNEST / IL TUO PASSAPORTO</div><h1>Ogni scoperta lascia un segno.</h1><p>Il tuo viaggio nella scienza, una pagina alla volta.</p><button type="button" class="passport-sound" id="passport-sound" aria-pressed="${passportSound}">${passportSound?'Suono della pagina: attivo':'Suono della pagina: disattivato'}</button></div><div class="passport-book ${passportOpen?'is-open':''}"><button type="button" class="passport-cover" id="open-passport" aria-expanded="${passportOpen}" aria-controls="passport-pages" ${passportOpen?'inert aria-hidden="true"':''}><svg class="cover-art" viewBox="874 0 874 1240" aria-hidden="true" focusable="false"><image href="/static/community/passport-cover-official.png" width="1748" height="1240"/></svg><span class="cover-name" data-cover-name></span><span class="cover-edition">Passaporto online</span><span class="cover-invitation">Apri il tuo passaporto <span aria-hidden="true">↗</span></span></button><div id="passport-pages" ${passportOpen?'':'hidden'}><div class="passport-book-toolbar"><button type="button" class="back" id="close-passport">← Chiudi il passaporto</button><span>LE TUE SCOPERTE</span></div><section class="passport passport-spread" aria-label="Il tuo passaporto">${[passport.slice(0,3),passport.slice(3)].map((icons,page)=>`<div class="paper-page"><div class="paper-running"><span>ERNEST</span><span>PASSAPORTO ONLINE</span></div><div class="paper-identity">${page===0?`<span>PASSAPORTO DI</span><strong data-paper-name></strong>`:`<span>Timbri raccolti</span><strong>${earned} / ${passport.length}</strong>`}</div><div class="paper-stamps">${icons.map(icon=>`<article class="paper-stamp ${icon.earned?'earned':''}"><div class="stamp-circle">${stampIcon(icon.id)}${icon.earned?'<span class="stamp-seal">✓</span>':''}</div><div class="paper-stamp-caption"><h2>${escapeHTML(icon.label)}</h2><p>${icon.earned?'Timbro conquistato':icon.quizzes.length?'Da conquistare':'Nuove sfide in arrivo'}</p>${icon.quizzes.map(id=>{const q=quizzes.find(q=>q.id===id);return q?`<a href="#quiz/${q.id}" title="${escapeHTML(q.title)}">${escapeHTML(q.title)} <span aria-hidden="true">↗</span></a>`:''}).join('')}</div></article>`).join('')}</div><div class="paper-footer"><span>European Researchers’ Night</span><span>0${page+1}</span></div></div>`).join('')}</section><div class="passport-note"><strong>Un timbro per ogni icona.</strong><p>Completa almeno un quiz associato per ottenerlo. Ripetere un quiz migliora il punteggio, senza duplicare il timbro.</p><p>${name?'I timbri seguono i risultati salvati nel tuo profilo.':'Il passaporto senza account resta in questa sessione. Accedi dallo stesso browser per conservarlo nel tuo profilo.'}</p>${name?'':'<button class="outline" id="passport-login">Accedi o registrati →</button>'}</div><p class="note">Questi timbri raccontano le attività online e non certificano la partecipazione agli eventi in presenza.</p></div></div><p class="cover-help" ${passportOpen?'hidden':''}>Tocca la copertina per sfogliare il passaporto.</p>`);
 // Insert the nickname as text after translation; never interpret it as markup.
 document.querySelector('[data-cover-name]').textContent=name||t('Ospite');
 document.querySelector('[data-paper-name]').textContent=name||t('Ospite');
 const cover=document.querySelector('#open-passport'),pages=document.querySelector('#passport-pages'),book=document.querySelector('.passport-book'),hint=document.querySelector('.cover-help');
 function setBookOpen(open){
  playPageSound();
  passportOpen=open;pages.hidden=!open;cover.inert=open;
  cover.setAttribute('aria-expanded',String(open));cover.setAttribute('aria-hidden',String(open));
  book.classList.toggle('is-open',open);hint.hidden=open;
  (open?document.querySelector('#close-passport'):cover).focus({preventScroll:true});
 }
 document.querySelector('#passport-sound').addEventListener('click',event=>{passportSound=!passportSound;event.currentTarget.setAttribute('aria-pressed',String(passportSound));event.currentTarget.textContent=t(passportSound?'Suono della pagina: attivo':'Suono della pagina: disattivato');});
 cover.addEventListener('click',()=>setBookOpen(true));
 document.querySelector('#close-passport').addEventListener('click',()=>setBookOpen(false));
 document.querySelector('#passport-login')?.addEventListener('click',openAuth);
}


// A short, quiet paper rustle. Audio is created only in response to a page turn.
function playPageSound(){
 if(!passportSound)return;
 try{
  const AudioContext=window.AudioContext||window.webkitAudioContext;
  if(!AudioContext)return;
  pageAudioContext=pageAudioContext||new AudioContext();
  const ctx=pageAudioContext;
  ctx.resume().then(()=>{
   if(!passportSound||ctx.state!=='running')return;
   const duration=.38,buffer=ctx.createBuffer(1,Math.ceil(ctx.sampleRate*duration),ctx.sampleRate),samples=buffer.getChannelData(0);
   for(let i=0;i<samples.length;i++){
    const x=i/samples.length;
    samples[i]=(Math.random()*2-1)*(.5+.5*Math.sin(x*31)**2);
   }
   const source=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain(),now=ctx.currentTime;
   source.buffer=buffer;filter.type='bandpass';filter.Q.value=.7;
   filter.frequency.setValueAtTime(2100,now);filter.frequency.exponentialRampToValueAtTime(700,now+duration);
   gain.gain.setValueAtTime(0,now);gain.gain.linearRampToValueAtTime(.12,now+.06);gain.gain.exponentialRampToValueAtTime(.001,now+duration);
   source.connect(filter);filter.connect(gain);gain.connect(ctx.destination);
   source.onended=()=>{source.disconnect();filter.disconnect();gain.disconnect();};
   source.start(now);source.stop(now+duration);
  }).catch(()=>{});
 }catch{/* Audio unavailable: page navigation still works. */}
}
