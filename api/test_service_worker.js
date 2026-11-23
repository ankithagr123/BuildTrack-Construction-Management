const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const handlers = {};
const cached = new Map();
const offlinePage = new Response('offline screen', { status: 200 });
const appPage = new Response('BuildTrack login shell', { status: 200 });
cached.set('http://127.0.0.1:5001/', appPage);
cached.set('http://127.0.0.1:5001/offline.html', offlinePage);
let fetchImpl;
const sandbox = {
  URL,
  Request,
  Response,
  self: {
    location: new URL('http://127.0.0.1:5001/'),
    addEventListener: (name, handler) => { handlers[name] = handler; },
    clients: { claim: async () => {} },
    skipWaiting: async () => {}
  },
  caches: {
    open: async () => ({
      match: async request => cached.get(typeof request === 'string' ? request : request.url),
      put: async (request, response) => cached.set(typeof request === 'string' ? request : request.url, response)
    }),
    match: async request => cached.get(typeof request === 'string' ? request : request.url),
    keys: async () => ['buildtrack-shell-v12'],
    delete: async () => true
  },
  fetch: (...args) => fetchImpl(...args),
  setTimeout: callback => { callback(); return 0; },
  Promise,
  Map
};
vm.runInNewContext(fs.readFileSync('service-worker.js', 'utf8'), sandbox);

async function dispatch(request) {
  let responsePromise;
  handlers.fetch({ request, respondWith: promise => { responsePromise = promise; } });
  return responsePromise;
}
const makeRequest = (url, mode = 'cors') => ({url, method: 'GET', mode});

(async () => {
  let apiOptions;
  fetchImpl = async (_request, options) => {
    apiOptions = options;
    return new Response('{"status":"ok"}', { status: 200 });
  };
  const apiResponse = await dispatch(makeRequest('http://127.0.0.1:5001/api/health'));
  assert.equal(apiResponse.status, 200);
  assert.equal(apiOptions.cache, 'no-store');

  fetchImpl = async request => {
    const url = request.url || request.href || request;
    if (new URL(url).pathname === '/api/health') return new Response('{"status":"ok"}', { status: 200 });
    throw new Error('temporary navigation failure');
  };
  const recovered = await dispatch(makeRequest('http://127.0.0.1:5001/', 'navigate'));
  assert.equal(await recovered.text(), 'BuildTrack login shell');

  fetchImpl = async () => { throw new Error('offline'); };
  const unavailableApi = await dispatch(makeRequest('http://127.0.0.1:5001/api/projects'));
  assert.equal(unavailableApi.status, 503);
  assert.match((await unavailableApi.json()).error, /server is unavailable/i);
  const offlineNavigation = await dispatch(makeRequest('http://127.0.0.1:5001/', 'navigate'));
  assert.equal(await offlineNavigation.text(), 'offline screen');
  process.stdout.write('Service worker network, API no-cache, transient recovery, and offline fallback checks passed.\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
