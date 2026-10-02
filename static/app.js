window.RMesUI={
  csrf(){
    const m=document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m?decodeURIComponent(m[1]):"";
  },
  esc(value){
    const d=document.createElement("div");d.textContent=value??"";return d.innerHTML;
  },
  toast(text,kind=""){
    let wrap=document.querySelector(".toasts");
    if(!wrap){wrap=document.createElement("div");wrap.className="toasts";document.body.appendChild(wrap);}
    const translated=window.RMesI18n?.t?.(text)||text;
    const el=document.createElement("div");el.className=`toast ${kind}`;el.textContent=translated;wrap.appendChild(el);
    setTimeout(()=>el.classList.add("show"),10);
    setTimeout(()=>{el.classList.remove("show");setTimeout(()=>el.remove(),200)},3200);
  },
  async post(url,data={}){
    const r=await fetch(url,{
      method:"POST",
      headers:{
        "X-CSRFToken":this.csrf(),
        "X-Requested-With":"XMLHttpRequest",
        "Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"
      },
      body:new URLSearchParams(data)
    });
    const j=await r.json().catch(()=>({detail:"Ошибка сервера"}));
    if(!r.ok)throw new Error(j.detail||"Ошибка");
    return j;
  },
  debounce(fn,delay=160){
    let timer;return(...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),delay)};
  }
};

document.addEventListener("DOMContentLoaded",()=>{
  const savedScale=Math.max(85,Math.min(120,Number(document.body.dataset.fontScale||100)));
  const applyUiScale=value=>{const factor=Math.max(.85,Math.min(1.2,Number(value||100)/100));document.body.style.zoom=String(factor);document.body.style.width=`${100/factor}vw`;document.body.style.height=`${100/factor}vh`};
  applyUiScale(savedScale);
  window.RMesApplyScale=applyUiScale;

  const networkStatus=document.querySelector("#rmesNetworkStatus");
  let networkStatusTimer=null;
  const showNetworkStatus=(text,kind="")=>{
    if(!networkStatus)return;clearTimeout(networkStatusTimer);networkStatus.textContent=text;networkStatus.className=`rmes-network-status ${kind}`.trim();
    if(kind==="success")networkStatusTimer=setTimeout(()=>networkStatus.classList.add("hidden"),1800);
  };
  if(!navigator.onLine)showNetworkStatus("Нет сети · переподключаюсь…","error");
  window.addEventListener("offline",()=>showNetworkStatus("Нет сети · переподключаюсь…","error"));
  window.addEventListener("online",()=>showNetworkStatus("Связь восстановлена","success"));
  setTimeout(()=>document.querySelectorAll(".toast").forEach(x=>x.remove()),4200);

  const shellUserId=document.querySelector(".tg-app")?.dataset.userId||"anonymous";
  document.querySelectorAll(".tg-chat-item[data-conversation-id]").forEach(item=>{
    const id=item.dataset.conversationId;
    const draft=localStorage.getItem(`rmes:draft:${shellUserId}:${id}`);
    const preview=item.querySelector(".tg-chat-preview");
    if(draft&&preview){
      preview.innerHTML=`<span class="draft-prefix">Черновик:</span> ${RMesUI.esc(draft.slice(0,52))}`;
      item.classList.add("has-draft");
    }
  });

  const sidebarMenuBtn=document.querySelector("#sidebarMenuBtn");
  const sidebarMenu=document.querySelector("#sidebarMenu");
  sidebarMenuBtn?.addEventListener("click",e=>{e.stopPropagation();sidebarMenu?.classList.toggle("hidden")});

  const mobileBtn=document.querySelector("#mobileSidebarBtn");
  mobileBtn?.addEventListener("click",()=>document.body.classList.toggle("sidebar-open"));

  document.addEventListener("click",e=>{
    if(sidebarMenu&&!sidebarMenu.contains(e.target)&&e.target!==sidebarMenuBtn)sidebarMenu.classList.add("hidden");
  });

  const globalCfg=window.R_MES_GLOBAL||{};
  let authRedirecting=false;
  function authSessionLost(response){
    if(!response||authRedirecting)return authRedirecting;
    let loginRedirect=false;
    try{
      const url=new URL(response.url||"",location.origin);
      loginRedirect=Boolean(response.redirected&&url.pathname.startsWith("/auth/login/"));
    }catch(_){}
    if(response.status===401||loginRedirect){
      authRedirecting=true;
      const next=`${location.pathname}${location.search}`;
      location.replace(`/auth/login/?next=${encodeURIComponent(next)}`);
      return true;
    }
    return false;
  }
  let serverClockOffset=0;
  function syncServerClock(value){const stamp=new Date(value||"").getTime();if(Number.isFinite(stamp))serverClockOffset=stamp-Date.now()}
  syncServerClock(globalCfg.serverNow);
  const serverNow=()=>Date.now()+serverClockOffset;
  const serverZone=globalCfg.serverTimeZone||"Asia/Tashkent";
  const uiLocale=globalCfg.language==="en"?"en-GB":globalCfg.language==="uz"?"uz-UZ":"ru-RU";
  const timeFormatter=new Intl.DateTimeFormat(uiLocale,{timeZone:serverZone,hour:"2-digit",minute:"2-digit",hour12:false});
  const dayFormatter=new Intl.DateTimeFormat("en-CA",{timeZone:serverZone,year:"numeric",month:"2-digit",day:"2-digit"});
  const dateFormatter=new Intl.DateTimeFormat(uiLocale,{timeZone:serverZone,day:"2-digit",month:"2-digit",year:"numeric"});
  const appClock=value=>{const d=new Date(value||serverNow());return Number.isNaN(d.getTime())?"":timeFormatter.format(d)};
  const displayClock=value=>{
    if(value&&typeof value==="object"){
      const explicit=String(value.time_hm||value.server_time_hm||"").trim();
      if(/^\d{1,2}:\d{2}$/.test(explicit))return explicit;
    }
    return appClock(value);
  };
  window.RMesServerClock={now:serverNow,sync:syncServerClock,time:appClock,date:value=>dateFormatter.format(new Date(value||serverNow()))};
  const notificationBell=document.querySelector("#notificationBell");
  const notificationPanel=document.querySelector("#notificationPanel");
  const notificationBadge=document.querySelector("#notificationBadge");
  notificationBell?.addEventListener("click",e=>{e.stopPropagation();notificationPanel?.classList.toggle("hidden")});
  document.querySelector("#readAllNotifications")?.addEventListener("click",async()=>{
    try{await RMesUI.post(globalCfg.notificationReadAllUrl);document.querySelectorAll(".notification-row.unread").forEach(x=>x.classList.remove("unread"));notificationBadge?.classList.add("hidden");notificationBadge.textContent="";}catch(e){RMesUI.toast(e.message,"error")}
  });
  document.addEventListener("click",e=>{if(notificationPanel&&!notificationPanel.contains(e.target)&&!e.target.closest("#notificationBell"))notificationPanel.classList.add("hidden")});

  const notificationList=document.querySelector("#notificationList");
  function renderNotifications(data){
    if(notificationBadge){
      notificationBadge.textContent=data.unread>99?"99+":String(data.unread||"");
      notificationBadge.classList.toggle("hidden",!data.unread);
    }
    if(!notificationList)return;
    notificationList.innerHTML=(data.results||[]).length
      ?data.results.map(n=>`<a class="notification-row ${n.read?"":"unread"}" href="${n.url||"#"}">
          <div class="tg-avatar tg-avatar-sm">${n.avatar?`<img src="${n.avatar}" alt="">`:"<span>!</span>"}</div>
          <div><b>${RMesUI.esc(n.title||n.actor||"R-Messanger")}</b><span>${RMesUI.esc(n.body||"")}</span><time>${RMesUI.esc(n.time||"")}</time></div>
        </a>`).join("")
      :'<div class="tg-search-empty">Новых уведомлений нет.</div>';
  }
  function recomputeChatUnreadTotal(){
    let total=0;
    document.querySelectorAll(".tg-chat-item .tg-unread").forEach(el=>{total+=Number((el.textContent||"").replace(/\D/g,""))||0});
    const totalBadge=document.querySelector("#sidebarUnreadTotal");
    if(totalBadge){totalBadge.textContent=total>99?"99+":String(total||"");totalBadge.classList.toggle("hidden",!total)}
    const baseTitle=(document.title||"R-Messanger").replace(/^\(\d+\+?\)\s*/,"");
    document.title=total?`(${total>99?"99+":total}) ${baseTitle}`:baseTitle;
    return total;
  }
  function applyChatUnreadCounts(counts={}){
    document.querySelectorAll(".tg-chat-item[data-conversation-id]").forEach(card=>{
      const cid=String(card.dataset.conversationId||"");
      const count=Math.max(0,Number(counts[cid]||0));
      let badge=card.querySelector(".tg-unread");
      if(count&&!badge){badge=document.createElement("span");badge.className="tg-unread";card.querySelector(".tg-chat-bottomline")?.appendChild(badge)}
      if(badge){badge.textContent=count>99?"99+":String(count||"");badge.classList.toggle("hidden",!count)}
    });
    recomputeChatUnreadTotal();
  }
  recomputeChatUnreadTotal();
  function notificationCategoryEnabled(kind){
    if(kind==="direct")return globalCfg.notifyDirectChats!==false;
    if(kind==="group")return globalCfg.notifyGroups!==false;
    if(kind==="channel")return globalCfg.notifyChannels!==false;
    return false;
  }
  function notificationPing(){
    if(!globalCfg.notificationSound)return;
    try{const ctx=new (window.AudioContext||window.webkitAudioContext)(),o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=720;g.gain.value=.025;o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.06)}catch(_){}
  }
  const seenRealtimeMessages=new Set();
  const notifiedMessageIds=new Set();
  let desktopMessageCursor=localStorage.getItem(`rmes:desktop-message-cursor:${globalCfg.userId||"0"}`)||"";
  // Presence follows the actually focused R-Messanger window/tab. Native clients
  // additionally report their real window visibility/focus from Electron.
  let desktopWindowVisible=true,desktopWindowFocused=window.RMesDesktop?.isDesktop?document.hasFocus():true;
  if(window.RMesDesktop?.getWindowState){
    window.RMesDesktop.getWindowState().then(state=>{desktopWindowVisible=state?.visible!==false;desktopWindowFocused=Boolean(state?.focused)}).catch(()=>{});
  }
  if(window.RMesDesktop?.onVisibility){
    window.RMesDesktop.onVisibility(state=>{
      desktopWindowVisible=state?.visible!==false;desktopWindowFocused=Boolean(state?.focused);
      window.dispatchEvent(new Event("rmes-native-visibility"));
      if(desktopWindowVisible){refreshNotifications();window.RMesRealtime?.resync?.()}
    });
  }
  function appReallyActive(){return desktopWindowVisible&&desktopWindowFocused&&!document.hidden}
  function showInAppMessageToast({title,body,url,avatar}){
    let wrap=document.querySelector("#rmesMessageToastStack");
    if(!wrap){wrap=document.createElement("div");wrap.id="rmesMessageToastStack";wrap.className="rmes-message-toast-stack";document.body.appendChild(wrap)}
    const el=document.createElement("button");el.type="button";el.className="rmes-message-toast";
    const safeTitle=RMesUI.esc(title||"R-Messanger"),safeBody=RMesUI.esc(body||"Новое сообщение");
    let avatarHtml='<img class="rmes-message-toast-logo" src="/static/rmes-icon.png" alt="R-Messanger">';
    if(avatar)avatarHtml+=`<img class="rmes-message-toast-avatar" src="${RMesUI.esc(avatar)}" alt="">`;
    el.innerHTML=`${avatarHtml}<span class="rmes-message-toast-copy"><small>R-Messanger</small><b>${safeTitle}</b><em>${safeBody}</em></span><span class="rmes-message-toast-close">×</span>`;
    el.addEventListener("click",e=>{if(e.target.closest(".rmes-message-toast-close")){el.remove();return}location.href=url||"/"});
    wrap.appendChild(el);requestAnimationFrame(()=>el.classList.add("show"));
    setTimeout(()=>{el.classList.remove("show");setTimeout(()=>el.remove(),180)},6500);
    return true;
  }
  async function showDesktopMessageNotification(item){
    if(!globalCfg.desktopNotifications||!notificationCategoryEnabled(item.conversation_kind)||item.notify_allowed===false)return false;
    if(Number(item.sender?.id||item.sender_id||0)===Number(globalCfg.userId||0))return false;
    const sameChat=String(item.conversation_id)===String(globalCfg.currentConversationId||"");
    if(sameChat&&globalCfg.suppressActiveChatNotifications&&appReallyActive())return false;
    const locked=Boolean(document.querySelector("#appLockScreen"));
    const senderName=item.sender?.name||item.sender_name||item.sender||item.chat||"R-Messanger";
    const title=locked||globalCfg.showSenderName===false?"R-Messanger":senderName;
    const body=locked||globalCfg.showMessagePreview===false?"Новое сообщение":(item.body||"Новое сообщение");
    const url=item.url||`/c/${item.conversation_id}/`;
    let avatar=item.avatar||item.sender?.avatar||"";try{if(avatar)avatar=new URL(avatar,location.origin).toString()}catch(_){}
    if(globalCfg.notificationSound)notificationPing();
    // When the app is visible, render our own Telegram-like toast inside R-Messanger.
    // When it is hidden/minimized, Desktop creates a branded always-on-top R-Messanger window.
    if(appReallyActive()&&!sameChat)return showInAppMessageToast({title,body,url,avatar});
    if(window.RMesDesktop?.showNotification){
      try{const result=await window.RMesDesktop.showNotification({title,body,url,icon:avatar,silent:!globalCfg.notificationSound,tag:`rmes-message-${item.id}`});if(result?.ok!==false)return true}catch(_){}
    }
    // Browser fallback keeps the event visible if the Electron toast cannot be created.
    if("Notification" in window&&Notification.permission==="granted"){
      try{const n=new Notification(title,{body,icon:avatar||undefined,tag:`rmes-message-${item.id}`});n.onclick=()=>{window.focus();location.href=url;n.close()};return true}catch(_){}
    }
    return showInAppMessageToast({title,body,url,avatar});
  }
  async function refreshNotifications(){
    if(!globalCfg.notificationUrl)return;
    try{
      const suffix=desktopMessageCursor?`?after_message_id=${encodeURIComponent(desktopMessageCursor)}`:"";
      const r=await fetch(globalCfg.notificationUrl+suffix,{headers:{"X-Requested-With":"XMLHttpRequest"},cache:"no-store"});
      if(authSessionLost(r)||!r.ok)return;
      const data=await r.json();if(data.server_time)syncServerClock(data.server_time);renderNotifications(data);applyChatUnreadCounts(data.chat_unread_counts||{});
      for(const item of (data.desktop_messages||[])){
        const id=String(item.id||"");
        if(id&&notifiedMessageIds.has(id))continue;
        const shown=await showDesktopMessageNotification(item);
        if(shown&&id){notifiedMessageIds.add(id);if(notifiedMessageIds.size>600)notifiedMessageIds.delete(notifiedMessageIds.values().next().value)}
      }
      if(data.message_cursor!==undefined){desktopMessageCursor=String(data.message_cursor||0);localStorage.setItem(`rmes:desktop-message-cursor:${globalCfg.userId||"0"}`,desktopMessageCursor)}
    }catch(_){}
  }
  notificationBell?.addEventListener("click",()=>refreshNotifications());
  refreshNotifications();
  // WebSocket is primary; 2.5 s polling is a deliberate recovery path for sleeping/minimized clients.
  setInterval(refreshNotifications,5000);

  if(globalCfg.desktopNotifications&&!window.RMesDesktop?.showNotification&&"Notification" in window&&Notification.permission==="default"){
    setTimeout(()=>Notification.requestPermission().catch(()=>{}),900);
  }

  function updateSidebarFromMessage(item){
    const card=document.querySelector(`.tg-chat-item[data-conversation-id="${CSS.escape(String(item.conversation_id||""))}"]`);
    if(!card){refreshSidebarState();return}
    const preview=card.querySelector(".tg-chat-preview"),time=card.querySelector(".tg-chat-topline time");
    const mine=Number(item.sender?.id||0)===Number(globalCfg.userId||0);
    let body=String(item.body||"").replace(/\s+/g," ").trim();
    if(!body){const a=(item.attachments||[])[0];body=a?.content_type?.startsWith("image/")?"Фото":a?.content_type?.startsWith("video/")?"Видео":a?.content_type?.startsWith("audio/")?"Голосовое сообщение":a?`Файл: ${a.name||"вложение"}`:"Новое сообщение"}
    if(preview)preview.innerHTML=`${mine?'<span class="you-prefix">Вы:</span> ':""}${RMesUI.esc(body.length>58?body.slice(0,57)+"…":body)}`;
    if(time)time.textContent=displayClock(item);
    const list=card.parentElement;if(list&&list.firstElementChild!==card)list.prepend(card);
    if(!mine&&String(item.conversation_id)!==String(globalCfg.currentConversationId||"")){
      let badge=card.querySelector(".tg-unread");
      if(!badge){badge=document.createElement("span");badge.className="tg-unread";card.querySelector(".tg-chat-bottomline")?.appendChild(badge)}
      if(badge){const n=Math.min(999,(Number((badge.textContent||"").replace(/\D/g,""))||0)+1);badge.textContent=String(n)}
    }
    recomputeChatUnreadTotal();
  }
  function sidebarCardHtml(row){
    const peer=row.peer||null,initial=(row.title||"?").slice(0,1).toUpperCase();
    const avatar=peer?.avatar?`<img src="${RMesUI.esc(peer.avatar)}" alt="">`:`<span>${row.kind==="channel"?"#":RMesUI.esc(initial)}</span>`;
    const peerHidden=Boolean(peer?.hidden)||(Boolean(peer?.developer)&&!globalCfg.isDeveloper);
    const online=peer&&!peerHidden?`<span class="tg-online-dot ${peer.online?"":"hidden"}" data-online-dot></span>`:"";
    const last=row.last||{},preview=last.body||"Нет сообщений";
    return `<a class="tg-chat-item ${String(row.id)===String(globalCfg.currentConversationId||"")?"active":""}" data-conversation-id="${RMesUI.esc(row.id)}" data-peer-id="${peer?.id||""}" data-soft-nav="1" href="${RMesUI.esc(row.url||(`/c/${row.id}/`))}">
      <div class="tg-avatar-wrap"><div class="tg-avatar">${avatar}</div>${online}</div>
      <div class="tg-chat-copy"><div class="tg-chat-topline"><div class="tg-chat-title">${row.pinned?'<span class="mini-text-icon">📌</span>':""}<span>${RMesUI.esc(row.title||"Чат")}</span>${row.muted?'<span class="mini-text-icon">🔕</span>':""}</div><time>${last.created_at?displayClock(last):""}</time></div>
      <div class="tg-chat-bottomline"><div class="tg-chat-preview">${last.mine?'<span class="you-prefix">Вы:</span> ':""}${RMesUI.esc(preview.length>54?preview.slice(0,53)+"…":preview)}</div>${row.unread?`<span class="tg-unread">${row.unread>99?"99+":row.unread}</span>`:""}</div></div></a>`;
  }
  let sidebarSyncBusy=false;
  async function refreshSidebarState(){
    const list=document.querySelector("#chatList");if(!list||!globalCfg.sidebarStateUrl||sidebarSyncBusy)return;
    sidebarSyncBusy=true;
    try{
      const r=await fetch(`${globalCfg.sidebarStateUrl}?folder=${encodeURIComponent(globalCfg.currentFolder||"all")}`,{headers:{"X-Requested-With":"XMLHttpRequest"},cache:"no-store"});
      if(authSessionLost(r)||!r.ok)return;const data=await r.json();if(data.server_time)syncServerClock(data.server_time);
      const keep=new Set();
      for(const row of (data.results||[])){
        keep.add(String(row.id));
        const existing=list.querySelector(`.tg-chat-item[data-conversation-id="${CSS.escape(String(row.id))}"]`);
        const wrap=document.createElement("div");wrap.innerHTML=sidebarCardHtml(row);const fresh=wrap.firstElementChild;
        if(existing)existing.replaceWith(fresh);else list.appendChild(fresh);
      }
      list.querySelectorAll(".tg-chat-item[data-conversation-id]").forEach(x=>{if(!keep.has(String(x.dataset.conversationId||"")))x.remove()});
      recomputeChatUnreadTotal();
    }catch(_){}finally{sidebarSyncBusy=false}
  }
  setInterval(refreshSidebarState,4000);
  function formatLastSeen(iso){
    const lang=globalCfg.language||document.body?.dataset.language||"ru";
    if(!iso)return lang==="en"?"last seen a long time ago":lang==="uz"?"uzoq vaqt oldin onlayn bo‘lgan":"давно не был(а) в сети";
    const d=new Date(iso),diff=Math.max(0,serverNow()-d.getTime());
    if(diff<60000)return lang==="en"?"last seen just now":lang==="uz"?"hozirgina onlayn edi":"был(а) только что";
    if(diff<3600000){const minutes=Math.max(1,Math.floor(diff/60000));return lang==="en"?`last seen ${minutes} min ago`:lang==="uz"?`${minutes} daqiqa oldin onlayn edi`:`был(а) ${minutes} мин. назад`}
    if(dayFormatter.format(d)===dayFormatter.format(new Date(serverNow())))return lang==="en"?`last seen today at ${appClock(d)}`:lang==="uz"?`bugun ${appClock(d)} da onlayn edi`:`был(а) сегодня в ${appClock(d)}`;
    return lang==="en"?`last seen ${dateFormatter.format(d)} ${appClock(d)}`:lang==="uz"?`${dateFormatter.format(d)} da onlayn edi`:`был(а) ${dateFormatter.format(d)} в ${appClock(d)}`;
  }
  function hiddenPresenceLabel(){
    const lang=globalCfg.language||document.body?.dataset.language||"ru";
    return lang==="en"?"last seen time hidden":lang==="uz"?"oxirgi tashrif vaqti yashirilgan":"время посещения скрыто";
  }
  function recentlyPresenceLabel(){
    const lang=globalCfg.language||document.body?.dataset.language||"ru";
    return lang==="en"?"last seen recently":lang==="uz"?"yaqinda onlayn edi":"был(а) недавно";
  }
  function onlinePresenceLabel(){
    const lang=globalCfg.language||document.body?.dataset.language||"ru";
    return lang==="en"?"online":lang==="uz"?"onlayn":"в сети";
  }
  function applyPresence(item){
    const uid=String(item.user_id||"");if(!uid)return;
    const developer=Boolean(item.developer===true||item.developer==="true"||item.developer===1);
    let visibility=String(item.visibility||"").toLowerCase();
    if(!visibility)visibility=Boolean(item.hidden)||(developer&&!globalCfg.isDeveloper)?"hidden":"exact";
    // The browser never reconstructs exact presence from a privacy-safe payload.
    // Developer receives visibility=exact from the server regardless of peer privacy.
    const hidden=visibility==="hidden";
    const approximate=visibility==="recently";
    const online=visibility==="exact"&&Boolean(item.online);
    document.querySelectorAll(`.tg-chat-item[data-peer-id="${CSS.escape(uid)}"] [data-online-dot]`).forEach(dot=>dot.classList.toggle("hidden",!online));
    if(String(globalCfg.currentPeerId||"")===uid){
      const status=document.querySelector("#peerStatus");
      if(status)status.textContent=hidden?hiddenPresenceLabel():approximate?(item.label||recentlyPresenceLabel()):(item.label||(online?onlinePresenceLabel():formatLastSeen(item.last_seen_at_ms||item.last_seen_at)));
    }
  }

  window.RMesPresence={apply:applyPresence,formatLastSeen};
  async function refreshPresenceBatch(){
    if(!globalCfg.presenceBatchUrl)return;
    const ids=new Set();document.querySelectorAll(".tg-chat-item[data-peer-id]").forEach(x=>{if(x.dataset.peerId)ids.add(x.dataset.peerId)});if(globalCfg.currentPeerId)ids.add(String(globalCfg.currentPeerId));
    if(!ids.size)return;
    try{const r=await fetch(`${globalCfg.presenceBatchUrl}?ids=${encodeURIComponent([...ids].join(","))}`,{headers:{"X-Requested-With":"XMLHttpRequest"},cache:"no-store"});if(authSessionLost(r)||!r.ok)return;const j=await r.json();syncServerClock(j.server_time);Object.entries(j.users||{}).forEach(([user_id,row])=>applyPresence({user_id,...row}))}catch(_){}
  }
  let appWs=null,appWsTimer=null,appWsDelay=700,lastAppPong=Date.now(),presenceActiveSent=null,presenceClosing=false;
  // A presence lease belongs to this document, not to the account, focus or
  // sessionStorage.  A normal page navigation therefore closes only the old
  // document while the new document opens its own lease.  Multiple tabs and
  // devices remain online independently until the last lease disappears.
  const presenceClientId=`page-${globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}`}`.slice(0,96);
  const appWsScheme=location.protocol==="https:"?"wss":"ws";
  // Telegram-like foreground presence: a window is online only while it is
  // actually visible and focused. Other R-Messanger tabs/devices have independent
  // leases, so one background tab cannot keep the whole account online.
  function currentPresenceActive(){
    if(presenceClosing||document.hidden||!document.hasFocus())return false;
    if(window.RMesDesktop?.isDesktop&&(desktopWindowVisible===false||desktopWindowFocused===false))return false;
    return true;
  }
  async function publishPresenceHttp(active){
    if(!globalCfg.presenceUrl)return;
    const params=new URLSearchParams({active:active?"1":"0",client_id:presenceClientId});
    try{
      const r=await fetch(globalCfg.presenceUrl,{method:"POST",credentials:"same-origin",keepalive:true,headers:{"X-CSRFToken":RMesUI.csrf(),"X-Requested-With":"XMLHttpRequest","Content-Type":"application/x-www-form-urlencoded;charset=UTF-8","X-R-Mes-Presence-Client":presenceClientId},body:params});
      if(authSessionLost(r))return;
      if(r.ok){const j=await r.json().catch(()=>null);if(j?.server_time)syncServerClock(j.server_time);return}
    }catch(_){/* GET below is the CSRF-free recovery path. */}
    try{
      const r=await fetch(`${globalCfg.presenceUrl}?${params.toString()}`,{method:"GET",credentials:"same-origin",headers:{"X-Requested-With":"XMLHttpRequest","X-R-Mes-Presence-Client":presenceClientId},cache:"no-store"});
      if(authSessionLost(r))return;
      if(r.ok){const j=await r.json().catch(()=>null);if(j?.server_time)syncServerClock(j.server_time)}
    }catch(_){ }
  }
  function sendPresence(force=false){
    const active=currentPresenceActive();if(!force&&presenceActiveSent===active)return;presenceActiveSent=active;
    if(appWs&&appWs.readyState===WebSocket.OPEN)appWs.send(JSON.stringify({type:"presence",active,client_id:presenceClientId}));
    else publishPresenceHttp(active);
  }
  function publishPresenceClose(){
    if(presenceClosing)return;
    presenceClosing=true;presenceActiveSent=false;
    if(!globalCfg.presenceUrl)return;
    const params=new URLSearchParams({active:"0",client_id:presenceClientId,csrfmiddlewaretoken:RMesUI.csrf()});
    try{
      if(navigator.sendBeacon?.(globalCfg.presenceUrl,params))return;
    }catch(_){}
    publishPresenceHttp(false);
  }
  let pendingGlobalCall=null,globalCallRingTimer=null;
  const globalCallOverlay=document.querySelector("#globalIncomingCall");
  const globalCallAccept=document.querySelector("#globalCallAccept");
  const globalCallReject=document.querySelector("#globalCallReject");
  function callSignal(payload){
    if(appWs&&appWs.readyState===WebSocket.OPEN){
      try{appWs.send(JSON.stringify(payload));return true}catch(_){}
    }
    if(!globalCfg.callSignalUrl)return false;
    callSignalHttp(payload).catch(()=>{});
    return true;
  }
  async function callSignalHttp(payload){
    if(!globalCfg.callSignalUrl)throw new Error("Сигнализация звонка недоступна");
    const r=await fetch(globalCfg.callSignalUrl,{method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":RMesUI.csrf(),"X-Requested-With":"XMLHttpRequest","Content-Type":"application/json"},body:JSON.stringify({...payload,media:"audio"})});
    if(authSessionLost(r))throw new Error("Сессия завершена");
    const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||"Сигнализация звонка недоступна");return j;
  }
  function stopGlobalCallRing(){if(globalCallRingTimer){clearInterval(globalCallRingTimer);globalCallRingTimer=null}}
  function globalCallPing(){
    try{const ctx=new (window.AudioContext||window.webkitAudioContext)(),o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=620;g.gain.value=.035;o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.12)}catch(_){}
  }
  function hideGlobalIncoming(){stopGlobalCallRing();globalCallOverlay?.classList.add("hidden");pendingGlobalCall=null}
  function showGlobalIncoming(d){
    if(!d?.call_id||!d?.conversation_id)return;
    const existing=sessionStorage.getItem("rmes:pending-call");
    if(existing){try{const e=JSON.parse(existing);if(e.call_id&&e.call_id!==d.call_id){callSignal({type:"call_busy",call_id:d.call_id,conversation_id:d.conversation_id,reason:"busy"});return}}catch(_){}}
    pendingGlobalCall={...d,media:"audio",received_at:serverNow()};
    sessionStorage.setItem("rmes:pending-call",JSON.stringify(pendingGlobalCall));
    const name=d.from_name||"Пользователь";
    const nameEl=document.querySelector("#globalCallName"),typeEl=document.querySelector("#globalCallType"),avatarEl=document.querySelector("#globalCallAvatar");
    if(nameEl)nameEl.textContent=name;
    if(typeEl)typeEl.textContent="Входящий аудиозвонок";
    if(avatarEl){avatarEl.innerHTML=d.from_avatar?`<img src="${RMesUI.esc(d.from_avatar)}" alt="">`:`<span>${RMesUI.esc(name.slice(0,1).toUpperCase())}</span>`}
    globalCallOverlay?.classList.remove("hidden");
    stopGlobalCallRing();globalCallPing();globalCallRingTimer=setInterval(globalCallPing,1700);
    if(!appReallyActive()){
      let callAvatar=d.from_avatar||"";try{if(callAvatar)callAvatar=new URL(callAvatar,location.origin).toString()}catch(_){}
      const callUrl=`/c/${encodeURIComponent(d.conversation_id)}/?incoming_call=${encodeURIComponent(d.call_id)}`;
      const browserFallback=()=>{
        if("Notification" in window&&Notification.permission==="granted"){
          try{const n=new Notification("Входящий звонок",{body:`${name} · аудиозвонок`,icon:callAvatar||undefined,tag:`rmes-call-${d.call_id}`,requireInteraction:true});n.onclick=()=>{window.focus();location.href=callUrl;n.close()}}catch(_){}
        }
      };
      if(window.RMesDesktop?.showNotification){
        window.RMesDesktop.showNotification({title:"Входящий звонок",body:`${name} · аудиозвонок`,url:callUrl,icon:callAvatar,silent:false,tag:`rmes-call-${d.call_id}`}).then(result=>{if(result?.ok===false)browserFallback()}).catch(browserFallback);
      }else browserFallback();
    }
  }
  globalCallAccept?.addEventListener("click",()=>{
    if(!pendingGlobalCall)return;
    const d={...pendingGlobalCall,auto_accept:true};
    sessionStorage.setItem("rmes:pending-call",JSON.stringify(d));
    stopGlobalCallRing();globalCallOverlay?.classList.add("hidden");
    if(String(globalCfg.currentConversationId||"")===String(d.conversation_id||"")&&window.RMesChatCalls?.handleSignal){
      pendingGlobalCall=null;
      window.RMesChatCalls.handleSignal(d).then(()=>window.RMesChatCalls?.accept?.()).catch(()=>{});
      return;
    }
    location.href=`/c/${encodeURIComponent(d.conversation_id)}/?incoming_call=${encodeURIComponent(d.call_id)}`;
  });
  globalCallReject?.addEventListener("click",()=>{
    if(pendingGlobalCall)callSignal({type:"call_reject",call_id:pendingGlobalCall.call_id,conversation_id:pendingGlobalCall.conversation_id,reason:"declined"});
    sessionStorage.removeItem("rmes:pending-call");hideGlobalIncoming();
  });

  const seenCallSignals=new Set();
  function rememberCallSignal(d){
    const key=d.signal_id?`id:${d.signal_id}`:`${d.type}:${d.call_id||""}:${d.from_user||""}:${JSON.stringify(d.candidate||d.sdp||d.reason||"").slice(0,180)}`;
    if(seenCallSignals.has(key))return false;seenCallSignals.add(key);if(seenCallSignals.size>800)seenCallSignals.delete(seenCallSignals.values().next().value);return true;
  }
  function handleAppRealtime(d){
    if(d.server_time||d.ts)syncServerClock(d.server_time||d.ts);
    if(["call_offer","call_answer","call_ice","call_end","call_reject","call_busy","call_error"].includes(d.type)){
      if(d.type==="call_offer"&&d.created_at&&serverNow()-new Date(d.created_at).getTime()>45000)return;
      if(!rememberCallSignal(d))return;
      if(d.type==="call_offer"){showGlobalIncoming(d);return}
      const sameConversation=String(d.conversation_id||"")===String(globalCfg.currentConversationId||"");
      if(sameConversation&&window.RMesChatCalls?.handleSignal){window.RMesChatCalls.handleSignal(d).catch(()=>{});return}
      if(pendingGlobalCall&&String(pendingGlobalCall.call_id)===String(d.call_id||"")){
        if(d.type==="call_ice"&&d.candidate){
          pendingGlobalCall.pending_ice=[...(pendingGlobalCall.pending_ice||[]),d.candidate].slice(-80);
          sessionStorage.setItem("rmes:pending-call",JSON.stringify(pendingGlobalCall));
        }else if(["call_end","call_reject","call_busy","call_error"].includes(d.type)){sessionStorage.removeItem("rmes:pending-call");hideGlobalIncoming()}
      }
      return;
    }
    if(d.type==="message"){
      const id=String(d.id||"");if(id&&seenRealtimeMessages.has(id))return;if(id){seenRealtimeMessages.add(id);if(seenRealtimeMessages.size>500)seenRealtimeMessages.delete(seenRealtimeMessages.values().next().value)}
      updateSidebarFromMessage(d);
      try{window.dispatchEvent(new CustomEvent("rmes:global-message",{detail:d}))}catch(_){}
      showDesktopMessageNotification(d).then(shown=>{if(shown&&id){notifiedMessageIds.add(id);if(notifiedMessageIds.size>600)notifiedMessageIds.delete(notifiedMessageIds.values().next().value)}}).catch(()=>{});
      setTimeout(refreshNotifications,80);
    }else if(d.type==="message_updated"){
      updateSidebarFromMessage(d);
      try{window.dispatchEvent(new CustomEvent("rmes:global-message-updated",{detail:d}))}catch(_){}
    }else if(d.type==="presence")applyPresence(d);
    else if(d.type==="read"){try{window.dispatchEvent(new CustomEvent("rmes:receipt-read",{detail:d}))}catch(_){}}
    else if(d.type==="pong"||d.type==="app_ready")lastAppPong=Date.now();
  }
  let callPollBusy=false;
  const callCursorKey=`rmes:call-cursor:v138:${globalCfg.userId||"0"}`;
  let callCursor=sessionStorage.getItem(callCursorKey)||"0";
  async function pollCallSignals(){
    if(!globalCfg.callPollUrl||callPollBusy)return;callPollBusy=true;
    try{const sep=globalCfg.callPollUrl.includes("?")?"&":"?";const r=await fetch(`${globalCfg.callPollUrl}${sep}after=${encodeURIComponent(callCursor)}&client_id=${encodeURIComponent(presenceClientId)}`,{headers:{"X-Requested-With":"XMLHttpRequest"},cache:"no-store"});if(authSessionLost(r)||!r.ok)return;const j=await r.json();syncServerClock(j.server_time);for(const evt of (j.events||[]))handleAppRealtime(evt);if(j.cursor!==undefined){callCursor=String(j.cursor||0);sessionStorage.setItem(callCursorKey,callCursor)}}catch(_){}finally{callPollBusy=false}
  }
  pollCallSignals();setInterval(pollCallSignals,1000);
  function connectAppWs(){
    clearTimeout(appWsTimer);
    if(presenceClosing)return;
    if(appWs&&(appWs.readyState===WebSocket.CONNECTING||appWs.readyState===WebSocket.OPEN))return;
    try{appWs=new WebSocket(`${appWsScheme}://${location.host}/ws/app/?client_id=${encodeURIComponent(presenceClientId)}`)}catch(_){scheduleAppWs();return}
    appWs.onopen=()=>{appWsDelay=700;lastAppPong=Date.now();presenceActiveSent=null;sendPresence(true);refreshNotifications();refreshPresenceBatch()};
    appWs.onmessage=e=>{try{handleAppRealtime(JSON.parse(e.data))}catch(_){}};
    appWs.onclose=event=>{appWs=null;if(event?.code===4401){presenceClosing=true;presenceActiveSent=false;return}if(!presenceClosing){publishPresenceHttp(currentPresenceActive());scheduleAppWs()}};appWs.onerror=()=>{};
  }
  function scheduleAppWs(){clearTimeout(appWsTimer);appWsTimer=setTimeout(connectAppWs,appWsDelay);appWsDelay=Math.min(Math.round(appWsDelay*1.7),8000)}
  connectAppWs();
  const heartbeat=setInterval(()=>{
    const active=currentPresenceActive();
    if(appWs&&appWs.readyState===WebSocket.OPEN){
      if(active)appWs.send(JSON.stringify({type:"presence_ping"}));
      else sendPresence(true);
      if(Date.now()-lastAppPong>12000){try{appWs.close()}catch(_){}}
    }else publishPresenceHttp(active);
  },3000);
  const presenceRefresh=setInterval(refreshPresenceBatch,4000);
  const activityChanged=()=>{sendPresence(true);if(currentPresenceActive()){refreshNotifications();refreshPresenceBatch()}};
  window.addEventListener("focus",activityChanged);window.addEventListener("blur",activityChanged);document.addEventListener("visibilitychange",activityChanged);window.addEventListener("rmes-native-visibility",activityChanged);
  window.addEventListener("online",()=>{if(!presenceClosing){connectAppWs();sendPresence(true)}refreshNotifications();refreshPresenceBatch()});
  window.addEventListener("pagehide",publishPresenceClose);
  window.addEventListener("pageshow",event=>{if(!event.persisted)return;presenceClosing=false;presenceActiveSent=null;connectAppWs();sendPresence(true);refreshPresenceBatch()});
  window.RMesRealtime={
    resync:()=>{if(appWs&&appWs.readyState===WebSocket.OPEN)appWs.send(JSON.stringify({type:"resync"}));refreshNotifications();refreshPresenceBatch()},
    socket:()=>appWs,
    sendCall:payload=>callSignal({...payload,media:"audio"}),
    sendCallFallback:payload=>callSignalHttp({...payload,media:"audio"})
  };

  // SPA-like navigation: aggressively prefetch likely chat destinations and keep sidebar scroll position.
  const chatList=document.querySelector("#chatList");
  if(chatList){
    const saved=sessionStorage.getItem("rmes:sidebar-scroll");if(saved)chatList.scrollTop=Number(saved)||0;
    chatList.addEventListener("scroll",RMesUI.debounce(()=>sessionStorage.setItem("rmes:sidebar-scroll",String(chatList.scrollTop)),80),{passive:true});
  }
  const prefetched=new Set();
  document.addEventListener("pointerenter",e=>{
    const a=e.target.closest?.('a[data-soft-nav="1"]');if(!a||prefetched.has(a.href))return;prefetched.add(a.href);
    fetch(a.href,{credentials:"same-origin",headers:{"X-R-Mes-Prefetch":"1"}}).catch(()=>{});
  },true);

  const input=document.querySelector("#globalSearch");
  const results=document.querySelector("#globalSearchResults");
  const clear=document.querySelector("#clearGlobalSearch");
  if(!input||!results||!globalCfg.searchUrl)return;

  const avatar=(row)=>row.avatar
    ?`<div class="tg-avatar tg-avatar-sm"><img src="${row.avatar}" alt=""></div>`
    :`<div class="tg-avatar tg-avatar-sm"><span>${RMesUI.esc(row.initials||"?")}</span></div>`;

  function section(title,items,renderer){
    if(!items?.length)return "";
    return `<div class="tg-search-section"><div class="tg-search-section-title">${title}</div>${items.map(renderer).join("")}</div>`;
  }

  function render(data){
    const people=section("Люди",data.people,p=>`
      <a class="tg-search-result" href="${p.blocked?"#":p.url}" ${p.blocked?'data-blocked-result="1"':""}>
        ${avatar(p)}
        <div class="tg-search-result-copy"><b>${RMesUI.esc(p.name)}</b>
          <span>${p.handle?`@${RMesUI.esc(p.handle)} · `:""}${RMesUI.esc(p.status||p.email)}</span>
        </div>
        ${p.blocked?'<span class="tg-search-tag">заблокирован</span>':""}
      </a>`);
    const chats=section("Чаты",data.chats,c=>`
      <a class="tg-search-result" href="${c.url}">
        ${avatar(c)}
        <div class="tg-search-result-copy"><b>${RMesUI.esc(c.title)}</b><span>${c.kind==="channel"?"Канал":c.kind==="group"?"Группа":"Личный чат"}</span></div>
        ${c.unread?`<span class="tg-unread">${c.unread}</span>`:""}
      </a>`);
    const msgs=section("Сообщения",data.messages,m=>`
      <a class="tg-search-message-result" href="${m.url}">
        <div class="tg-search-message-head"><b>${RMesUI.esc(m.chat)}</b><time>${RMesUI.esc(m.time)}</time></div>
        <span><strong>${RMesUI.esc(m.sender)}:</strong> ${RMesUI.esc(m.text)}</span>
      </a>`);
    results.innerHTML=people+chats+msgs || '<div class="tg-search-empty">Ничего не найдено</div>';
    window.RMesI18n?.refresh?.();
    results.classList.remove("hidden");
  }

  const run=RMesUI.debounce(async()=>{
    const q=input.value.trim();
    clear?.classList.toggle("hidden",!q);
    if(!q){results.classList.add("hidden");results.innerHTML="";return;}
    try{
      const r=await fetch(`${globalCfg.searchUrl}?q=${encodeURIComponent(q)}`,{headers:{"X-Requested-With":"XMLHttpRequest"}});
      if(!r.ok)throw new Error();
      render(await r.json());
    }catch(_){
      results.innerHTML='<div class="tg-search-empty">Ошибка поиска</div>';results.classList.remove("hidden");
    }
  },140);

  input.addEventListener("input",run);
  input.addEventListener("focus",()=>{if(input.value.trim())run()});
  clear?.addEventListener("click",()=>{input.value="";input.focus();clear.classList.add("hidden");results.classList.add("hidden")});
  results.addEventListener("click",e=>{
    if(e.target.closest("[data-blocked-result]")){e.preventDefault();RMesUI.toast("Диалог недоступен из-за блокировки","error")}
  });
  document.addEventListener("click",e=>{if(!results.contains(e.target)&&e.target!==input)results.classList.add("hidden")});
});

// R-Messanger poll voting.
document.addEventListener("click",async e=>{
  const btn=e.target.closest?.("[data-poll-vote-url]");
  if(!btn)return;
  e.preventDefault();
  try{
    const fd=new FormData();fd.append("option_id",btn.dataset.optionId);
    const r=await fetch(btn.dataset.pollVoteUrl,{method:"POST",headers:{"X-CSRFToken":RMesUI.csrf(),"X-Requested-With":"XMLHttpRequest"},body:fd});
    const j=await r.json();if(!r.ok)throw new Error(j.detail||"Ошибка голосования");
    if(j.poll){
      const box=btn.closest(".tg-poll");
      j.poll.options.forEach(o=>{const x=box.querySelector(`[data-option-id="${o.id}"] b`);if(x)x.textContent=o.votes});
      const meta=box.querySelector(".tg-poll-meta");if(meta)meta.textContent=`${j.poll.options.reduce((a,o)=>a+o.votes,0)} голосов${j.poll.anonymous?" · анонимный":""}${j.poll.multiple_choice?" · несколько вариантов":""}`;
    }
  }catch(err){RMesUI.toast(err.message,"error")}
});

// R-Messanger v12: one passcode lock for web and Desktop sessions.
(function(){
  function csrf(){return window.RMesUI?.csrf?.()||""}
  async function post(url,data={}){
    const r=await fetch(url,{method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":csrf(),"X-Requested-With":"XMLHttpRequest","Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"},body:new URLSearchParams(data)});
    const j=await r.json().catch(()=>({}));
    return {r,j};
  }
  document.addEventListener("DOMContentLoaded",()=>{
    if(document.querySelector("#appLockScreen"))return;
    if(document.body.dataset.appLockEnabled!=="1")return;
    const timeoutMinutes=Math.max(0,Number(document.body.dataset.appLockTimeout||0));
    let timer=null,lastHeartbeat=0,busy=false;
    const unlockUrl="/auth/app-lock/";

    async function goLocked(){
      if(location.pathname.startsWith(unlockUrl))return;
      location.assign(`${unlockUrl}?next=${encodeURIComponent(location.pathname+location.search)}`);
    }
    async function heartbeat(force=false){
      const now=Date.now();
      if(busy||(!force&&now-lastHeartbeat<25000))return;
      busy=true;lastHeartbeat=now;
      try{
        const {r,j}=await post("/auth/app-lock/activity/");
        if(r.status===423||j.locked)goLocked();
      }catch(_){}finally{busy=false}
    }
    function arm(){
      if(!timeoutMinutes)return;
      clearTimeout(timer);
      timer=setTimeout(()=>lockNow("timeout"),timeoutMinutes*60*1000);
    }
    async function lockNow(reason="manual"){
      if(busy)return;
      busy=true;
      try{await post("/auth/app-lock/lock/",{reason});}catch(_){}
      finally{busy=false;goLocked()}
    }
    function activity(){heartbeat(false);arm()}
    ["pointerdown","keydown","touchstart","wheel"].forEach(name=>window.addEventListener(name,activity,{passive:true}));
    document.addEventListener("visibilitychange",()=>{if(!document.hidden){heartbeat(true);arm()}});
    window.RMesLock={lockNow,heartbeat};
    heartbeat(true);arm();
  });
})();

document.addEventListener("click",e=>{
  const btn=e.target.closest?.("#sidebarLockNow,#quickLockBtn");
  if(!btn)return;
  e.preventDefault();
  if(btn.id==="quickLockBtn"&&btn.dataset.lockEnabled!=="1"){
    location.href=btn.dataset.lockSettings||"/auth/profile/#privacy";
    return;
  }
  window.RMesLock?.lockNow?.("menu");
});

// v13.1: server-driven native client update. Server/UI changes arrive immediately.
// Native EXE/APK updates become installable as soon as an artifact is published on the server.
document.addEventListener("DOMContentLoaded",()=>{
  const banner=document.querySelector("#clientUpdateBanner");
  if(!banner)return;
  let pollTimer=null;
  function updateButton(){return document.querySelector("#clientUpdateBtn")}
  async function install(){
    const btn=updateButton();if(!btn)return;
    const url=banner.dataset.updateUrl||"",version=banner.dataset.latestVersion||"",sha256=banner.dataset.updateSha256||"";
    if(!url){RMesUI.toast("Файл обновления ещё не опубликован");return}
    btn.disabled=true;btn.textContent="Загрузка…";
    try{
      if(window.RMesDesktop?.installUpdate){
        const result=await window.RMesDesktop.installUpdate({url,version,sha256});
        if(!result?.ok)throw new Error(result?.error||"Не удалось запустить обновление");
        btn.remove();
        const note=banner.querySelector(".client-update-note");
        if(note)note.textContent=result.managed?"Обновление загружается внутри приложения…":"Обновление запускается…";
        banner.dataset.installing="1";return;
      }
      banner.remove();
      location.href=url;
      setTimeout(()=>{btn.disabled=false;btn.textContent="Обновить"},2500);
    }catch(err){btn.disabled=false;btn.textContent="Обновить";RMesUI.toast(err.message||"Ошибка обновления","error")}
  }
  function bind(){updateButton()?.addEventListener("click",install,{once:true})}
  async function checkReady(){
    if(banner.dataset.ready==="1"){if(pollTimer)clearInterval(pollTimer);return}
    const platform=banner.dataset.platform||"",current=banner.dataset.currentVersion||"";
    if(!platform)return;
    try{
      const r=await fetch(`/ops/client-policy/?platform=${encodeURIComponent(platform)}&current=${encodeURIComponent(current)}`,{headers:{"X-Requested-With":"XMLHttpRequest"}});
      if(!r.ok)return;const j=await r.json();
      if(!j.available){banner.remove();if(pollTimer)clearInterval(pollTimer);return}
      if(j.artifact_ready&&j.update_url){
        banner.dataset.ready="1";banner.dataset.updateUrl=j.update_url;banner.dataset.updateSha256=j.sha256||"";banner.dataset.latestVersion=j.latest_version||banner.dataset.latestVersion;
        const status=banner.querySelector(".client-update-preparing");if(status)status.outerHTML='<button type="button" id="clientUpdateBtn">Обновить</button>';
        const note=banner.querySelector(".client-update-note");if(note)note.textContent=j.release_notes||"Пакет обновления готов к установке.";
        bind();if(pollTimer)clearInterval(pollTimer);
      }
    }catch(_){}
  }
  bind();
  window.RMesDesktop?.onUpdateState?.(state=>{
    if(state.state==="current"||state.state==="installed"){
      if(pollTimer)clearInterval(pollTimer);banner.remove();return;
    }
    const btn=updateButton();if(!btn)return;
    if(state.state==="downloading"){btn.disabled=true;btn.textContent=`Загрузка ${state.percent||0}%`}
    else if(state.state==="ready"){btn.disabled=false;btn.textContent="Перезапустить и обновить";btn.addEventListener("click",install,{once:true})}
    else if(state.state==="error"){btn.disabled=false;btn.textContent="Повторить обновление"}
  });
  if(banner.dataset.ready!=="1"){checkReady();pollTimer=setInterval(checkReady,10000)}
});


// Manual update check is always available in native clients.
document.addEventListener("click",async e=>{
  const btn=e.target.closest?.("#checkClientUpdateBtn");if(!btn)return;
  e.preventDefault();
  const ua=navigator.userAgent||"";
  const desktop=ua.match(/RMesDesktop\/([0-9A-Za-z._+-]+)/i);
  const android=ua.match(/RMesAndroid\/([0-9A-Za-z._+-]+)/i);
  const ios=ua.match(/RMesIOS\/([0-9A-Za-z._+-]+)/i);
  const platform=desktop?"windows":android?"android":ios?"ios":"";
  const current=(desktop||android||ios)?.[1]||"0";
  if(!platform){RMesUI.toast("Обновления доступны только в приложении");return}
  try{
    btn.disabled=true;
    const r=await fetch(`/ops/client-policy/?platform=${encodeURIComponent(platform)}&current=${encodeURIComponent(current)}`,{headers:{"X-Requested-With":"XMLHttpRequest"}});
    const j=await r.json();
    if(!r.ok)throw new Error("Не удалось проверить обновление");
    if(!j.available){RMesUI.toast(`Установлена актуальная версия ${current}`);return}
    if(!j.artifact_ready&&!j.update_url){RMesUI.toast(`Версия ${j.latest_version} уже объявлена, пакет ещё не опубликован`);return}
    if(window.RMesDesktop?.installUpdate){
      const result=await window.RMesDesktop.installUpdate({url:j.update_url,version:j.latest_version,sha256:j.sha256||""});
      if(!result?.ok)throw new Error(result?.error||"Не удалось установить обновление");
      return;
    }
    location.href=j.update_url;
  }catch(err){RMesUI.toast(err.message||"Ошибка обновления","error")}
  finally{btn.disabled=false}
});


// R-Messanger 15 native push bridge. Android/iOS emit this event after receiving
// their provider token. Registration uses the authenticated WebView session.
(() => {
  let pending=null,busy=false,retryTimer=null;
  async function register(detail){
    const cfg=window.R_MES_GLOBAL||{};if(!cfg.pushTokenUrl||!detail?.token||busy)return;
    pending=detail;busy=true;
    try{
      const r=await fetch(cfg.pushTokenUrl,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":RMesUI.csrf(),"X-Requested-With":"XMLHttpRequest"},credentials:"same-origin",body:JSON.stringify({token:detail.token,provider:detail.provider})});
      if(r.status===409){clearTimeout(retryTimer);retryTimer=setTimeout(()=>register(pending),1500);return}
      if(!r.ok)throw new Error(`push token ${r.status}`);
      pending=null;
    }catch(err){console.warn("R-Messanger push registration",err);clearTimeout(retryTimer);retryTimer=setTimeout(()=>pending&&register(pending),5000)}
    finally{busy=false}
  }
  window.addEventListener("rmes:native-push-token",e=>register(e.detail||{}));
  window.RMesNativePush={register};
})();


// R-Messanger native offline shell. Enabled only inside installed Android/iOS/Desktop
// clients on HTTPS, never for ordinary browsers.
(() => {
  const native=/RMes(?:Android|IOS|Desktop)\//i.test(navigator.userAgent||"");
  if(!native||!("serviceWorker" in navigator)||location.protocol!=="https:")return;
  navigator.serviceWorker.register("/sw.js",{scope:"/"}).catch(err=>console.warn("R-Messanger offline cache",err));
  document.addEventListener("click",e=>{
    const a=e.target.closest?.('a[href*="/auth/logout/"]');if(!a)return;
    navigator.serviceWorker.controller?.postMessage({type:"PURGE_PRIVATE"});
  });
})();


// rmes-mobile-touch-prefetch-safe
document.addEventListener("touchstart", function(e) {
  var a = e.target && e.target.closest ? e.target.closest('a[data-soft-nav="1"]') : null;
  if (!a || !a.href) return;
  try {
    fetch(a.href, {
      credentials: "same-origin",
      cache: "force-cache",
      headers: {"X-R-Mes-Prefetch": "1"}
    }).catch(function(){});
  } catch (_) {}
}, {passive: true, capture: true});
