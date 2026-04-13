fetch('http://execution-node:8008/')
  .then(r => { console.log('STATUS:', r.status); return r.text(); })
  .then(t => console.log('BODY:', t.substring(0, 200)))
  .catch(e => console.log('ERROR:', e.message));
