const CACHE_NAME = 'buildtrack-shell-v13';
const OFFLINE_URL = new URL('./offline.html', self.location.href).href;
const APP_SHELL = [
  './',
  './index.html',
  OFFLINE_URL,
  './manifest.json',
  './css/style.css',
  './assets/logo.svg',
  './assets/avatar.svg',
  './assets/icon-192.png',
  './assets/icon-512.png',
  './js/data.js',
  './js/api.js',
  './js/app.js?v=auth-fix-1',
  './js/dashboard.js',
  './js/projects.js',
  './js/tasks.js',
  './js/labour.js',
  './js/materials.js',
  './js/finance.js',
  './js/progress.js',
  './js/risks.js',
  './js/reports.js',
  './js/settings.js',
  './js/pwa.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(APP_SHELL.map(path => new Request(new URL(path, self.location.href), { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith('buildtrack-shell-') && key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const requestUrl = new URL(request.url);
  // Private records and dashboard data must always come from the authenticated API.
  if (requestUrl.origin === self.location.origin && requestUrl.pathname.startsWith('/api/')) {
    event.respondWith(fetch(request, { cache: 'no-store' }).catch(() => new Response(
      JSON.stringify({ error: 'BuildTrack server is unavailable. Reconnect and try again.' }),
      { status: 503, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } }
    )));
    return;
  }
  if (requestUrl.origin !== self.location.origin) {
    // Keep successful CDN responses (for example Chart.js) available after
    // their first online use. Opaque responses are valid cache entries too.
    event.respondWith(
      caches.open(CACHE_NAME).then(async cache => {
        const cached = await cache.match(request);
        if (cached) return cached;
        try {
          const response = await fetch(request);
          if (response.ok || response.type === 'opaque') await cache.put(request, response.clone());
          return response;
        } catch (error) {
          return new Response('', { status: 503, statusText: 'Offline' });
        }
      })
    );
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(request);
    try {
      // Revalidate app shell files so an installed PWA cannot keep stale auth code.
      const response = await fetch(request, { cache: 'no-store' });
      if (response.ok && request.method === 'GET') await (await caches.open(CACHE_NAME)).put(request, response.clone());
      return response;
    } catch (error) {
      if (request.mode === 'navigate') {
        // A transient navigation failure must not strand users on the cached
        // Offline screen while Flask is already answering its health endpoint.
        for (let attempt = 0; attempt < 3; attempt += 1) {
          try {
            const health = await fetch(new URL('./api/health', self.location.href), { cache: 'no-store' });
            if (health.ok) {
              const appShell = await caches.match(new URL('./', self.location.href).href) || await caches.match(new URL('./index.html', self.location.href).href);
              if (appShell) return appShell;
            }
          } catch (_) { /* Retry briefly before selecting the genuine offline fallback. */ }
          await new Promise(resolve => setTimeout(resolve, 700));
        }
        return await caches.match(OFFLINE_URL) || cached || new Response('BuildTrack is offline.', {
          status: 503, statusText: 'Offline', headers: { 'Content-Type': 'text/plain; charset=utf-8' }
        });
      }
      if (cached) return cached;
      return new Response('', { status: 503, statusText: 'Offline' });
    }
  })());
});
