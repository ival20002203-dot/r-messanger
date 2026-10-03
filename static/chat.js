(() => {
  const cfg=window.R_MES_CHAT;if(!cfg)return;
  const $=s=>document.querySelector(s);
  const $$=s=>[...document.querySelectorAll(s)];
  const esc=RMesUI.esc;
  const stream=$("#messageStream"),input=$("#messageInput"),typingIndicator=$("#typingIndicator");
  const scrollBtn=$("#scrollBottomBtn"),scrollCount=$("#scrollBottomCount");
  let replyTo=null,editId=null,forwardId=null,reactionId=null,deleteMessageId=null;
  let typingTimer=null,recorder=null,chunks=[],recorderStream=null,recordingCtx=null,recordingFrame=null,recordingMaxTimer=null,recordingStartedAt=0,recordingCancelled=false,pc=null,localStream=null,pendingOffer=null,pendingIce=[],callRemoteStream=null,callRecorder=null,callRecordingCtx=null,callRecordChunks=[],callStartedAt=null,callConnectedAt=null,callUploadPending=false,callInitiator=false,callRecordingId="";
  let historyLoading=false,historyHasMore=true,newWhileAway=0;
  let ws=null,reconnectDelay=900,reconnectTimer=null,exiting=false;

  const draftKey=`rmes:draft:${cfg.userId}:${cfg.conversationId}`;
  const offlineKey=`rmes:offline:${cfg.userId}:${cfg.conversationId}`;
  const makeClientId=()=>crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const url=(tpl,id)=>tpl.replace("__ID__",id);
  const node=id=>document.querySelector(`[data-message-id="${id}"]`);
  const clientNode=id=>id?document.querySelector(`[data-client-id="${CSS.escape(String(id))}"]`):null;
  const isNearBottom=()=>stream ? (stream.scrollHeight-stream.scrollTop-stream.clientHeight)<110 : true;
  const scrollBottom=(smooth=false)=>stream?.scrollTo({top:stream.scrollHeight,behavior:smooth?"smooth":"auto"});
  const uploadFiles=new Map();
  const uploadPreviewByAttachment=new Map();
  const serverTimestamp=()=>window.RMesServerClock?.now?.()||Date.now();
  const uiLocale=cfg.language==="en"?"en-GB":cfg.language==="uz"?"uz-UZ":"ru-RU";
  const formatClock=value=>{
    // The API already formatted this instant in the server timezone.  Prefer
    // that value so a workstation's timezone/clock can never change a chat
    // timestamp.  The epoch fallback is retained for optimistic/legacy rows.
    if(value&&typeof value==="object"){
      const explicit=String(value.time_hm||value.server_time_hm||"").trim();
      if(/^\d{1,2}:\d{2}$/.test(explicit))return explicit;
    }
    const raw=value?.created_at_ms||value?.created_at||value||serverTimestamp();const d=new Date(raw);
    return Number.isNaN(d.getTime())?"":new Intl.DateTimeFormat(uiLocale,{timeZone:cfg.serverTimeZone||"Asia/Tashkent",hour:"2-digit",minute:"2-digit",hour12:false}).format(d);
  };
  const formatBytes=n=>{n=Number(n||0);if(n<1024)return `${n} B`;if(n<1024*1024)return `${(n/1024).toFixed(n<10240?1:0)} KB`;return `${(n/1024/1024).toFixed(n<10*1024*1024?1:0)} MB`};
  const attachmentKind=ct=>String(ct||"").startsWith("image/")?"Фото":String(ct||"").startsWith("video/")?"Видео":String(ct||"").startsWith("audio/")?"Голосовое сообщение":"Файл";

  function updateScrollButton(){
    if(!stream||!scrollBtn)return;
    const away=!isNearBottom();
    scrollBtn.classList.toggle("hidden",!away);
    if(!away){newWhileAway=0;scrollCount?.classList.add("hidden");}
    else if(newWhileAway>0&&scrollCount){
      scrollCount.textContent=newWhileAway>99?"99+":String(newWhileAway);
      scrollCount.classList.remove("hidden");
    }
  }
  scrollBtn?.addEventListener("click",()=>{newWhileAway=0;scrollBottom(true);setTimeout(updateScrollButton,220)});
  const composerBox=document.querySelector(".tg-composer-area,.tg-composer-disabled");
  if(scrollBtn&&composerBox&&"ResizeObserver" in window){
    const syncScrollButtonOffset=()=>{scrollBtn.style.bottom=`${composerBox.offsetHeight+14}px`};
    new ResizeObserver(syncScrollButtonOffset).observe(composerBox);syncScrollButtonOffset();
  }

  const avatarHtml=s=>s?.avatar
    ?`<div class="tg-avatar tg-message-avatar"><img src="${s.avatar}" alt=""></div>`
    :`<div class="tg-avatar tg-message-avatar"><span>${esc(s?.initials||"?")}</span></div>`;

  function attachmentsHtml(list=[]){
    return list.map(a=>{
      const ct=String(a.content_type||"");
      const name=esc(a.name||attachmentKind(ct));
      const size=formatBytes(a.size||0);
      const status=String(a.scan_status||"safe");
      const uploading=status==="uploading";
      const progress=Math.max(0,Math.min(100,Number(a.upload_progress||0)));
      const local=a.local_url||"";
      const src=a.url||local;
      const pendingAttr=status==="pending"&&a.id?` data-pending-attachment="${esc(a.id)}"`:"";
      if(status==="infected")return `<div class="tg-attachment-card tg-attachment-blocked"><div class="tg-attachment-icon">!</div><div><b>${name}</b><span>Файл заблокирован проверкой безопасности</span></div></div>`;
      if(ct.startsWith("image/")){
        if(src&&cfg.mediaPreviews)return `<button type="button" class="tg-photo ${uploading?"is-pending":""}" data-lightbox="${esc(src)}" data-download="${esc(a.download_url||src)}"${pendingAttr}><img src="${esc(src)}" alt="${name}">${uploading?`<div class="tg-media-upload-state"><span class="tg-upload-ring" data-upload-client="${esc(a.client_id||"")}" style="--p:${progress}"></span><small>${progress}%</small></div>`:""}</button>`;
        return `<button type="button" class="tg-attachment-card" data-lightbox="${esc(src||"")}" data-download="${esc(a.download_url||src||"")}"${pendingAttr}><div class="tg-attachment-icon">🖼</div><div><b>${name}</b><span>Изображение · ${size}${status==="pending"?" · проверяем":""}</span></div></button>`;
      }
      if(ct.startsWith("video/")&&src)return `<div class="tg-video-local ${uploading?"is-pending":""}"${pendingAttr}><video class="tg-video" ${uploading?"muted":"controls"} preload="metadata" src="${esc(src)}"></video>${uploading?`<div class="tg-media-upload-state"><span class="tg-upload-ring" data-upload-client="${esc(a.client_id||"")}" style="--p:${progress}"></span><small>${progress}%</small></div>`:""}</div>`;
      if(ct.startsWith("audio/")&&src)return `<div class="tg-audio tg-voice-player ${uploading?"is-pending":""}"${pendingAttr}><button class="tg-voice-play" type="button" aria-label="Воспроизвести"><span>▶</span></button><div class="tg-voice-track"><div class="tg-voice-waveform" data-waveform></div><div class="tg-voice-time"><span data-current>0:00</span><span class="tg-voice-live-dot"></span><span data-duration>0:00</span></div></div><button class="tg-voice-speed" type="button" aria-label="Скорость">1×</button><audio preload="metadata" src="${esc(src)}"></audio>${uploading?`<small>${progress}%</small>`:""}</div>`;
      const kind=attachmentKind(ct);
      const href=a.preview_url||a.download_url||src||"";
      return `<${href?"a":"div"} class="tg-attachment-card ${uploading?"is-pending":""}" ${href?`href="${esc(href)}"`:""}${pendingAttr}><div class="tg-attachment-icon">${ct.startsWith("audio/")?"🎙":ct.startsWith("video/")?"▶":"📄"}</div><div class="tg-attachment-copy"><b>${name}</b><span>${uploading?`Отправка ${progress}% · ${size}`:`${kind} · ${size}${status==="pending"?" · проверяем":""}`}</span>${uploading?`<div class="tg-attachment-progress"><i style="width:${progress}%"></i></div>`:""}</div>${uploading?`<span class="tg-upload-ring" data-upload-client="${esc(a.client_id||"")}" style="--p:${progress}"></span>`:""}</${href?"a":"div"}>`;
    }).join("");
  }

  function richText(value){
    return esc(value||"").replace(/(^|\s)(@[a-z0-9_]{4,32}|@all|@everyone)/gi,'$1<span class="mention-token">$2</span>').replace(/\n/g,"<br>");
  }

  function reactionsHtml(r={},id){
    return Object.entries(r).map(([emoji,users])=>`<button class="tg-reaction-chip" data-emoji="${esc(emoji)}" data-react-url="${url(cfg.reactTemplate,id)}">${esc(emoji)} <span>${users.length}</span></button>`).join("");
  }

  function pollHtml(p){
    if(!p)return "";
    const options=(p.options||[]).map(o=>`
      <button type="button" class="tg-poll-option" data-poll-vote-url="/poll/${encodeURIComponent(p.id)}/vote/" data-option-id="${encodeURIComponent(o.id)}" ${p.closed?"disabled":""}>
        <span>${esc(o.text||"")}</span><b>${Number(o.votes||0)}</b>
      </button>`).join("");
    const total=(p.options||[]).reduce((sum,o)=>sum+Number(o.votes||0),0);
    return `<div class="tg-poll" data-poll-id="${esc(String(p.id))}">
      <div class="tg-poll-question">${esc(p.question||"Опрос")}</div>
      <div class="tg-poll-meta">${p.anonymous?"Анонимный":"Публичный"} · ${p.multiple_choice?"несколько ответов":"один ответ"}${p.closed?" · закрыт":""}</div>
      <div class="tg-poll-options">${options}</div>
      <div class="tg-poll-total">${total} ${total===1?"голос":"голосов"}</div>
    </div>`;
  }

  function renderMessage(m){
    const mine=Number(m.sender?.id)===Number(cfg.userId);
    const sender=m.sender||{name:"Удалённый пользователь",initials:"?"};
    const el=document.createElement("article");
    el.className=`tg-message ${mine?"mine":""} ${m._pending?"sending":""} ${m._failed?"send-failed":""}`.trim();
    const clientId=m.client_message_id||"";
    el.id=m._pending?`msg-pending-${clientId}`:`msg-${m.id}`;
    if(!m._pending)el.dataset.messageId=m.id;
    if(clientId)el.dataset.clientId=clientId;
    el.dataset.senderId=m.sender?.id||"";
    el.dataset.createdAt=m.created_at||"";
    const reply=m.reply_to?`<button class="tg-reply-quote" data-jump="${m.reply_to.id}" type="button"><b>${esc(m.reply_to.sender)}</b><span>${esc(m.reply_to.body)}</span></button>`:"";
    const forwarded=m.forwarded_from?`<div class="tg-forward-label">Переслано от ${esc(m.forwarded_from.sender)}</div>`:"";
    const body=m.is_deleted
      ?'<div class="tg-deleted-message">Сообщение удалено</div>'
      :`${m.poll?pollHtml(m.poll):m.sticker?`<div class="tg-sticker-message"><img src="${m.sticker.url}" alt="${esc(m.sticker.title||"")}"><span>${esc(m.sticker.emoji||"")}</span></div>`:(m.body?`<div class="tg-message-text mention-render">${richText(m.body)}</div>`:"")}${attachmentsHtml(m.attachments)}`;
    const actions=(m.is_deleted||m._pending||m._failed)?"":`<div class="tg-message-actions">
      <button type="button" data-action="reply" title="Ответить">↩</button>
      <button type="button" data-action="react" title="Реакция">☺</button>
      <button type="button" data-action="forward" title="Переслать">↪</button>
      ${mine?'<button type="button" data-action="edit" title="Изменить">✎</button>':""}
      <button type="button" data-action="delete" title="Удалить">🗑</button>
      <button type="button" data-action="pin" title="Закрепить">📌</button>
      ${mine?'<button type="button" data-action="receipts" title="Кто прочитал">✓✓</button>':""}
    </div>`;
    const receipts=m.receipts||{};const readMark=Number(receipts.total||0)>0&&Number(receipts.read||0)>=Number(receipts.total||0)?"✓✓":"✓";
    el.innerHTML=`${mine?"":avatarHtml(sender)}<div class="tg-bubble">${forwarded}${reply}
      ${mine?"":`<div class="tg-sender-name">${esc(sender.name)}</div>`}${body}
      <div class="tg-reactions">${reactionsHtml(m.reactions,m.id)}</div>
      <div class="tg-message-time">${m.edited?"<span>изменено</span>":""}<time>${formatClock(m)}</time>${mine?(m._failed?`<button class="tg-send-state failed" type="button" data-retry-client="${esc(clientId)}" title="Не отправлено. Нажмите, чтобы повторить">!</button>`:m._pending?`<span class="tg-send-state pending" title="Отправляется">↻</span>`:`<span class="tg-read-mark ${readMark==="✓✓"?"read":""}" data-read-for="${m.id}">${readMark}</span>`):""}</div>
      ${actions}</div>`;
    return el;
  }

  function upsertMessage(m,{forceScroll=false}={}){
    const optimistic=Number(m.sender?.id)===Number(cfg.userId)?clientNode(m.client_message_id):null;
    const old=optimistic||node(m.id),fresh=renderMessage(m);
    const wasNearBottom=isNearBottom();
    if(old)old.replaceWith(fresh);
    else{
      stream.insertBefore(fresh,typingIndicator);
      if(Number(m.sender?.id)!==Number(cfg.userId)&&!wasNearBottom){
        newWhileAway+=1;
      }
    }
    if(forceScroll||wasNearBottom||Number(m.sender?.id)===Number(cfg.userId))scrollBottom();
    hydrateInteractiveMedia(fresh);
    updateScrollButton();
  }

  const mediaTime=value=>{const n=Math.max(0,Number(value)||0),m=Math.floor(n/60),s=Math.floor(n%60);return `${m}:${String(s).padStart(2,"0")}`};
  function hydrateInteractiveMedia(root=document){
    root.querySelectorAll?.(".tg-voice-player:not([data-ready])").forEach(player=>{
      player.dataset.ready="1";
      const audio=player.querySelector("audio"),button=player.querySelector(".tg-voice-play"),wave=player.querySelector("[data-waveform]");
      if(!audio||!button||!wave)return;
      const seed=[...String(audio.currentSrc||audio.src||"")].reduce((sum,ch)=>sum+ch.charCodeAt(0),0);
      for(let i=0;i<46;i++){const bar=document.createElement("i");const h=20+((i*17+seed)%74);bar.style.setProperty("--h",`${h}%`);bar.style.setProperty("--delay",`${(i%9)*-0.07}s`);wave.appendChild(bar)}
      const current=player.querySelector("[data-current]"),duration=player.querySelector("[data-duration]"),speed=player.querySelector(".tg-voice-speed"),playIcon=button.querySelector("span")||button;
      const paint=()=>{const p=audio.duration?audio.currentTime/audio.duration:0;const bars=[...wave.children];bars.forEach((bar,index)=>bar.classList.toggle("played",index/Math.max(1,bars.length-1)<=p));if(current)current.textContent=mediaTime(audio.currentTime);if(duration)duration.textContent=mediaTime(audio.duration)};
      audio.addEventListener("loadedmetadata",paint);audio.addEventListener("durationchange",paint);audio.addEventListener("timeupdate",paint);
      audio.addEventListener("play",()=>{document.querySelectorAll(".tg-voice-player audio").forEach(other=>{if(other!==audio)other.pause()});playIcon.textContent="Ⅱ";player.classList.add("is-playing")});
      audio.addEventListener("pause",()=>{playIcon.textContent="▶";player.classList.remove("is-playing")});audio.addEventListener("ended",()=>{playIcon.textContent="▶";player.classList.remove("is-playing");paint()});
      button.addEventListener("click",()=>{if(audio.paused)audio.play().catch(()=>RMesUI.toast("Не удалось воспроизвести голосовое","error"));else audio.pause()});
      speed?.addEventListener("click",()=>{const rates=[1,1.5,2],idx=rates.findIndex(x=>Math.abs(x-audio.playbackRate)<.05),next=rates[(idx+1)%rates.length];audio.playbackRate=next;speed.textContent=`${next}×`;speed.classList.add("pop");setTimeout(()=>speed.classList.remove("pop"),180)});
      wave.addEventListener("click",event=>{if(!audio.duration)return;const rect=wave.getBoundingClientRect();audio.currentTime=Math.max(0,Math.min(audio.duration,((event.clientX-rect.left)/rect.width)*audio.duration));paint()});
      paint();
    });
  }

  const photoLightbox=$("#photoLightbox"),photoLightboxImage=$("#photoLightboxImage"),photoLightboxDownload=$("#photoLightboxDownload");
  function closePhotoLightbox(){photoLightbox?.classList.add("hidden");if(photoLightboxImage)photoLightboxImage.removeAttribute("src")}
  document.addEventListener("click",event=>{
    const trigger=event.target.closest?.("[data-lightbox]");if(!trigger)return;
    const src=trigger.dataset.lightbox;if(!src)return;event.preventDefault();
    if(photoLightboxImage)photoLightboxImage.src=src;if(photoLightboxDownload)photoLightboxDownload.href=trigger.dataset.download||src;photoLightbox?.classList.remove("hidden");
  });
  $("#photoLightboxClose")?.addEventListener("click",closePhotoLightbox);
  photoLightbox?.addEventListener("click",event=>{if(event.target===photoLightbox)closePhotoLightbox()});
  hydrateInteractiveMedia(document);

  let attachmentPollBusy=false;
  async function refreshPendingAttachments(){
    if(attachmentPollBusy||!cfg.attachmentStatusTemplate)return;
    const ids=[...new Set($$("[data-pending-attachment]").map(x=>x.dataset.pendingAttachment).filter(Boolean))];
    if(!ids.length)return;attachmentPollBusy=true;
    try{
      for(const id of ids.slice(0,12)){
        try{
          const r=await fetch(url(cfg.attachmentStatusTemplate,id),{headers:{"X-Requested-With":"XMLHttpRequest"},cache:"no-store"});if(!r.ok)continue;const j=await r.json();
          if(j.message&&j.scan_status!=="pending"){
            for(const a of (j.message.attachments||[])){
              const local=uploadPreviewByAttachment.get(String(a.id));
              if(local&&a.scan_status!=="safe"&&a.scan_status!=="infected")a.local_url=local;
              if(local&&(a.scan_status==="safe"||a.scan_status==="infected")){try{URL.revokeObjectURL(local)}catch(_){}uploadPreviewByAttachment.delete(String(a.id))}
            }
            upsertMessage(j.message);
          }
        }catch(_){}
      }
    }finally{attachmentPollBusy=false}
  }
  setInterval(()=>{if(!document.hidden)refreshPendingAttachments()},1600);
  function optimisticMessage(body,clientId){
    return {
      id:`pending-${clientId}`,client_message_id:clientId,body,created_at:new Date(serverTimestamp()).toISOString(),time_hm:formatClock(),
      sender:{id:cfg.userId,name:cfg.userName,avatar:cfg.userAvatar,initials:(cfg.userName||"?").slice(0,2).toUpperCase()},
      reactions:{},attachments:[],receipts:{total:0,delivered:0,read:0},_pending:true
    };
  }
  function markPendingFailed(clientId,message="Не удалось отправить") {
    const row=clientNode(clientId);if(!row)return;
    row.classList.remove("sending");row.classList.add("send-failed");
    const state=row.querySelector(".tg-send-state");
    if(state){state.outerHTML=`<button class="tg-send-state failed" type="button" data-retry-client="${esc(clientId)}" title="${esc(message)}">!</button>`;}
  }

  async function loadOlder(){
    if(!stream||historyLoading||!historyHasMore)return;
    const first=stream.querySelector(".tg-message");
    if(!first)return;
    historyLoading=true;
    stream.classList.add("loading-history");
    const before=first.dataset.messageId;
    const oldHeight=stream.scrollHeight;
    const oldTop=stream.scrollTop;
    try{
      const r=await fetch(`${cfg.historyUrl}?before=${encodeURIComponent(before)}&limit=60`,{headers:{"X-Requested-With":"XMLHttpRequest"}});
      if(!r.ok)throw new Error("Не удалось загрузить историю");
      const j=await r.json();
      historyHasMore=Boolean(j.has_more);
      if(j.results?.length){
        const frag=document.createDocumentFragment();
        j.results.forEach(m=>{if(!node(m.id))frag.appendChild(renderMessage(m))});
        stream.insertBefore(frag,first);
        const newHeight=stream.scrollHeight;
        stream.scrollTop=oldTop+(newHeight-oldHeight);
      }else historyHasMore=false;
      if(!historyHasMore){
        const label=stream.querySelector(".tg-history-label");
        if(label)label.textContent="Начало переписки";
      }
    }catch(err){
      RMesUI.toast(err.message,"error");
    }finally{
      historyLoading=false;
      stream.classList.remove("loading-history");
    }
  }

  stream?.addEventListener("scroll",()=>{
    updateScrollButton();
    if(stream.scrollTop<130)loadOlder();
  },{passive:true});

  function pingSound(){
    if(!cfg.sound)return;
    try{
      const ctx=new (window.AudioContext||window.webkitAudioContext)(),o=ctx.createOscillator(),g=ctx.createGain();
      o.frequency.value=720;g.gain.value=.025;o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.06);
    }catch(_){}
  }

  const scheme=location.protocol==="https:"?"wss":"ws";

  // Presence is managed once per application window by /ws/app/ (v13.2).

  window.addEventListener("rmes:global-message",e=>{
    const d=e.detail||{};
    if(String(d.conversation_id)!==String(cfg.conversationId))return;
    if(d.id)upsertMessage(d);
    if(Number(d.sender?.id)!==Number(cfg.userId))markReadSoon();
  });
  window.addEventListener("rmes:global-message-updated",e=>{
    const d=e.detail||{};if(String(d.conversation_id)!==String(cfg.conversationId))return;if(d.id)upsertMessage(d);
  });
  function applyReadReceipt(d){
    if(d.conversation_id&&String(d.conversation_id)!==String(cfg.conversationId))return;
    if(Number(d.user_id)===Number(cfg.userId))return;
    $$(".tg-read-mark").forEach(x=>{if(Number(x.dataset.readFor)<=Number(d.message_id)){x.textContent="✓✓";x.classList.add("read")}});
  }
  window.addEventListener("rmes:receipt-read",e=>applyReadReceipt(e.detail||{}));

  function handleWsMessage(e){
    const d=JSON.parse(e.data);
    if(d.type==="message"){
      if(Number(d.sender?.id)===Number(cfg.userId))ackOffline(d.client_message_id);
      upsertMessage(d);
      if(Number(d.sender?.id)!==Number(cfg.userId)){
        const categoryAllowed=cfg.conversationKind==="direct"?cfg.notifyDirectChats:cfg.conversationKind==="group"?cfg.notifyGroups:cfg.conversationKind==="channel"?cfg.notifyChannels:false;
        const activeHere=!document.hidden&&document.hasFocus();
        const shouldAlert=cfg.notify&&categoryAllowed&&!(cfg.suppressActiveChatNotifications&&activeHere);
        if(shouldAlert&&!window.RMesDesktop?.showNotification){
          pingSound();
          if("Notification" in window&&Notification.permission==="granted"){
            const title=cfg.showSenderName?(d.sender?.name||"R-Mes"):"R-Mes";
            const body=cfg.showMessagePreview?(d.body||"Новое сообщение"):"Новое сообщение";
            const n=new Notification(title,{body,icon:d.sender?.avatar||undefined,tag:`rmes-chat-${d.id||Date.now()}`});
            n.onclick=()=>{window.focus();n.close()};
          }
        }
      }
      markReadSoon();
    }else if(d.type==="message_updated"||d.type==="reaction"||d.type==="poll_updated"){
      upsertMessage(d);
    }else if(d.type==="message_deleted"){
      const affected=(d.hidden_for_user_ids||[]).map(Number);
      if(affected.length&&!affected.includes(Number(cfg.userId)))return;
      const n=node(d.id);
      if(n){
        n.querySelector(".tg-message-text")?.replaceWith(Object.assign(document.createElement("div"),{className:"tg-deleted-message",textContent:"Сообщение удалено"}));
        n.querySelectorAll(".tg-photo,.tg-file,.tg-audio,.tg-video,.tg-message-actions,.tg-reactions").forEach(x=>x.remove());
      }
    }else if(d.type==="history_cleared"){
      const affected=(d.affected_user_ids||[]).map(Number);if(affected.includes(Number(cfg.userId))){stream.querySelectorAll(".tg-message").forEach(row=>row.remove());const label=stream.querySelector(".tg-history-label");if(label)label.textContent="История очищена";historyHasMore=false;updateScrollButton()}
    }else if(d.type==="conversation_deleted"){
      const affected=(d.affected_user_ids||[]).map(Number);if(affected.includes(Number(cfg.userId)))exitChat();
    }else if(d.type==="typing"&&Number(d.user_id)!==Number(cfg.userId)){
      typingIndicator.classList.toggle("hidden",!d.typing);
      typingIndicator.querySelector("em").textContent=d.typing?`${d.name} печатает…`:"";
      if(d.typing&&isNearBottom())scrollBottom();
    }else if(d.type==="read"&&Number(d.user_id)!==Number(cfg.userId)){
      applyReadReceipt(d);
    }else if(d.type==="presence"&&Number(d.user_id)!==Number(cfg.userId)){
      window.RMesPresence?.apply?.(d);
    }else if(["call_offer","call_answer","call_ice","call_end","call_reject"].includes(d.type)){
      handleCallSignal(d);
    }else if(d.type==="error"){
      if(d.client_message_id)markPendingFailed(d.client_message_id,d.message||"Не удалось отправить");
      if(d.message)RMesUI.toast(d.message,"error");
      console.warn("R-Mes realtime:",d.message||"event error");
    }
  }

  function latestMessageId(){
    let max=0;$$('.tg-message[data-message-id]').forEach(x=>{const n=Number(x.dataset.messageId||0);if(n>max)max=n});return max;
  }
  let recoveryBusy=false;
  async function recoverRecentMessages(){
    if(recoveryBusy||!cfg.historyUrl)return;recoveryBusy=true;
    try{const after=latestMessageId();const r=await fetch(`${cfg.historyUrl}?after=${encodeURIComponent(after)}&limit=80`,{headers:{"X-Requested-With":"XMLHttpRequest"},cache:"no-store"});if(!r.ok)return;const j=await r.json();for(const m of (j.results||[]))upsertMessage(m);if((j.results||[]).some(m=>Number(m.sender?.id)!==Number(cfg.userId)))markReadSoon()}catch(_){}finally{recoveryBusy=false}
  }
  setInterval(()=>{if(!ws||ws.readyState!==WebSocket.OPEN)recoverRecentMessages()},3500);
  function connectWebSocket(){
    clearTimeout(reconnectTimer);
    if(exiting)return;
    try{
      ws=new WebSocket(`${scheme}://${location.host}/ws/chat/${cfg.conversationId}/`);
    }catch(_){
      scheduleReconnect();return;
    }
    ws.onopen=()=>{
      reconnectDelay=900;
      flushOfflineQueue();
      markReadSoon();
    };
    ws.onmessage=handleWsMessage;
    ws.onerror=()=>{};
    ws.onclose=()=>{
      if(exiting)return;
      scheduleReconnect();
    };
  }

  function scheduleReconnect(){
    if(exiting)return;
    clearTimeout(reconnectTimer);
    reconnectTimer=setTimeout(connectWebSocket,reconnectDelay);
    reconnectDelay=Math.min(Math.round(reconnectDelay*1.7),10000);
  }

  connectWebSocket();

  const appShell=document.querySelector(".tg-app");
  const infoToggle=$("#toggleInfoPanel");
  const infoPanel=document.querySelector(".tg-info-panel");
  const infoStateKey=`rmes:info:${cfg.userId}`;
  function setInfoPanel(open){
    if(!appShell||!infoPanel)return;
    appShell.classList.toggle("info-open",open);
    appShell.classList.toggle("info-collapsed",!open);
    infoToggle?.classList.toggle("active",open);
    localStorage.setItem(infoStateKey,open?"open":"closed");
  }
  if(infoPanel){
    const preferred=localStorage.getItem(infoStateKey);
    setInfoPanel(preferred==="open" && window.innerWidth>1220);
    infoToggle?.addEventListener("click",()=>setInfoPanel(!appShell.classList.contains("info-open")));
    window.addEventListener("resize",()=>{ if(window.innerWidth<=1220)setInfoPanel(false); });
  }

  function offlineRows(){try{return JSON.parse(localStorage.getItem(offlineKey)||"[]")}catch(_){return []}}
  function saveOfflineRows(rows){localStorage.setItem(offlineKey,JSON.stringify(rows.slice(-200)))}
  function enqueueOffline(payload){const rows=offlineRows();rows.push(payload);saveOfflineRows(rows)}
  function flushOfflineQueue(){
    if(!ws||ws.readyState!==WebSocket.OPEN)return;
    const rows=offlineRows();if(!rows.length)return;
    rows.forEach(x=>ws.send(JSON.stringify(x)));
  }
  function ackOffline(clientId){if(!clientId)return;saveOfflineRows(offlineRows().filter(x=>x.client_id!==clientId))}
  function updateSidebarPreview(body){
    const card=document.querySelector(`.tg-chat-item[data-conversation-id="${CSS.escape(String(cfg.conversationId))}"]`);
    if(!card)return;
    const preview=card.querySelector(".tg-chat-preview"),time=card.querySelector(".tg-chat-topline time");
    if(preview){
      const clipped=String(body||"").replace(/\s+/g," ").trim();
      preview.innerHTML=`<span class="you-prefix">Вы:</span> ${esc(clipped.length>54?clipped.slice(0,53)+"…":clipped)}`;
    }
    if(time)time.textContent=formatClock();
    const list=card.parentElement;if(list&&list.firstElementChild!==card)list.prepend(card);
  }

  function send(){
    const body=(input?.value||"").trim();if(!body)return;
    const clientId=makeClientId();
    const payload={type:"message",body,reply_to:replyTo,client_id:clientId};
    // Telegram-style optimistic UI: the message appears immediately with a rotating send mark.
    upsertMessage(optimisticMessage(body,clientId),{forceScroll:true});
    updateSidebarPreview(body);
    enqueueOffline(payload);
    if(ws&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(payload));
    localStorage.removeItem(draftKey);input.value="";autoGrow();clearReply();sendTyping(false);
  }
  $("#sendButton")?.addEventListener("click",send);
  stream?.addEventListener("click",async e=>{
    const uploadRetry=e.target.closest?.("[data-retry-upload-client]");
    if(uploadRetry){const clientId=uploadRetry.dataset.retryUploadClient;const item=uploadFiles.get(clientId);if(item){const row=clientNode(clientId);row?.classList.remove("send-failed");row?.classList.add("sending");const state=row?.querySelector(".tg-send-state");if(state)state.outerHTML='<span class="tg-send-state pending" title="Отправляется">↻</span>';uploadFile(item.file,item.voice,item.meta)}return;}
    const attachmentRetry=e.target.closest?.("[data-attachment-retry]");
    if(attachmentRetry){
      const id=attachmentRetry.dataset.attachmentRetry;
      try{await RMesUI.post(url(cfg.attachmentRetryTemplate,id));const box=attachmentRetry.closest(".tg-file-security");if(box){box.dataset.pendingAttachment=id;box.removeAttribute("data-attachment-error");box.innerHTML="<b>Проверяем файл…</b><span>Антивирусная проверка выполняется автоматически.</span>"}setTimeout(refreshPendingAttachments,250)}catch(err){RMesUI.toast(err.message,"error")}return;
    }
    const retry=e.target.closest?.("[data-retry-client]");if(!retry)return;
    const clientId=retry.dataset.retryClient,row=clientNode(clientId);
    const payload=offlineRows().find(x=>x.client_id===clientId);if(!payload)return;
    row?.classList.remove("send-failed");row?.classList.add("sending");
    if(retry)retry.outerHTML='<span class="tg-send-state pending" title="Отправляется">↻</span>';
    if(ws&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(payload));
    else scheduleReconnect();
  });
  input?.addEventListener("keydown",e=>{
    if(e.key==="Enter"&&cfg.enterToSend&&!e.shiftKey){e.preventDefault();send()}
    if(e.key==="Enter"&&!cfg.enterToSend&&e.ctrlKey){e.preventDefault();send()}
  });
  input?.addEventListener("input",()=>{
    autoGrow();
    const value=input.value;
    if(value)localStorage.setItem(draftKey,value);else localStorage.removeItem(draftKey);
    updateMentionSuggest(value);
    sendTyping(true);clearTimeout(typingTimer);typingTimer=setTimeout(()=>sendTyping(false),950);
  });
  const mentionBox=$("#mentionSuggest");
  const updateMentionSuggest=RMesUI.debounce(async value=>{
    const match=value.match(/(?:^|\s)@([a-z0-9_]{1,32})$/i);
    if(!match||!mentionBox){mentionBox?.classList.add("hidden");return}
    const q=match[1];
    try{
      const r=await fetch(`${window.R_MES_GLOBAL.searchUrl}?q=${encodeURIComponent(q)}`);const j=await r.json();
      const people=(j.people||[]).filter(x=>!x.blocked).slice(0,7);
      mentionBox.innerHTML=`<button class="mention-choice" data-mention="all"><div><b>@all</b><span>Упомянуть всех участников</span></div></button>`+people.map(x=>`<button class="mention-choice" data-mention="${esc(x.handle||"")}">${x.avatar?`<div class="tg-avatar tg-avatar-sm"><img src="${x.avatar}" alt=""></div>`:""}<div><b>${esc(x.name)}</b><span>@${esc(x.handle||"")}</span></div></button>`).join("");
      mentionBox.classList.remove("hidden");
    }catch(_){mentionBox.classList.add("hidden")}
  },120);
  mentionBox?.addEventListener("click",e=>{const b=e.target.closest("[data-mention]");if(!b)return;input.value=input.value.replace(/@([a-z0-9_]*)$/i,`@${b.dataset.mention} `);mentionBox.classList.add("hidden");input.focus();autoGrow()});

  function autoGrow(){if(!input)return;input.style.height="auto";input.style.height=Math.min(input.scrollHeight,170)+"px"}
  function sendTyping(on){if(ws&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({type:"typing",typing:on}))}

  function markReadSoon(){
    setTimeout(()=>{
      const rows=$$(".tg-message"),last=rows.at(-1);
      if(last&&ws&&ws.readyState===WebSocket.OPEN&&last.dataset.messageId)ws.send(JSON.stringify({type:"read",message_id:last.dataset.messageId}));
    },260);
  }
  window.addEventListener("focus",markReadSoon);

  function clearReply(){replyTo=null;$("#replyComposer")?.classList.add("hidden")}
  $("#cancelReply")?.addEventListener("click",clearReply);

  // Telegram-style Unicode emoji picker with categories and recent emoji.
  const emojiPanel=$("#emojiPanel"),emojiTabs=$("#emojiTabs"),emojiGrid=$("#emojiGrid"),emojiTitle=$("#emojiCategoryTitle");
  const EMOJI_CATEGORIES=[
    {id:"recent",icon:"🕘",title:"Недавние",emojis:[]},
    {id:"smileys",icon:"😀",title:"Смайлы и люди",emojis:`😀 😃 😄 😁 😆 😅 😂 🤣 😊 😇 🙂 🙃 😉 😌 😍 🥰 😘 😗 😙 😚 😋 😛 😝 😜 🤪 🤨 🧐 🤓 😎 🥸 🤩 🥳 😏 😒 😞 😔 😟 😕 🙁 ☹️ 😣 😖 😫 😩 🥺 😢 😭 😤 😠 😡 🤬 🤯 😳 🥵 🥶 😱 😨 😰 😥 😓 🤗 🤔 🫣 🤭 🫢 🫡 🤫 🫠 🤥 😶 😐 😑 😬 🫨 🙄 😯 😦 😧 😮 😲 🥱 😴 🤤 😪 😵 😵‍💫 🤐 🥴 🤢 🤮 🤧 😷 🤒 🤕 🤑 🤠 😈 👿 👹 👺 🤡 💩 👻 💀 ☠️ 👽 👾 🤖 🎃 😺 😸 😹 😻 😼 😽 🙀 😿 😾 🫶 🤲 👐 🙌 👏 🤝 👍 👎 👊 ✊ 🤛 🤜 🤞 ✌️ 🫰 🤟 🤘 👌 🤌 🤏 👈 👉 👆 👇 ☝️ ✋ 🤚 🖐️ 🖖 👋 🤙 💪 🦾 🖕 ✍️ 🙏 🫵 🦶 🦵 👂 🦻 👃 🧠 🫀 🫁 🦷 👀 👁️ 👅 👄 🫦 👶 🧒 👦 👧 🧑 👱 👨 🧔 👩 🧓 👴 👵 🙍 🙎 🙅 🙆 💁 🙋 🧏 🙇 🤦 🤷 👮 👷 💂 🕵️ 👩‍⚕️ 👨‍⚕️ 👩‍💻 👨‍💻 👩‍🏫 👨‍🏫 👩‍🍳 👨‍🍳 👩‍🔧 👨‍🔧 👩‍🚀 👨‍🚀 🧑‍🚒 🥷 👸 🤴 🦸 🦹 🧙 🧚 🧛 🧜 🧝 🧞 🧟 💆 💇 🚶 🧍 🧎 🏃 💃 🕺 🕴️ 👯 🧖 🧗 🤺 🏇 ⛷️ 🏂 🏌️ 🏄 🚣 🏊 ⛹️ 🏋️ 🚴 🚵 🤸 🤼 🤽 🤾 🤹 🧘 🛀 🛌`.split(/\s+/)},
    {id:"animals",icon:"🐻",title:"Животные и природа",emojis:`🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐻‍❄️ 🐨 🐯 🦁 🐮 🐷 🐽 🐸 🐵 🙈 🙉 🙊 🐒 🐔 🐧 🐦 🐤 🐣 🐥 🦆 🦅 🦉 🦇 🐺 🐗 🐴 🦄 🫎 🐝 🪱 🐛 🦋 🐌 🪲 🐞 🦗 🪳 🕷️ 🦂 🐢 🐍 🦎 🦖 🦕 🐙 🦑 🦐 🦞 🦀 🐡 🐠 🐟 🐬 🐳 🐋 🦈 🦭 🐊 🐅 🐆 🦓 🫏 🦍 🦧 🐘 🦛 🦏 🐪 🐫 🦒 🦘 🦬 🐃 🐂 🐄 🐎 🐖 🐏 🐑 🦙 🐐 🦌 🐕 🐩 🦮 🐕‍🦺 🐈 🐈‍⬛ 🪽 🪶 🐓 🦃 🦤 🦚 🦜 🦢 🪿 🦩 🕊️ 🐇 🦝 🦨 🦡 🦫 🦦 🦥 🐁 🐀 🐿️ 🦔 🐾 🐉 🐲 🌵 🎄 🌲 🌳 🌴 🪵 🌱 🌿 ☘️ 🍀 🎍 🪴 🎋 🍃 🍂 🍁 🪺 🪹 🍄 🐚 🪸 🪨 🌾 💐 🌷 🌹 🥀 🪻 🌺 🌸 🌼 🌻 🌞 🌝 🌚 🌕 🌖 🌗 🌘 🌑 🌒 🌓 🌔 🌙 🌎 🌍 🌏 🪐 💫 ⭐ 🌟 ✨ ⚡ ☄️ 💥 🔥 🌪️ 🌈 ☀️ 🌤️ ⛅ 🌥️ ☁️ 🌦️ 🌧️ ⛈️ 🌩️ 🌨️ ❄️ ☃️ ⛄ 🌬️ 💨 💧 💦 🫧 ☔ ☂️ 🌊`.split(/\s+/)},
    {id:"food",icon:"🍔",title:"Еда и напитки",emojis:`🍏 🍎 🍐 🍊 🍋 🍋‍🟩 🍌 🍉 🍇 🍓 🫐 🍈 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🍆 🥑 🫛 🥦 🥬 🥒 🌶️ 🫑 🌽 🥕 🫒 🧄 🧅 🥔 🍠 🫚 🥐 🥯 🍞 🥖 🥨 🧀 🥚 🍳 🧈 🥞 🧇 🥓 🥩 🍗 🍖 🌭 🍔 🍟 🍕 🫓 🥪 🥙 🧆 🌮 🌯 🫔 🥗 🥘 🫕 🥫 🍝 🍜 🍲 🍛 🍣 🍱 🥟 🦪 🍤 🍙 🍚 🍘 🍥 🥠 🥮 🍢 🍡 🍧 🍨 🍦 🥧 🧁 🍰 🎂 🍮 🍭 🍬 🍫 🍿 🍩 🍪 🌰 🥜 🫘 🍯 🥛 🍼 🫖 ☕ 🍵 🧃 🥤 🧋 🫙 🍶 🍺 🍻 🥂 🍷 🥃 🍸 🍹 🧉 🍾 🧊 🥄 🍴 🍽️ 🥣 🥡 🥢 🧂`.split(/\s+/)},
    {id:"activity",icon:"⚽",title:"Активность",emojis:`⚽ 🏀 🏈 ⚾ 🥎 🎾 🏐 🏉 🥏 🎱 🪀 🏓 🏸 🏒 🏑 🥍 🏏 🪃 🥅 ⛳ 🪁 🛝 🏹 🎣 🤿 🥊 🥋 🎽 🛹 🛼 🛷 ⛸️ 🥌 🎿 ⛷️ 🏂 🪂 🏋️ 🤼 🤸 ⛹️ 🤺 🤾 🏌️ 🏇 🧘 🏄 🏊 🤽 🚣 🧗 🚴 🚵 🎯 🎳 🎮 🎰 🎲 🧩 ♟️ 🎭 🎨 🧵 🪡 🧶 🎼 🎤 🎧 🎷 🪗 🎸 🎹 🎺 🎻 🥁 🪘 🎬 🎪 🎟️ 🎫 🏆 🥇 🥈 🥉 🏅 🎖️ 🏵️ 🎗️`.split(/\s+/)},
    {id:"travel",icon:"🚗",title:"Путешествия и места",emojis:`🚗 🚕 🚙 🚌 🚎 🏎️ 🚓 🚑 🚒 🚐 🛻 🚚 🚛 🚜 🏍️ 🛵 🚲 🛴 🚨 🚔 🚍 🚘 🚖 🛞 🚡 🚠 🚟 🚃 🚋 🚞 🚝 🚄 🚅 🚈 🚂 🚆 🚇 🚊 🚉 ✈️ 🛫 🛬 🛩️ 💺 🛰️ 🚀 🛸 🚁 🛶 ⛵ 🚤 🛥️ 🛳️ ⛴️ 🚢 ⚓ 🛟 ⛽ 🚧 🚦 🚥 🗺️ 🗿 🗽 🗼 🏰 🏯 🏟️ 🎡 🎢 🎠 ⛲ ⛱️ 🏖️ 🏝️ 🏜️ 🌋 ⛰️ 🏔️ 🗻 🏕️ ⛺ 🛖 🏠 🏡 🏢 🏥 🏦 🏨 🏪 🏫 🏬 🏭 🏛️ ⛪ 🕌 🛕 🕍 🕋 ⛩️ 🛤️ 🛣️ 🌅 🌄 🌠 🎇 🎆 🌇 🌆 🏙️ 🌃 🌌 🌉 🌁`.split(/\s+/)},
    {id:"objects",icon:"💡",title:"Объекты",emojis:`⌚ 📱 📲 💻 ⌨️ 🖥️ 🖨️ 🖱️ 🖲️ 🕹️ 🗜️ 💽 💾 💿 📀 📼 📷 📸 📹 🎥 📽️ 🎞️ 📞 ☎️ 📟 📠 📺 📻 🎙️ 🎚️ 🎛️ 🧭 ⏱️ ⏲️ ⏰ 🕰️ ⌛ ⏳ 📡 🔋 🪫 🔌 💡 🔦 🕯️ 🪔 🧯 🛢️ 💸 💵 💴 💶 💷 🪙 💰 💳 🧾 💎 ⚖️ 🪜 🧰 🪛 🔧 🔨 ⚒️ 🛠️ ⛏️ 🪚 🔩 ⚙️ 🪤 🧱 ⛓️ 🧲 🔫 💣 🧨 🪓 🔪 🗡️ ⚔️ 🛡️ 🚬 ⚰️ 🪦 ⚱️ 🏺 🔮 📿 🧿 🪬 💈 ⚗️ 🔭 🔬 🕳️ 🩹 🩺 💊 💉 🩸 🧬 🦠 🧫 🧪 🌡️ 🧹 🪠 🧺 🧻 🚽 🚿 🛁 🧼 🪥 🪒 🧽 🪣 🧴 🛎️ 🔑 🗝️ 🚪 🪑 🛋️ 🛏️ 🪞 🪟 🛍️ 🛒 🎁 🎈 🎏 🎀 🪄 🪅 🎊 🎉 🪩 ✉️ 📩 📨 📧 💌 📥 📤 📦 🏷️ 📪 📫 📬 📭 📮 📯 📜 📃 📄 📑 🧾 📊 📈 📉 🗒️ 🗓️ 📆 📅 🗑️ 📇 🗃️ 🗳️ 🗄️ 📋 📁 📂 🗂️ 🗞️ 📰 📓 📔 📒 📕 📗 📘 📙 📚 📖 🔖 🧷 🔗 📎 🖇️ 📐 📏 🧮 📌 📍 ✂️ 🖊️ 🖋️ ✒️ 🖌️ 🖍️ 📝 ✏️ 🔍 🔎 🔏 🔐 🔒 🔓`.split(/\s+/)},
    {id:"symbols",icon:"❤️",title:"Символы",emojis:`❤️ 🧡 💛 💚 💙 🩵 💜 🖤 🩶 🤍 🤎 💔 ❤️‍🔥 ❤️‍🩹 ❣️ 💕 💞 💓 💗 💖 💘 💝 💟 ☮️ ✝️ ☪️ 🕉️ ☸️ ✡️ 🔯 🕎 ☯️ ☦️ 🛐 ⛎ ♈ ♉ ♊ ♋ ♌ ♍ ♎ ♏ ♐ ♑ ♒ ♓ 🆔 ⚛️ 🉑 ☢️ ☣️ 📴 📳 🈶 🈚 🈸 🈺 🈷️ ✴️ 🆚 💮 🉐 ㊙️ ㊗️ 🈴 🈵 🈹 🈲 🅰️ 🅱️ 🆎 🆑 🅾️ 🆘 ❌ ⭕ 🛑 ⛔ 📛 🚫 💯 💢 ♨️ 🚷 🚯 🚳 🚱 🔞 📵 🚭 ❗ ❕ ❓ ❔ ‼️ ⁉️ 🔅 🔆 〽️ ⚠️ 🚸 🔱 ⚜️ 🔰 ♻️ ✅ 🈯 💹 ❇️ ✳️ ❎ 🌐 💠 Ⓜ️ 🌀 💤 🏧 🚾 ♿ 🅿️ 🛗 🛂 🛃 🛄 🛅 🚹 🚺 🚼 ⚧️ 🚻 🚮 🎦 📶 🈁 🔣 ℹ️ 🔤 🔡 🔠 🆖 🆗 🆙 🆒 🆕 🆓 0️⃣ 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣ 8️⃣ 9️⃣ 🔟 🔢 #️⃣ *️⃣ ⏏️ ▶️ ⏸️ ⏯️ ⏹️ ⏺️ ⏭️ ⏮️ ⏩ ⏪ ⏫ ⏬ ◀️ 🔼 🔽 ➡️ ⬅️ ⬆️ ⬇️ ↗️ ↘️ ↙️ ↖️ ↕️ ↔️ ↪️ ↩️ ⤴️ ⤵️ 🔀 🔁 🔂 🔄 🔃 🎵 🎶 ➕ ➖ ➗ ✖️ 🟰 ♾️ 💲 ™️ ©️ ®️ 👁️‍🗨️ 🔚 🔙 🔛 🔝 🔜 ✔️ ☑️ 🔘 🔴 🟠 🟡 🟢 🔵 🟣 ⚫ ⚪ 🟤 🔺 🔻 🔸 🔹 🔶 🔷 🔳 🔲 ▪️ ▫️ ◾ ◽ ◼️ ◻️ 🟥 🟧 🟨 🟩 🟦 🟪 ⬛ ⬜ 🟫`.split(/\s+/)},
    {id:"flags",icon:"🏳️",title:"Флаги",emojis:`🏁 🚩 🎌 🏴 🏳️ 🏳️‍🌈 🏳️‍⚧️ 🏴‍☠️ 🇺🇿 🇰🇿 🇰🇬 🇹🇯 🇹🇲 🇦🇿 🇹🇷 🇷🇺 🇺🇦 🇬🇪 🇦🇲 🇺🇸 🇨🇦 🇲🇽 🇧🇷 🇦🇷 🇬🇧 🇫🇷 🇩🇪 🇮🇹 🇪🇸 🇵🇹 🇳🇱 🇧🇪 🇨🇭 🇦🇹 🇵🇱 🇨🇿 🇸🇰 🇭🇺 🇷🇴 🇧🇬 🇬🇷 🇸🇪 🇳🇴 🇫🇮 🇩🇰 🇮🇸 🇮🇪 🇪🇪 🇱🇻 🇱🇹 🇲🇩 🇷🇸 🇭🇷 🇸🇮 🇧🇦 🇦🇱 🇲🇰 🇨🇾 🇲🇹 🇪🇺 🇨🇳 🇯🇵 🇰🇷 🇮🇳 🇵🇰 🇧🇩 🇮🇩 🇲🇾 🇸🇬 🇹🇭 🇻🇳 🇵🇭 🇦🇺 🇳🇿 🇸🇦 🇦🇪 🇶🇦 🇰🇼 🇮🇱 🇪🇬 🇿🇦 🇳🇬 🇲🇦 🇰🇪`.split(/\s+/)}
  ];
  const EMOJI_RECENT_KEY="rmes:recent-emojis:v1";
  const DEFAULT_RECENT=["👍","❤️","😂","🔥","👏","🙏","😍","🎉","🤝","💯","😊","🤣"];
  const emojiRecent=()=>{try{const v=JSON.parse(localStorage.getItem(EMOJI_RECENT_KEY)||"[]");return Array.isArray(v)&&v.length?v.slice(0,32):DEFAULT_RECENT}catch(_){return DEFAULT_RECENT}};
  function saveRecent(emoji){try{const next=[emoji,...emojiRecent().filter(x=>x!==emoji)].slice(0,32);localStorage.setItem(EMOJI_RECENT_KEY,JSON.stringify(next))}catch(_){}}
  let activeEmojiCategory="recent";
  function renderEmojiTabs(){if(!emojiTabs)return;emojiTabs.innerHTML=EMOJI_CATEGORIES.map(c=>`<button type="button" role="tab" data-emoji-cat="${c.id}" class="${c.id===activeEmojiCategory?"active":""}" title="${c.title}" aria-label="${c.title}">${c.icon}</button>`).join("")}
  function renderEmojiCategory(id=activeEmojiCategory){
    const cat=EMOJI_CATEGORIES.find(x=>x.id===id)||EMOJI_CATEGORIES[1];activeEmojiCategory=cat.id;
    const list=cat.id==="recent"?emojiRecent():cat.emojis;
    if(emojiTitle)emojiTitle.textContent=cat.title;
    if(emojiGrid)emojiGrid.innerHTML=(list||[]).map(e=>`<button type="button" class="tg-emoji-choice" data-emoji="${e}" aria-label="${e}">${e}</button>`).join("");
    renderEmojiTabs();
  }
  function insertEmoji(emoji){
    if(!input)return;const start=input.selectionStart??input.value.length,end=input.selectionEnd??start;
    input.value=input.value.slice(0,start)+emoji+input.value.slice(end);
    const pos=start+emoji.length;input.setSelectionRange(pos,pos);input.dispatchEvent(new Event("input",{bubbles:true}));input.focus();autoGrow();saveRecent(emoji);
    if(activeEmojiCategory==="recent")renderEmojiCategory("recent");
  }
  $("#emojiButton")?.addEventListener("click",e=>{e.stopPropagation();emojiPanel?.classList.toggle("hidden");$("#stickerPanel")?.classList.add("hidden");if(emojiPanel&&!emojiPanel.classList.contains("hidden"))renderEmojiCategory(activeEmojiCategory)});
  emojiTabs?.addEventListener("click",e=>{const b=e.target.closest("[data-emoji-cat]");if(!b)return;e.stopPropagation();renderEmojiCategory(b.dataset.emojiCat)});
  emojiGrid?.addEventListener("click",e=>{const b=e.target.closest("[data-emoji]");if(!b)return;e.stopPropagation();insertEmoji(b.dataset.emoji)});
  document.addEventListener("click",e=>{if(emojiPanel&&!emojiPanel.classList.contains("hidden")&&!emojiPanel.contains(e.target)&&!e.target.closest("#emojiButton"))emojiPanel.classList.add("hidden")});
  $("#stickerButton")?.addEventListener("click",()=>{$("#stickerPanel")?.classList.toggle("hidden");emojiPanel?.classList.add("hidden")});
  $("#stickerPanel")?.addEventListener("click",async e=>{const b=e.target.closest("[data-sticker-id]");if(!b)return;try{const j=await RMesUI.post(url(cfg.stickerTemplate,b.dataset.stickerId),{client_id:makeClientId()});if(j.message)upsertMessage(j.message,{forceScroll:true});$("#stickerPanel").classList.add("hidden")}catch(err){RMesUI.toast(err.message,"error")}});

  async function loadMedia(kind="media"){
    const browser=$("#mediaBrowser");if(!browser)return;browser.innerHTML='<div class="tg-search-empty">Загрузка…</div>';
    try{const r=await fetch(`${cfg.mediaUrl}?kind=${encodeURIComponent(kind)}`);const j=await r.json();const rows=j.results||[];
      if(kind==="media")browser.innerHTML=`<div class="media-browser-grid">${rows.map(x=>x.content_type?.startsWith("image/")?`<button type="button" data-lightbox="${esc(x.url)}" data-download="${esc(x.download_url||x.url)}"><img src="${esc(x.url)}" alt=""></button>`:`<video controls preload="metadata" src="${esc(x.url)}"></video>`).join("")}</div>`||'<div class="tg-search-empty">Нет медиа</div>';
      else browser.innerHTML=`<div class="media-browser-list">${rows.map(x=>`<a class="media-browser-item" href="${esc(x.download_url||x.url)}">${esc(x.name)} · ${esc(x.time||"")}</a>`).join("")}</div>`||'<div class="tg-search-empty">Пусто</div>';
      hydrateInteractiveMedia(browser);
    }catch(_){browser.innerHTML='<div class="tg-search-empty">Ошибка загрузки</div>'}
  }
  $("#mediaTabs")?.addEventListener("click",e=>{const b=e.target.closest("[data-media-kind]");if(!b)return;$("#mediaTabs").querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===b));loadMedia(b.dataset.mediaKind)});
  if($("#mediaBrowser"))loadMedia("media");
  $("#openPins")?.addEventListener("click",async e=>{e.stopPropagation();try{const r=await fetch(cfg.pinsUrl);const j=await r.json();$("#pinsList").innerHTML=(j.results||[]).map(x=>`<a class="tg-message-search-item" href="${x.url}"><div><b>${esc(x.sender)}</b><time>${esc(x.time)}</time></div><span>${esc(x.body)}</span></a>`).join("")||'<div class="tg-search-empty">Нет закреплённых</div>';$("#pinsModal").classList.remove("hidden")}catch(err){RMesUI.toast(err.message,"error")}});

  const searchPanel=$("#messageSearchPanel"),searchInput=$("#messageSearchInput"),searchResults=$("#messageSearchResults");
  $("#toggleMessageSearch")?.addEventListener("click",()=>{searchPanel.classList.remove("hidden");searchInput.focus()});
  $("#closeMessageSearch")?.addEventListener("click",()=>closeSearch());
  function closeSearch(){
    searchPanel?.classList.add("hidden");searchResults?.classList.add("hidden");
    if(searchInput)searchInput.value="";
    if($("#messageSearchCount"))$("#messageSearchCount").textContent="";
  }
  const runMessageSearch=RMesUI.debounce(async()=>{
    const q=searchInput.value.trim();
    if(!q){searchResults.classList.add("hidden");$("#messageSearchCount").textContent="";return}
    try{
      const r=await fetch(`${cfg.searchUrl}?q=${encodeURIComponent(q)}`);
      const j=await r.json();$("#messageSearchCount").textContent=`${j.results.length}`;
      searchResults.innerHTML=j.results.length
        ?j.results.map(x=>`<a href="${x.url}" class="tg-message-search-item"><div><b>${esc(x.sender)}</b><time>${esc(x.time)}</time></div><span>${esc(x.text)}</span></a>`).join("")
        :'<div class="tg-search-empty">Ничего не найдено</div>';
      searchResults.classList.remove("hidden");
    }catch(_){RMesUI.toast("Ошибка поиска","error")}
  },150);
  searchInput?.addEventListener("input",runMessageSearch);

  const chatMenu=$("#chatMenu");
  $("#chatMenuBtn")?.addEventListener("click",e=>{e.stopPropagation();chatMenu.classList.toggle("hidden")});
  document.addEventListener("click",e=>{
    if(chatMenu&&!chatMenu.contains(e.target)&&!e.target.closest("#chatMenuBtn"))chatMenu.classList.add("hidden");
    const pop=$("#reactionPopover");
    if(pop&&!pop.contains(e.target)&&!e.target.closest('[data-action="react"]'))pop.classList.add("hidden");
  });

  async function chatAction(action){
    try{
      if(action==="pin"){await RMesUI.post(cfg.chatPinUrl);location.reload()}
      else if(action==="archive"){await RMesUI.post(cfg.archiveUrl);exitChat()}
      else if(action==="mute"){await RMesUI.post(cfg.muteUrl);location.reload()}
      else if(action==="delete")$("#chatDeleteModal").classList.remove("hidden");
      else if(action==="clear")$("#chatClearModal").classList.remove("hidden");
    }catch(err){RMesUI.toast(err.message,"error")}
  }
  $$("[data-chat-action]").forEach(b=>b.addEventListener("click",()=>chatAction(b.dataset.chatAction)));
  $$("[data-mute-minutes]").forEach(b=>b.addEventListener("click",async()=>{try{await RMesUI.post(cfg.muteDurationUrl,{minutes:b.dataset.muteMinutes});location.reload()}catch(err){RMesUI.toast(err.message,"error")}}));

  async function userAction(button){
    const id=button.dataset.userId,action=button.dataset.userAction;
    try{
      await RMesUI.post(url(action==="block"?cfg.blockTemplate:cfg.unblockTemplate,id));
      RMesUI.toast(action==="block"?"Пользователь заблокирован":"Пользователь разблокирован","success");
      location.reload();
    }catch(err){RMesUI.toast(err.message,"error")}
  }
  $$("[data-user-action]").forEach(b=>b.addEventListener("click",()=>userAction(b)));

  document.addEventListener("click",async e=>{
    const jump=e.target.closest("[data-jump]");
    if(jump){
      const n=node(jump.dataset.jump);
      if(n){n.scrollIntoView({behavior:"smooth",block:"center"});n.classList.add("highlight");setTimeout(()=>n.classList.remove("highlight"),1000)}
      return;
    }
    const chip=e.target.closest(".tg-reaction-chip");
    if(chip){
      try{await RMesUI.post(chip.dataset.reactUrl,{emoji:chip.dataset.emoji})}catch(err){RMesUI.toast(err.message,"error")}
      return;
    }
    const btn=e.target.closest(".tg-message-actions button");if(!btn)return;
    const row=btn.closest(".tg-message"),id=row.dataset.messageId,action=btn.dataset.action;
    if(action==="reply"){
      replyTo=id;$("#replyText").textContent=(row.querySelector(".tg-message-text")?.innerText||"Сообщение").slice(0,140);
      $("#replyComposer").classList.remove("hidden");input?.focus();
    }else if(action==="edit"){
      editId=id;$("#editText").value=row.querySelector(".tg-message-text")?.innerText||"";$("#editModal").classList.remove("hidden");$("#editText").focus();
    }else if(action==="delete"){
      deleteMessageId=id;$("#messageDeleteModal").classList.remove("hidden");
    }else if(action==="react"){
      reactionId=id;const rect=btn.getBoundingClientRect(),pop=$("#reactionPopover");
      pop.style.left=Math.min(rect.left,window.innerWidth-320)+"px";pop.style.top=Math.max(8,rect.top-58)+"px";pop.classList.remove("hidden");
    }else if(action==="pin"){
      try{await RMesUI.post(url(cfg.pinTemplate,id));RMesUI.toast("Закрепление обновлено","success");location.reload()}catch(err){RMesUI.toast(err.message,"error")}
    }else if(action==="forward"){
      forwardId=id;$("#forwardModal").classList.remove("hidden");
    }else if(action==="receipts"){
      openReceipts(id);
    }
  });

  async function openReceipts(id){
    try{const r=await fetch(url(cfg.receiptsTemplate,id));const j=await r.json();if(!r.ok)throw new Error(j.detail||"Ошибка");const list=$("#receiptsList");list.innerHTML=(j.results||[]).map(x=>`<div class="receipt-row">${x.avatar?`<div class="tg-avatar tg-avatar-sm"><img src="${x.avatar}" alt=""></div>`:`<div class="tg-avatar tg-avatar-sm"><span>${esc((x.name||"?").slice(0,1))}</span></div>`}<div><b>${esc(x.name)}</b><span>${x.handle?`@${esc(x.handle)} · `:""}${x.read_at?`прочитано ${esc(x.read_at)}`:x.delivered_at?`доставлено ${esc(x.delivered_at)}`:"ожидает доставки"}</span></div><div class="receipt-state">${x.read_at?"✓✓":x.delivered_at?"✓":"○"}</div></div>`).join("")||'<div class="tg-search-empty">Нет данных.</div>';$("#receiptsModal").classList.remove("hidden")}catch(err){RMesUI.toast(err.message,"error")}
  }

  $("#reactionPopover")?.addEventListener("click",async e=>{
    if(e.target.tagName!=="BUTTON"||!reactionId)return;
    try{await RMesUI.post(url(cfg.reactTemplate,reactionId),{emoji:e.target.textContent})}catch(err){RMesUI.toast(err.message,"error")}
    $("#reactionPopover").classList.add("hidden");
  });

  $("#saveEdit")?.addEventListener("click",async()=>{
    try{await RMesUI.post(url(cfg.editTemplate,editId),{body:$("#editText").value});$("#editModal").classList.add("hidden")}
    catch(err){RMesUI.toast(err.message,"error")}
  });

  $$(".tg-forward-target").forEach(b=>b.addEventListener("click",async()=>{
    try{
      await RMesUI.post(url(cfg.forwardTemplate,forwardId),{conversation_id:b.dataset.target});
      $("#forwardModal").classList.add("hidden");RMesUI.toast("Сообщение переслано","success");
    }catch(err){RMesUI.toast(err.message,"error")}
  }));

  async function deleteMessage(scope){
    if(!deleteMessageId)return;
    try{
      await RMesUI.post(url(cfg.deleteTemplate,deleteMessageId),{scope});
      if(scope==="self")node(deleteMessageId)?.remove();
      $("#messageDeleteModal").classList.add("hidden");
      updateScrollButton();
    }catch(err){RMesUI.toast(err.message,"error")}
  }
  $("#deleteMessageSelf")?.addEventListener("click",()=>deleteMessage("self"));
  $("#deleteMessagePeer")?.addEventListener("click",()=>deleteMessage("peer"));
  $("#deleteMessageEveryone")?.addEventListener("click",()=>deleteMessage("everyone"));

  async function deleteChat(scope){
    try{
      const j=await RMesUI.post(cfg.deleteChatUrl,{scope});
      exitChat();
    }catch(err){RMesUI.toast(err.message,"error")}
  }
  $("#deleteChatSelf")?.addEventListener("click",()=>deleteChat("self"));
  $("#deleteChatPeer")?.addEventListener("click",()=>deleteChat("peer"));
  $("#deleteChatEveryone")?.addEventListener("click",()=>deleteChat("everyone"));

  async function clearChat(scope){
    try{
      const result=await RMesUI.post(cfg.clearChatUrl,{scope});
      $("#chatClearModal")?.classList.add("hidden");
      if(result.applied===false)return;
      stream.querySelectorAll(".tg-message").forEach(row=>row.remove());
      const label=stream.querySelector(".tg-history-label");if(label)label.textContent="История очищена";
      historyHasMore=false;updateSidebarPreview("");updateScrollButton();
    }catch(err){RMesUI.toast(err.message,"error")}
  }
  $("#clearChatSelf")?.addEventListener("click",()=>clearChat("self"));
  $("#clearChatPeer")?.addEventListener("click",()=>clearChat("peer"));
  $("#clearChatEveryone")?.addEventListener("click",()=>clearChat("everyone"));

  $$(".close-modal").forEach(b=>b.addEventListener("click",()=>b.closest(".tg-modal")?.classList.add("hidden")));
  $$(".tg-modal").forEach(m=>m.addEventListener("click",e=>{if(e.target===m)m.classList.add("hidden")}));

  function updateUploadProgress(clientId,pct){
    const row=clientNode(clientId);if(!row)return;pct=Math.max(0,Math.min(100,Math.round(pct||0)));
    row.querySelectorAll(".tg-upload-ring[data-upload-client]").forEach(x=>x.style.setProperty("--p",pct));
    const copy=row.querySelector(".tg-attachment-copy span");if(copy){const file=uploadFiles.get(clientId)?.file;copy.textContent=`Отправка ${pct}%${file?` · ${formatBytes(file.size)}`:""}`}
    row.querySelectorAll(".tg-media-upload-state small").forEach(x=>x.textContent=`${pct}%`);
    row.querySelectorAll(".tg-attachment-progress i").forEach(x=>x.style.width=`${pct}%`);
  }
  function optimisticAttachmentMessage(file,clientId,localUrl,voice=false,meta={}){
    const ct=file.type||"application/octet-stream";
    return {
      id:`pending-${clientId}`,client_message_id:clientId,body:meta.body||"",kind:voice?"voice":"file",
      created_at:new Date(serverTimestamp()).toISOString(),time_hm:formatClock(),
      sender:{id:cfg.userId,name:cfg.userName,avatar:cfg.userAvatar,initials:(cfg.userName||"?").slice(0,2).toUpperCase()},
      reactions:{},receipts:{total:0,delivered:0,read:0},_pending:true,_uploading:true,
      attachments:[{id:`local-${clientId}`,client_id:clientId,name:file.name||`voice-${Date.now()}.webm`,size:file.size||0,content_type:ct,scan_status:"uploading",upload_progress:0,local_url:localUrl||""}]
    };
  }
  function xhrUpload(fd,clientId){
    return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();xhr.open("POST",cfg.uploadUrl,true);xhr.responseType="json";
      xhr.setRequestHeader("X-CSRFToken",RMesUI.csrf());xhr.setRequestHeader("X-Requested-With","XMLHttpRequest");
      xhr.upload.onprogress=e=>{if(e.lengthComputable)updateUploadProgress(clientId,(e.loaded/e.total)*100)};
      xhr.onerror=()=>reject(new Error("Нет соединения с сервером"));
      xhr.ontimeout=()=>reject(new Error("Сервер слишком долго не отвечает"));
      xhr.onload=()=>{let j=xhr.response;try{if(!j&&xhr.responseText)j=JSON.parse(xhr.responseText)}catch(_){};if(xhr.status>=200&&xhr.status<300)resolve(j||{});else reject(new Error(j?.detail||`Ошибка загрузки (${xhr.status})`))};
      xhr.send(fd);
    });
  }
  async function optimizeImageForUpload(file){
    if(!file||!String(file.type||"").startsWith("image/")||file.type==="image/gif"||file.size<900*1024||!window.createImageBitmap)return file;
    try{
      const bitmap=await createImageBitmap(file),maxSide=2560,scale=Math.min(1,maxSide/Math.max(bitmap.width,bitmap.height));
      if(scale>=.999&&file.size<2.5*1024*1024){bitmap.close?.();return file}
      const canvas=document.createElement("canvas");canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));
      const ctx=canvas.getContext("2d",{alpha:false});ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close?.();
      const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/webp",.86));
      if(!blob||blob.size>=file.size)return file;
      const clean=(file.name||"image").replace(/\.[^.]+$/,""),optimized=new File([blob],`${clean}.webp`,{type:"image/webp",lastModified:Date.now()});
      RMesUI.toast(`Фото оптимизировано: ${formatBytes(file.size)} → ${formatBytes(optimized.size)}`);
      return optimized;
    }catch(_){return file}
  }

  async function uploadFile(file,voice=false,meta={}){
    if(!file)return null;
    if(!voice)file=await optimizeImageForUpload(file);
    if(file.size>cfg.maxUploadMb*1024*1024){RMesUI.toast(`Файл больше ${cfg.maxUploadMb} MB`,"error");return null}
    const clientId=meta.clientId||makeClientId();
    const previewable=String(file.type||"").startsWith("image/")||String(file.type||"").startsWith("video/")||String(file.type||"").startsWith("audio/");
    const localUrl=meta.localUrl!==undefined?meta.localUrl:(previewable?URL.createObjectURL(file):"");
    uploadFiles.set(clientId,{file,voice,meta:{...meta,clientId,localUrl}});
    if(!clientNode(clientId)){upsertMessage(optimisticAttachmentMessage(file,clientId,localUrl,voice,meta),{forceScroll:true});updateSidebarPreview(attachmentKind(file.type)||file.name)}
    const fd=new FormData();fd.append("file",file,file.name||`voice-${Date.now()}.webm`);fd.append("client_id",clientId);if(voice)fd.append("voice","1");if(meta.body)fd.append("body",meta.body);
    try{
      const j=await xhrUpload(fd,clientId);updateUploadProgress(clientId,100);
      if(j.message){
        let keepLocal=false;
        for(const a of (j.message.attachments||[])){if(localUrl&&!a.url){a.local_url=localUrl;uploadPreviewByAttachment.set(String(a.id),localUrl);keepLocal=true}}
        upsertMessage(j.message,{forceScroll:true});
        if(localUrl&&!keepLocal){try{URL.revokeObjectURL(localUrl)}catch(_){}}
      }
      uploadFiles.delete(clientId);if(meta.toast)RMesUI.toast(meta.toast,"success");setTimeout(refreshPendingAttachments,300);return j;
    }catch(err){
      const row=clientNode(clientId);if(row){row.classList.remove("sending");row.classList.add("send-failed");const state=row.querySelector(".tg-send-state");if(state)state.outerHTML=`<button class="tg-send-state failed" type="button" data-retry-upload-client="${esc(clientId)}" title="${esc(err.message)}">!</button>`;const copy=row.querySelector(".tg-attachment-copy span");if(copy)copy.textContent=`Не отправлено · ${formatBytes(file.size)}`}
      RMesUI.toast(err.message,"error");return null;
    }
  }
  const attachPanel=$("#attachPanel");
  $("#attachButton")?.addEventListener("click",e=>{e.stopPropagation();attachPanel?.classList.toggle("hidden");$("#emojiPanel")?.classList.add("hidden");$("#stickerPanel")?.classList.add("hidden")});
  attachPanel?.addEventListener("click",e=>{const b=e.target.closest("[data-attach]");if(!b)return;attachPanel.classList.add("hidden");if(b.dataset.attach==="media")$("#mediaInput")?.click();else $("#fileInput")?.click()});
  document.addEventListener("click",e=>{if(attachPanel&&!attachPanel.contains(e.target)&&!e.target.closest("#attachButton"))attachPanel.classList.add("hidden")});
  $("#fileInput")?.addEventListener("change",e=>{[...e.target.files].forEach(file=>uploadFile(file));e.target.value="";});
  $("#mediaInput")?.addEventListener("change",e=>{[...e.target.files].forEach(file=>uploadFile(file));e.target.value="";});
  input?.addEventListener("paste",e=>{
    const files=[...(e.clipboardData?.files||[])];
    if(!files.length)return;
    e.preventDefault();
    files.forEach(file=>uploadFile(file));
  });

  const chatStage=document.querySelector(".tg-chat");
  chatStage?.addEventListener("dragover",e=>{e.preventDefault();chatStage.classList.add("dragging")});
  chatStage?.addEventListener("dragleave",()=>chatStage.classList.remove("dragging"));
  chatStage?.addEventListener("drop",e=>{e.preventDefault();chatStage.classList.remove("dragging");[...(e.dataTransfer?.files||[])].forEach(file=>uploadFile(file))});

  const voiceRecorder=$("#voiceRecorder"),voiceComposer=document.querySelector(".tg-composer"),voiceCanvas=$("#voiceRecordWave"),voiceTimer=$("#voiceRecordTime");
  function voiceMimeType(){
    const variants=["audio/webm;codecs=opus","audio/ogg;codecs=opus","audio/mp4","audio/webm"];
    return variants.find(type=>window.MediaRecorder&&MediaRecorder.isTypeSupported(type))||"";
  }
  function resetVoiceRecorder(){
    if(recordingFrame)cancelAnimationFrame(recordingFrame);recordingFrame=null;
    clearTimeout(recordingMaxTimer);recordingMaxTimer=null;
    recorderStream?.getTracks().forEach(track=>track.stop());recorderStream=null;
    if(recordingCtx){recordingCtx.close().catch(()=>{});recordingCtx=null}
    voiceRecorder?.classList.add("hidden");voiceComposer?.classList.remove("hidden");
    $("#voiceButton")?.classList.remove("recording");if(voiceTimer)voiceTimer.textContent="0:00";
  }
  async function startVoiceRecorder(){
    if(recorder&&recorder.state!=="inactive")return;
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){RMesUI.toast("Запись голоса недоступна","error");return}
    try{
      recorderStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      const mime=voiceMimeType(),options=mime?{mimeType:mime}:{},analyserCtx=new (window.AudioContext||window.webkitAudioContext)();recordingCtx=analyserCtx;
      const source=analyserCtx.createMediaStreamSource(recorderStream),analyser=analyserCtx.createAnalyser();analyser.fftSize=128;source.connect(analyser);
      chunks=[];recordingCancelled=false;recordingStartedAt=performance.now();recorder=new MediaRecorder(recorderStream,options);
      recorder.ondataavailable=event=>{if(event.data?.size)chunks.push(event.data)};
      recorder.onstop=()=>{
        const shouldSend=!recordingCancelled&&chunks.length&&performance.now()-recordingStartedAt>350;
        const actualMime=recorder?.mimeType||mime||"audio/webm";
        const blob=shouldSend?new Blob(chunks,{type:actualMime}):null;
        recorder=null;chunks=[];resetVoiceRecorder();
        if(blob){const ext=actualMime.includes("ogg")?"ogg":actualMime.includes("mp4")?"m4a":"webm";uploadFile(new File([blob],`voice-${Date.now()}.${ext}`,{type:actualMime}),true)}
      };
      const values=new Uint8Array(analyser.frequencyBinCount),ctx=voiceCanvas?.getContext("2d");
      const draw=()=>{
        const elapsed=(performance.now()-recordingStartedAt)/1000;if(voiceTimer)voiceTimer.textContent=mediaTime(elapsed);
        if(ctx&&voiceCanvas){analyser.getByteTimeDomainData(values);const w=voiceCanvas.width,h=voiceCanvas.height;ctx.clearRect(0,0,w,h);const grad=ctx.createLinearGradient(0,0,w,0);grad.addColorStop(0,"#64d7ff");grad.addColorStop(.48,"#2AABEE");grad.addColorStop(1,"#477bff");ctx.fillStyle=grad;ctx.shadowColor="rgba(42,171,238,.55)";ctx.shadowBlur=8;const count=54,gap=2.4,bw=(w-gap*(count-1))/count;for(let i=0;i<count;i++){const raw=Math.abs((values[Math.floor(i*values.length/count)]-128)/128),bh=Math.max(4,Math.pow(raw,.62)*(h-5));const x=i*(bw+gap),y=(h-bh)/2;ctx.beginPath();ctx.roundRect?ctx.roundRect(x,y,bw,bh,bw/2):ctx.rect(x,y,bw,bh);ctx.fill()}ctx.shadowBlur=0}
        recordingFrame=requestAnimationFrame(draw);
      };
      voiceComposer?.classList.add("hidden");voiceRecorder?.classList.remove("hidden");$("#voiceButton")?.classList.add("recording");
      recorder.start(250);draw();recordingMaxTimer=setTimeout(()=>stopVoiceRecorder(true),10*60*1000);
    }catch(err){resetVoiceRecorder();RMesUI.toast(err?.name==="NotAllowedError"?"Разрешите доступ к микрофону":"Не удалось начать запись","error")}
  }
  function stopVoiceRecorder(send){
    if(!recorder||recorder.state==="inactive"){resetVoiceRecorder();return}
    recordingCancelled=!send;try{recorder.stop()}catch(_){resetVoiceRecorder()}
  }
  $("#voiceButton")?.addEventListener("click",startVoiceRecorder);
  $("#sendVoice")?.addEventListener("click",()=>stopVoiceRecorder(true));
  $("#cancelVoice")?.addEventListener("click",()=>stopVoiceRecorder(false));

  // Telegram-like WebRTC calling through the global /ws/app/ signaling channel.
  const callOverlay=$("#callOverlay"),remoteAudio=$("#remoteAudio");
  let callId="",callConnected=false,callTimeout=null;
  const makeCallId=()=>globalThis.crypto?.randomUUID?.()||`call-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  function signalCall(type,payload={}){
    const packet={type,call_id:callId,conversation_id:cfg.conversationId,media:"audio",...payload};
    const wsSent=Boolean(window.RMesRealtime?.sendCall?.(packet));
    const hasHttpFallback=Boolean(window.RMesRealtime?.sendCallFallback);
    if(!wsSent&&!hasHttpFallback&&type!=="call_end"){RMesUI.toast("Сигнализация звонка недоступна","error")}
    // Every signal, including ICE, gets a durable HTTP copy. This keeps calls
    // working when a proxy accepts WebSocket but silently drops some frames.
    if(hasHttpFallback)setTimeout(()=>window.RMesRealtime.sendCallFallback(packet).catch(error=>{
      if(!wsSent&&type!=="call_end")RMesUI.toast(error?.message||"Не удалось доставить сигнал звонка","error");
    }),180);
    return wsSent||hasHttpFallback;
  }
  function setCallStatus(text){const el=$("#callStatus");if(el)el.textContent=text}
  function clearCallTimeout(){if(callTimeout){clearTimeout(callTimeout);callTimeout=null}}
  async function createPeer(){
    if(pc)try{pc.close()}catch(_){}
    pc=new RTCPeerConnection({iceServers:Array.isArray(cfg.rtcIceServers)?cfg.rtcIceServers:[]});
    pc.onicecandidate=e=>{if(e.candidate)signalCall("call_ice",{candidate:e.candidate.toJSON()})};
    pc.ontrack=e=>{
      callRemoteStream=e.streams[0]||callRemoteStream;
      remoteAudio.srcObject=callRemoteStream;remoteAudio.play?.().catch(()=>{});
      callConnected=true;callConnectedAt=callConnectedAt||Date.now();clearCallTimeout();setCallStatus("Соединено");
    };
    pc.onconnectionstatechange=()=>{
      if(!pc)return;
      if(pc.connectionState==="connected"){callConnected=true;callConnectedAt=callConnectedAt||Date.now();clearCallTimeout();setCallStatus("Соединено")}
      else if(["failed","disconnected"].includes(pc.connectionState)){setCallStatus("Соединение потеряно");setTimeout(()=>cleanupCall(false),900)}
      else if(pc.connectionState==="closed")cleanupCall(false);
    };
    pc.oniceconnectionstatechange=()=>{
      if(!pc)return;
      if(pc.iceConnectionState==="checking")setCallStatus("Соединение…");
      if(pc.iceConnectionState==="failed")setCallStatus("Не удалось установить медиасоединение");
    };
    return pc;
  }

  function stopCallRecordingTracks(){
    if(callRecordingCtx){try{callRecordingCtx.close()}catch(_){}}
    callRecordingCtx=null;
  }
  function buildCallRecordingStream(){
    const recorded=new MediaStream();
    const audioTracks=[];
    if(localStream?.getAudioTracks?.().length)audioTracks.push(...localStream.getAudioTracks());
    if(callRemoteStream?.getAudioTracks?.().length)audioTracks.push(...callRemoteStream.getAudioTracks());
    if(audioTracks.length&&window.AudioContext){
      const ctx=new (window.AudioContext||window.webkitAudioContext)();
      const destination=ctx.createMediaStreamDestination();
      [localStream,callRemoteStream].forEach(stream=>{
        if(stream?.getAudioTracks?.().length){const source=ctx.createMediaStreamSource(stream);source.connect(destination)}
      });
      destination.stream.getAudioTracks().forEach(track=>recorded.addTrack(track));
      callRecordingCtx=ctx;
    }else if(callRemoteStream&&callRemoteStream.getAudioTracks().length){recorded.addTrack(callRemoteStream.getAudioTracks()[0])}
    return recorded;
  }
  function recordingMimeType(){
    const variants=["audio/webm;codecs=opus","audio/ogg;codecs=opus","audio/webm"];
    return variants.find(x=>window.MediaRecorder&&MediaRecorder.isTypeSupported(x))||"";
  }
  async function uploadCallRecording(blob,recordingId,durationSeconds){
    if(!blob||!recordingId||!cfg.callRecordingUrl)return false;
    let lastError=null;
    for(let attempt=1;attempt<=5;attempt++){
      try{
        const fd=new FormData();
        fd.append("call_id",recordingId);
        fd.append("duration_seconds",String(Math.max(0,Math.round(durationSeconds||0))));
        fd.append("file",new File([blob],`rmes-call-${recordingId}.webm`,{type:blob.type||"audio/webm"}));
        const r=await fetch(cfg.callRecordingUrl,{method:"POST",headers:{"X-CSRFToken":RMesUI.csrf(),"X-Requested-With":"XMLHttpRequest"},body:fd,credentials:"same-origin"});
        if(r.ok)return true;
        let detail="Не удалось сохранить запись звонка";
        try{detail=(await r.json()).detail||detail}catch(_){}
        lastError=new Error(detail);
        if(r.status>=400&&r.status<500&&r.status!==408&&r.status!==429)break;
      }catch(err){lastError=err}
      if(attempt<5)await new Promise(resolve=>setTimeout(resolve,Math.min(12000,1200*(2**(attempt-1)))));
    }
    throw lastError||new Error("Не удалось сохранить запись звонка");
  }

  function startComplianceRecording(){
    // Audio capture is intentionally disabled by default. Call lifecycle metadata
    // is still persisted server-side for the developer control panel.
    if(cfg.callAudioRecordingEnabled!==true)return;
    if(!callInitiator||callRecorder||callUploadPending||!callRemoteStream||!window.MediaRecorder)return;
    try{
      const capture=buildCallRecordingStream();if(!capture.getTracks().length)return;
      callRecordChunks=[];callStartedAt=callStartedAt||Date.now();callRecordingId=callId;
      const options={};const mime=recordingMimeType();if(mime)options.mimeType=mime;
      callRecorder=new MediaRecorder(capture,options);
      callRecorder.ondataavailable=e=>{if(e.data?.size)callRecordChunks.push(e.data)};
      callRecorder.onstop=async()=>{
        try{
          if(!callRecordChunks.length)return;
          const blob=new Blob(callRecordChunks,{type:callRecorder?.mimeType||recordingMimeType()||"application/octet-stream"});
          const duration=Math.max(0,((Date.now()-(callConnectedAt||callStartedAt||Date.now()))/1000));
          const recordId=callRecordingId;callUploadPending=true;
          await uploadCallRecording(blob,recordId,duration);
        }catch(err){console.warn("Call recording upload failed",err);RMesUI.toast("Запись звонка сохранится после проверки соединения","error")}finally{callRecorder=null;callRecordChunks=[];callUploadPending=false;callStartedAt=null;callConnectedAt=null;callRecordingId="";stopCallRecordingTracks()}
      };
      callRecorder.start(1000);
    }catch(err){console.warn("Call recording init failed",err);stopCallRecordingTracks()}
  }
  function stopComplianceRecording(){
    if(callRecorder&&callRecorder.state!=="inactive")callRecorder.stop();
    else{callRecorder=null;callRecordChunks=[];callStartedAt=null;stopCallRecordingTracks()}
  }
  async function getLocal(){
    if(!navigator.mediaDevices?.getUserMedia)throw new Error("Микрофон недоступен");
    localStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
    return localStream;
  }
  async function startCall(){
    if(pc||pendingOffer){RMesUI.toast("У вас уже есть активный звонок","error");return}
    if(!window.RMesRealtime?.sendCall){RMesUI.toast("Сервис звонков ещё не готов","error");return}
    callId=makeCallId();callInitiator=true;callConnected=false;callConnectedAt=null;callStartedAt=window.RMesServerClock?.now?.()||Date.now();
    callOverlay.classList.remove("hidden");setCallStatus("Вызов…");$("#acceptCall").classList.add("hidden");
    $("#callTitle").textContent=cfg.peerName||$("#callTitle").textContent||"Звонок";
    try{
      await createPeer();await getLocal();localStream.getTracks().forEach(t=>pc.addTrack(t,localStream));
      const offer=await pc.createOffer({offerToReceiveAudio:true,offerToReceiveVideo:false});await pc.setLocalDescription(offer);
      if(!signalCall("call_offer",{sdp:pc.localDescription}))throw new Error("Сигнализация недоступна");
      callTimeout=setTimeout(()=>{if(!callConnected){setCallStatus("Нет ответа");signalCall("call_end",{reason:"timeout"});setTimeout(()=>cleanupCall(false),1000)}},30000);
    }catch(err){RMesUI.toast("Не удалось начать звонок: "+(err.message||err),"error");cleanupCall(false)}
  }
  async function acceptCall(){
    if(!pendingOffer)return;
    callInitiator=false;callConnected=false;callConnectedAt=null;callStartedAt=window.RMesServerClock?.now?.()||Date.now();
    try{
      await createPeer();await getLocal();localStream.getTracks().forEach(t=>pc.addTrack(t,localStream));
      await pc.setRemoteDescription(new RTCSessionDescription(pendingOffer));
      for(const c of pendingIce.splice(0))await pc.addIceCandidate(new RTCIceCandidate(c));
      const answer=await pc.createAnswer();await pc.setLocalDescription(answer);
      signalCall("call_answer",{sdp:pc.localDescription});
      $("#acceptCall").classList.add("hidden");setCallStatus("Соединение…");pendingOffer=null;
      sessionStorage.removeItem("rmes:pending-call");
    }catch(err){RMesUI.toast("Не удалось принять звонок: "+(err.message||err),"error");signalCall("call_reject",{reason:"media_error"});cleanupCall(false)}
  }
  function cleanupCall(signal=true,reason="ended"){
    clearCallTimeout();
    if(signal&&callId)signalCall(pendingOffer&&!callConnected?"call_reject":"call_end",{reason});
    localStream?.getTracks().forEach(t=>t.stop());localStream=null;callRemoteStream=null;
    if(remoteAudio)remoteAudio.srcObject=null;
    if(pc)try{pc.close()}catch(_){}pc=null;pendingOffer=null;pendingIce=[];callInitiator=false;callConnected=false;callId="";
    callOverlay?.classList.add("hidden");sessionStorage.removeItem("rmes:pending-call");
  }
  async function handleCallSignal(d){
    if(Number(d.from_user)===Number(cfg.userId))return;
    try{
      if(d.type==="call_offer"){
        if((pc||pendingOffer)&&callId&&callId!==d.call_id){window.RMesRealtime?.sendCall?.({type:"call_busy",call_id:d.call_id,conversation_id:cfg.conversationId,reason:"busy"});return}
        callId=d.call_id||makeCallId();callInitiator=false;pendingOffer=d.sdp;callOverlay.classList.remove("hidden");
        $("#callTitle").textContent=d.from_name||cfg.peerName||"Входящий звонок";setCallStatus("Входящий аудиозвонок");$("#acceptCall").classList.remove("hidden");
        for(const candidate of (d.pending_ice||[]))pendingIce.push(candidate);
      }else if(d.call_id&&callId&&d.call_id!==callId)return;
      else if(d.type==="call_answer"&&pc){await pc.setRemoteDescription(new RTCSessionDescription(d.sdp));for(const c of pendingIce.splice(0))await pc.addIceCandidate(new RTCIceCandidate(c));setCallStatus("Соединение…")}
      else if(d.type==="call_ice"&&d.candidate){if(pc&&pc.remoteDescription)await pc.addIceCandidate(new RTCIceCandidate(d.candidate));else pendingIce.push(d.candidate)}
      else if(d.type==="call_busy"){setCallStatus("Пользователь занят");setTimeout(()=>cleanupCall(false),1200)}
      else if(d.type==="call_reject"){setCallStatus("Вызов отклонён");setTimeout(()=>cleanupCall(false),1000)}
      else if(d.type==="call_end"){setCallStatus("Звонок завершён");setTimeout(()=>cleanupCall(false),650)}
      else if(d.type==="call_error"){RMesUI.toast(d.message||"Ошибка звонка","error");cleanupCall(false)}
    }catch(err){RMesUI.toast("Ошибка звонка: "+err.message,"error");cleanupCall(false)}
  }
  $("#callAudio")?.addEventListener("click",startCall);
  $("#acceptCall")?.addEventListener("click",acceptCall);
  $("#endCall")?.addEventListener("click",()=>cleanupCall(true));
  $("#toggleMic")?.addEventListener("click",e=>{const t=localStream?.getAudioTracks()[0];if(t){t.enabled=!t.enabled;e.currentTarget.classList.toggle("off",!t.enabled);e.currentTarget.title=t.enabled?"Выключить микрофон":"Включить микрофон"}});
  window.RMesChatCalls={handleSignal:handleCallSignal,accept:acceptCall,isBusy:()=>Boolean(pc||pendingOffer),end:()=>cleanupCall(true)};
  try{
    const pending=JSON.parse(sessionStorage.getItem("rmes:pending-call")||"null");
    if(pending&&String(pending.conversation_id)===String(cfg.conversationId)){
      handleCallSignal(pending).then(async()=>{
        for(const candidate of (pending.pending_ice||[]))await handleCallSignal({type:"call_ice",call_id:pending.call_id,candidate});
        if(pending.auto_accept)setTimeout(()=>acceptCall(),80);
      }).catch(()=>{});
    }
  }catch(_){}

  function exitChat(){
    exiting=true;clearTimeout(reconnectTimer);
    try{if(ws&&ws.readyState<=1)ws.close()}catch(_){}
    const chat=document.querySelector(".tg-chat");
    if(chat){
      chat.classList.remove("chat-enter");
      chat.classList.add("chat-leaving");
      setTimeout(()=>{location.href=cfg.homeUrl||"/"},150);
    }else location.href=cfg.homeUrl||"/";
  }
  $("#closeChatBtn")?.addEventListener("click",exitChat);

  document.addEventListener("keydown",e=>{
    if(e.key!=="Escape")return;
    const visibleModal=$$(".tg-modal").find(m=>!m.classList.contains("hidden"));
    if(visibleModal){visibleModal.classList.add("hidden");return}
    if(callOverlay&&!callOverlay.classList.contains("hidden")){cleanupCall(true);return}
    if(searchPanel&&!searchPanel.classList.contains("hidden")){closeSearch();return}
    if(chatMenu&&!chatMenu.classList.contains("hidden")){chatMenu.classList.add("hidden");return}
    if($("#emojiPanel")&&!$("#emojiPanel").classList.contains("hidden")){$("#emojiPanel").classList.add("hidden");return}
    if($("#reactionPopover")&&!$("#reactionPopover").classList.contains("hidden")){$("#reactionPopover").classList.add("hidden");return}
    if($("#stickerPanel")&&!$("#stickerPanel").classList.contains("hidden")){$("#stickerPanel").classList.add("hidden");return}
    if($("#mentionSuggest")&&!$("#mentionSuggest").classList.contains("hidden")){$("#mentionSuggest").classList.add("hidden");return}
    if($("#messageContextMenu")&&!$("#messageContextMenu").classList.contains("hidden")){$("#messageContextMenu").classList.add("hidden");return}
    if($("#globalSearchResults")&&!$("#globalSearchResults").classList.contains("hidden")){$("#globalSearchResults").classList.add("hidden");return}
    if(replyTo){clearReply();return}
    exitChat();
  });


  // Desktop context menu + touch long-press.
  const contextMenu=$("#messageContextMenu");
  let contextMessageRow=null,longPressTimer=null;
  function openContextMenu(row,x,y){
    if(!row||!contextMenu)return;
    contextMessageRow=row;
    const own=Number(row.dataset.senderId)===Number(cfg.userId);
    contextMenu.querySelectorAll("[data-owner-only]").forEach(b=>b.classList.toggle("hidden",!own));
    contextMenu.style.left=Math.min(x,window.innerWidth-220)+"px";
    contextMenu.style.top=Math.min(y,window.innerHeight-285)+"px";
    contextMenu.classList.remove("hidden");
  }
  stream?.addEventListener("contextmenu",e=>{
    const row=e.target.closest(".tg-message");if(!row)return;
    e.preventDefault();openContextMenu(row,e.clientX,e.clientY);
  });
  stream?.addEventListener("pointerdown",e=>{
    if(e.pointerType!=="touch")return;
    const row=e.target.closest(".tg-message");if(!row)return;
    clearTimeout(longPressTimer);
    longPressTimer=setTimeout(()=>openContextMenu(row,e.clientX||window.innerWidth/2,e.clientY||window.innerHeight/2),520);
  },{passive:true});
  ["pointerup","pointercancel","pointermove"].forEach(name=>stream?.addEventListener(name,()=>clearTimeout(longPressTimer),{passive:true}));
  contextMenu?.addEventListener("click",async e=>{
    const b=e.target.closest("[data-context-action]");if(!b||!contextMessageRow)return;
    const action=b.dataset.contextAction;
    if(action==="copy"){
      const text=contextMessageRow.querySelector(".tg-message-text")?.innerText||"";
      try{await navigator.clipboard.writeText(text);RMesUI.toast("Сообщение скопировано","success")}catch(_){RMesUI.toast("Не удалось скопировать","error")}
    }else{
      contextMessageRow.querySelector(`.tg-message-actions [data-action="${action}"]`)?.click();
    }
    contextMenu.classList.add("hidden");
  });
  document.addEventListener("click",e=>{if(contextMenu&&!contextMenu.contains(e.target))contextMenu.classList.add("hidden")});

  // Productivity keyboard shortcuts.
  document.addEventListener("keydown",e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="f"){
      e.preventDefault();searchPanel?.classList.remove("hidden");searchInput?.focus();searchInput?.select();return;
    }
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){
      e.preventDefault();document.querySelector("#globalSearch")?.focus();return;
    }
    if(e.altKey&&e.key==="ArrowLeft"){e.preventDefault();exitChat();}
  });

  if(cfg.notify&&"Notification" in window&&Notification.permission==="default"){
    setTimeout(()=>Notification.requestPermission().catch(()=>{}),1500);
  }

  requestAnimationFrame(()=>{
    const savedDraft=localStorage.getItem(draftKey);
    if(input&&savedDraft&&!input.value){input.value=savedDraft;autoGrow();}
    document.querySelector(".tg-chat")?.classList.add("chat-entered");
    if(cfg.jumpMessageId){
      const n=node(cfg.jumpMessageId);
      if(n){n.scrollIntoView({block:"center"});n.classList.add("highlight");setTimeout(()=>n.classList.remove("highlight"),1200)}
    }else scrollBottom();
    updateScrollButton();markReadSoon();
  });
})();
