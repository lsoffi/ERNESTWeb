// Display the same public site total, without loading an analytics tracker.
fetch('https://ernest-project.goatcounter.com/counter/TOTAL.json',{cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer'})
 .then(response=>{if(!response.ok)throw new Error();return response.json()})
 .then(data=>{if(data.count!=null){document.querySelector('[data-visit-count]').textContent=data.count;document.querySelector('.site-visit-counter').hidden=false}})
 .catch(()=>{});
