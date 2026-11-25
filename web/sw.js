// RG Sağlık Takip – service worker
// Ağ öncelikli: önce güncel dosya alınır, çevrimdışıysa son kaydedilen kopya gösterilir.
const CACHE = 'rg-1.11.7';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  // Yalnızca aynı siteden GET istekleri; sunucu API'si (yetkili veri) önbelleğe alınmaz.
  if (r.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;
  e.respondWith(
    fetch(r, { cache: 'no-cache' })
      .then(res => {
        if (res.ok && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(r, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(r).then(m => m || (r.mode === 'navigate' ? caches.match('index.html') : null) || Response.error()))
  );
});
