// TQQQ 매매신호 앱 서비스워커
// 아이콘처럼 거의 안 바뀌는 정적 자산만 캐시 우선으로 쓰고,
// index.html / manifest.json / data.json은 항상 네트워크를 먼저 시도해서
// "새 파일을 올렸는데도 예전 화면이 계속 보이는" 문제가 생기지 않게 한다.
// 오프라인일 때만 마지막으로 받아둔 캐시로 대체된다.

const CACHE_NAME = 'tqqq-signal-app-v3';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './data.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

// 캐시 우선으로 둬도 안전한(자주 안 바뀌는) 정적 파일만 여기 포함
const CACHE_FIRST_SUFFIXES = ['icon-192.png', 'icon-512.png', 'apple-touch-icon.png'];

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

function isCacheFirstAsset(url) {
  return CACHE_FIRST_SUFFIXES.some((suffix) => url.endsWith(suffix));
}

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = event.request.url;

  // 아이콘류: 캐시 우선, 실패 시 네트워크
  if (isCacheFirstAsset(url)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return resp;
        });
      })
    );
    return;
  }

  // index.html / manifest.json / data.json 및 그 외 모든 요청:
  // 네트워크 우선 — 항상 최신 버전을 먼저 시도하고, 오프라인일 때만 캐시로 대체
  event.respondWith(
    fetch(event.request, { cache: 'no-store' }).then((resp) => {
      const copy = resp.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
      return resp;
    }).catch(() => caches.match(event.request))
  );
});
