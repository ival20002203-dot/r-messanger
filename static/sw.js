/* R-Mes 15 native offline cache. Never caches auth/control/API/attachments. */
const VERSION="rmes-native-v15";
const STATIC_CACHE=`${VERSION}-static`;
const PAGE_CACHE=`${VERSION}-pages`;
const STATIC_HINTS=["/static/app.css","/static/app.js","/static/chat.js","/static/i18n.js","/static/icons.svg","/static/rmes-logo.svg","/static/rmes-icon.png"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(STATIC_CACHE).then(c=>c.addAll(STATIC_HINTS).catch(()=>{})));self.skipWaiting()});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("rmes-native-")&&!k.startsWith(VERSION)).map(k=>caches.delete(k)))));self.clients.claim()});
function privateRoute(url){return url.pathname.startsWith("/auth/")||url.pathname.startsWith("/control/")||url.pathname.startsWith("/api/")||url.pathname.startsWith("/ops/")||url.pathname.startsWith("/a/")||url.pathname.includes("/upload/")||url.pathname.includes("/recording/")}
self.addEventListener("fetch",event=>{
  const req=event.request;if(req.method!=="GET")return;const url=new URL(req.url);if(url.origin!==self.location.origin)return;
  if(url.pathname.startsWith("/static/")){event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(r=>{if(r.ok){const copy=r.clone();caches.open(STATIC_CACHE).then(c=>c.put(req,copy))}return r})));return}
  if(req.mode==="navigate"&&!privateRoute(url)){
    event.respondWith(fetch(req).then(r=>{if(r.ok&&r.headers.get("content-type")?.includes("text/html")){const copy=r.clone();caches.open(PAGE_CACHE).then(async c=>{await c.put(req,copy);const keys=await c.keys();if(keys.length>30)await c.delete(keys[0])})}return r}).catch(()=>caches.match(req).then(hit=>hit||caches.match("/"))));
  }
});
self.addEventListener("message",event=>{if(event.data?.type==="PURGE_PRIVATE")event.waitUntil(caches.delete(PAGE_CACHE))});
