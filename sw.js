// ===== BrawlCity Rank — Service Worker PWA =====
const CACHE_NAME = 'brawlcity-v1';

// Arquivos que ficam salvos offline
const ARQUIVOS_CACHE = [
  '/',
  '/index.html'
];

// Instala e faz cache dos arquivos principais
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(ARQUIVOS_CACHE);
    })
  );
  self.skipWaiting();
});

// Limpa caches antigos ao ativar
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(key) { return key !== CACHE_NAME; })
            .map(function(key) { return caches.delete(key); })
      );
    })
  );
  self.clients.claim();
});

// Estratégia: tenta internet primeiro, cai no cache se offline
self.addEventListener('fetch', function(event) {
  event.respondWith(
    fetch(event.request)
      .then(function(response) {
        // Salva cópia no cache se for GET
        if (event.request.method === 'GET') {
          var responseClone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      })
      .catch(function() {
        // Sem internet? Usa o cache
        return caches.match(event.request).then(function(cached) {
          return cached || new Response(
            '<html><body style="background:#0a0612;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px">' +
            '<div style="font-size:60px">😵</div>' +
            '<div style="font-size:22px;font-weight:bold">Sem conexão</div>' +
            '<div style="color:#888;font-size:14px">Verifique sua internet e recarregue</div>' +
            '</body></html>',
            { headers: { 'Content-Type': 'text/html' } }
          );
        });
      })
  );
});
