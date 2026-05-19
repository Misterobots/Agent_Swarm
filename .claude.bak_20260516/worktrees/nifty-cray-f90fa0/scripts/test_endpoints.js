const endpoints = [
  '/api/backend/',
  '/api/backend/api/v1/identity',
  '/api/backend/v1/models',
];

(async () => {
  for (const ep of endpoints) {
    try {
      const r = await fetch('http://127.0.0.1:3000' + ep);
      const t = await r.text();
      console.log(`${r.status} ${ep} => ${t.substring(0, 100)}`);
    } catch (e) {
      console.log(`ERR ${ep} => ${e.message}`);
    }
  }
})();
