// TQQQ 매매신호 앱 서비스워커
// 앱 셸(HTML/아이콘)을 캐싱해서 오프라인에서도 최근 열었던 화면을 볼 수 있게 함.
// 시세 데이터는 파일 안에 이미 내장되어 있으므로 별도 네트워크 데이터 캐싱은 불필요.

const CACHE_NAME = 'tqqq-signal-app-v2';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './data.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// 캐시 우선(앱 셸) / 네트워크 우선(data.json) 전략
// data.json은 "앱을 열 때마다 최신 시세로 갱신"이 핵심 요구사항이므로
// 캐시보다 네트워크를 항상 먼저 시도하고, 실패(오프라인)할 때만 캐시로 폴백한다.
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const isDataJson = event.request.url.endsWith('/data.json') || event.request.url.endsWith('data.json');

  if (isDataJson) {
    event.respondWith(
      fetch(event.request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return resp;
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return resp;
      }).catch(() => cached);
    })
  );
});
