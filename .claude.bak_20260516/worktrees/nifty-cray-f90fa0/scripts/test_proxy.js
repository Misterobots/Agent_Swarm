fetch('http://127.0.0.1:3000/api/backend/')
  .then(r => { console.log('STATUS:', r.status); return r.text(); })
  .then(t => console.log('BODY:', t.substring(0, 300)))
  .catch(e => console.log('ERROR:', e.message));
