const {app,BrowserWindow,Menu,Tray,nativeImage,ipcMain,shell,session,dialog,net,screen}=require("electron");
const path=require("path");
const fs=require("fs");
const crypto=require("crypto");
const {spawn}=require("child_process");
let autoUpdater=null;
try{({autoUpdater}=require("electron-updater"))}catch(_){}

const BRAND_NAME="R-Messanger";
const DEFAULT_URL=process.env.R_MES_URL||"http://127.0.0.1:8000";
const LOCAL_FALLBACK_URL=process.env.R_MES_LOCAL_URL||"http://127.0.0.1:8000";
const LEGACY_SERVER_URLS=new Set(["http://127.0.0.1:8000"]);
try{
  const secureOrigins=[DEFAULT_URL,LOCAL_FALLBACK_URL].map(x=>new URL(x).origin).filter(x=>x.startsWith("http://"));
  if(secureOrigins.length)app.commandLine.appendSwitch("unsafely-treat-insecure-origin-as-secure",secureOrigins.join(","));
  app.commandLine.appendSwitch("autoplay-policy","no-user-gesture-required");
}catch(_){}
let desktopStartPending=true;
let loadingRMes=false;
let activeServerUrl=null;
let win=null,tray=null,forceQuit=false,unreadCount=0,updateState="idle",notificationWindows=[];

function settingsPath(){return path.join(app.getPath("userData"),"desktop-settings.json")}
function loadSettings(){
  const defaults={serverUrl:DEFAULT_URL,minimizeToTray:true,startAtLogin:true};
  try{
    const saved={...defaults,...JSON.parse(fs.readFileSync(settingsPath(),"utf8"))};
    if(LEGACY_SERVER_URLS.has(saved.serverUrl)&&saved.serverUrl!==DEFAULT_URL){saved.serverUrl=DEFAULT_URL;saveSettings(saved)}
    return saved;
  }catch(_){return defaults}
}
function saveSettings(data){fs.writeFileSync(settingsPath(),JSON.stringify(data,null,2),"utf8")}

function trayImage(){
  const img=nativeImage.createFromPath(path.join(__dirname,"assets","tray.png"));
  return img.isEmpty()?nativeImage.createFromPath(path.join(__dirname,"assets","icon.png")).resize({width:20,height:20}):img.resize({width:20,height:20});
}
function updateTray(){
  if(!tray)return;
  tray.setToolTip(unreadCount?`${BRAND_NAME} — ${unreadCount} непрочитанных`:BRAND_NAME);
  tray.setContextMenu(Menu.buildFromTemplate([
    {label:unreadCount?`Непрочитанные: ${unreadCount}`:"Нет непрочитанных",enabled:false},
    {type:"separator"},
    {label:`Открыть ${BRAND_NAME}`,click:()=>{win.show();win.focus()}},
    {label:"Заблокировать",click:()=>{win.show();win.focus();win.webContents.executeJavaScript("window.RMesLock?.lockNow?.(\"tray\")").catch(()=>{})}},
    {label:"Перезагрузить",click:()=>loadRMes()},
    {label:updateState==="ready"?"Перезапустить и обновить":updateState==="downloading"?"Обновление загружается…":updateState==="available"?"Доступно обновление":"Проверить обновления",click:()=>updateState==="ready"?applyReadyUpdate():checkForUpdates(true),enabled:Boolean(autoUpdater)&&updateState!=="downloading"},
    {type:"separator"},
    {label:"Выход",click:()=>{forceQuit=true;app.quit()}}
  ]));
}
function unreadOverlayIcon(count){
  const label=count>99?"99+":String(count);
  const fs=label.length>2?9:11;
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><circle cx="16" cy="16" r="15" fill="#2AABEE" stroke="#ffffff" stroke-width="2"/><text x="16" y="20" text-anchor="middle" font-family="Segoe UI,Arial" font-size="${fs}" font-weight="700" fill="#ffffff">${label}</text></svg>`;
  return nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`).resize({width:16,height:16});
}
function setUnread(value){
  unreadCount=Math.max(0,Number(value)||0);
  if(process.platform==="darwin")app.setBadgeCount(unreadCount);
  if(process.platform==="win32"&&win&&!win.isDestroyed()){try{win.setOverlayIcon(unreadCount?unreadOverlayIcon(unreadCount):null,unreadCount?`${unreadCount} непрочитанных`:"")}catch(_){}}
  updateTray();
}

function mediaOriginFor(value){
  try{const u=new URL(value);u.port="9000";u.pathname="/";u.search="";u.hash="";return u.origin}catch(_){return ""}
}
function internalOrigins(){
  const cfg=loadSettings();
  const values=[activeServerUrl,cfg.serverUrl,DEFAULT_URL,LOCAL_FALLBACK_URL,mediaOriginFor(activeServerUrl),mediaOriginFor(cfg.serverUrl),mediaOriginFor(DEFAULT_URL),"http://127.0.0.1:9000","http://localhost:9000"];
  const extra=String(process.env.R_MES_ALLOWED_ORIGINS||"").split(",").map(x=>x.trim()).filter(Boolean);
  return new Set([...values,...extra].map(value=>{try{return new URL(value).origin}catch(_){return ""}}).filter(Boolean));
}
function isAllowedInternal(url){
  try{
    const target=new URL(url);
    return target.protocol==="rmes:"||internalOrigins().has(target.origin);
  }catch(_){return false}
}

async function canReach(url){
  try{
    const r=await fetch(url,{method:"GET",redirect:"follow",headers:{"X-R-Mes-Desktop":"1","X-R-Mes-Client":"desktop","User-Agent":`RMesDesktop/${app.getVersion()}`},signal:AbortSignal.timeout(2500)});
    return r.status>=200&&r.status<500;
  }catch(_){return false}
}

function desktopTarget(base){
  const clean=String(base||"").replace(/\/$/,"");
  if(desktopStartPending){desktopStartPending=false;return `${clean}/auth/app-lock/desktop-start/`}
  return `${clean}/`;
}
async function loadRMes(){
  const cfg=loadSettings(),configuredUrl=cfg.serverUrl||DEFAULT_URL;
  loadingRMes=true;
  try{
    if(await canReach(configuredUrl)){
      activeServerUrl=configuredUrl;
      await win.loadURL(desktopTarget(configuredUrl));return;
    }
    const mayUseLocal=(configuredUrl===DEFAULT_URL||LEGACY_SERVER_URLS.has(configuredUrl));
    if(mayUseLocal&&LOCAL_FALLBACK_URL!==configuredUrl&&await canReach(LOCAL_FALLBACK_URL)){
      activeServerUrl=LOCAL_FALLBACK_URL;
      await win.loadURL(desktopTarget(LOCAL_FALLBACK_URL));return;
    }
    desktopStartPending=true;
    await win.loadFile(path.join(__dirname,"offline.html"),{query:{server:configuredUrl,local:LOCAL_FALLBACK_URL}});
  }finally{loadingRMes=false}
}



function versionParts(v){return String(v||"0").split(/[.+-]/).slice(0,3).map(x=>Number.parseInt(x,10)||0)}
function versionLt(a,b){const aa=versionParts(a),bb=versionParts(b);for(let i=0;i<3;i++){if(aa[i]<bb[i])return true;if(aa[i]>bb[i])return false}return false}
function updateFeedUrl(){
  const base=(activeServerUrl||loadSettings().serverUrl||DEFAULT_URL).replace(/\/$/,"");
  const platform=process.platform==="win32"?"windows":process.platform==="darwin"?"macos":"linux";
  return `${base}/ops/client-update/feed/${platform}/`;
}
function publishUpdateState(extra={}){
  updateTray();
  if(win&&!win.isDestroyed())win.webContents.send("client-update-state",{state:updateState,...extra});
}
function applyReadyUpdate(){
  if(!autoUpdater||updateState!=="ready")return false;
  forceQuit=true;setImmediate(()=>autoUpdater.quitAndInstall(false,true));return true;
}
async function checkServerVersionPolicy(){
  if(!app.isPackaged)return;
  try{
    const base=(loadSettings().serverUrl||DEFAULT_URL).replace(/\/$/,"");
    const platform=process.platform==="win32"?"windows":process.platform==="darwin"?"macos":"linux";
    const r=await fetch(`${base}/ops/client-policy/?platform=${platform}`,{headers:{"X-R-Mes-Desktop":"1","X-R-Mes-Client":"desktop","User-Agent":`RMesDesktop/${app.getVersion()}`},signal:AbortSignal.timeout(8000)});
    if(!r.ok)return;
    const policy=await r.json(),current=app.getVersion();
    const belowMin=versionLt(current,policy.minimum_version),behind=versionLt(current,policy.latest_version);
    if(!belowMin&&!(policy.force_update&&behind))return;
    updateState="required";updateTray();
    const result=await dialog.showMessageBox(win,{type:"warning",title:`Требуется обновление ${BRAND_NAME}`,message:`Установлена ${current}. Минимальная версия: ${policy.minimum_version}.`,detail:policy.release_notes||"Обновите корпоративный клиент.",buttons:["Обновить","Позже"],defaultId:0,cancelId:1});
    if(result.response===0)checkForUpdates(true)
  }catch(_){}
}

function checkForUpdates(userInitiated=false){
  if(!autoUpdater||!app.isPackaged)return Promise.resolve({ok:false,error:"Автообновление доступно в установленном приложении."});
  const url=(process.env.R_MES_UPDATE_URL||updateFeedUrl()).replace(/\/?$/,"/");
  try{
    autoUpdater.setFeedURL({provider:"generic",url});
    autoUpdater.requestHeaders={"X-R-Mes-Desktop":"1","X-R-Mes-Client":"desktop","User-Agent":`RMesDesktop/${app.getVersion()}`};
    updateState="checking";publishUpdateState();
    return autoUpdater.checkForUpdates().then(()=>({ok:true,managed:true})).catch(err=>{updateState="error";publishUpdateState({error:String(err?.message||err)});if(userInitiated&&win)dialog.showMessageBox(win,{type:"error",title:"Обновление R-Messanger",message:"Не удалось проверить обновление",detail:String(err?.message||err)});return {ok:false,error:String(err?.message||err)}});
  }catch(err){updateState="error";publishUpdateState({error:String(err?.message||err)});return Promise.resolve({ok:false,error:String(err?.message||err)})}
}
function setupAutoUpdate(){
  if(!autoUpdater||!app.isPackaged)return;
  autoUpdater.autoDownload=true;
  autoUpdater.autoInstallOnAppQuit=true;
  autoUpdater.on("update-available",info=>{updateState="available";publishUpdateState({version:info?.version})});
  autoUpdater.on("update-not-available",()=>{updateState="current";publishUpdateState()});
  autoUpdater.on("download-progress",progress=>{updateState="downloading";publishUpdateState({percent:Math.round(progress?.percent||0)})});
  autoUpdater.on("update-downloaded",async info=>{
    updateState="ready";publishUpdateState({version:info?.version});
    if(!win||win.isDestroyed())return;
    const result=await dialog.showMessageBox(win,{type:"info",title:"Обновление R-Messanger готово",message:`Версия ${info?.version||"новая"} загружена внутри приложения`,detail:"Нажмите «Перезапустить сейчас». Обновление установится автоматически, переписка и настройки сохранятся.",buttons:["Перезапустить сейчас","Позже"],defaultId:0,cancelId:1});
    if(result.response===0)applyReadyUpdate();
  });
  autoUpdater.on("error",error=>{updateState="error";publishUpdateState({error:String(error?.message||error)})});
  setTimeout(()=>{checkForUpdates(false);checkServerVersionPolicy()},8000);
  setInterval(()=>{checkForUpdates(false);checkServerVersionPolicy()},6*60*60*1000);
}

function createWindow(){
  win=new BrowserWindow({
    width:1320,height:860,minWidth:940,minHeight:620,
    backgroundColor:"#0e1621",
    show:false,
    title:BRAND_NAME,
    icon:path.join(__dirname,"assets","icon.png"),
    autoHideMenuBar:true,
    webPreferences:{
      preload:path.join(__dirname,"preload.js"),
      contextIsolation:true,
      nodeIntegration:false,
      sandbox:true,
      spellcheck:true,
      backgroundThrottling:false
    }
  });

  session.defaultSession.setPermissionRequestHandler((webContents,permission,callback,details={})=>{
    const allowed=["notifications","media","clipboard-sanitized-write"];
    const own=isAllowedInternal(webContents.getURL());
    const cameraRequested=permission==="media"&&Array.isArray(details.mediaTypes)&&details.mediaTypes.includes("video");
    callback(Boolean(own&&allowed.includes(permission)&&!cameraRequested));
  });
  session.defaultSession.setPermissionCheckHandler((webContents,permission,origin)=>{
    return Boolean(isAllowedInternal(origin)&&["notifications","media","clipboard-sanitized-write"].includes(permission));
  });
  session.defaultSession.webRequest.onBeforeSendHeaders((details,callback)=>{
    const headers={...details.requestHeaders,"X-R-Mes-Desktop":"1","X-R-Mes-Client":"desktop"};
    callback({requestHeaders:headers});
  });

  win.webContents.setUserAgent(`${win.webContents.getUserAgent()} RMesDesktop/${app.getVersion()}`);
  win.webContents.setWindowOpenHandler(({url})=>{
    if(isAllowedInternal(url)){
      win.loadURL(url).catch(()=>{});
      return {action:"deny"};
    }
    shell.openExternal(url);return {action:"deny"};
  });
  win.webContents.on("will-navigate",(event,url)=>{
    if(!isAllowedInternal(url)){event.preventDefault();shell.openExternal(url)}
  });
  win.webContents.on("did-fail-load",async(_e,errorCode,_desc,url,isMainFrame)=>{
    if(isMainFrame&&errorCode!==-3&&!loadingRMes){
      try{await loadRMes()}catch(_){}
    }
  });
  win.on("close",e=>{
    const cfg=loadSettings();
    if(!forceQuit&&cfg.minimizeToTray){e.preventDefault();win.hide()}
  });
  win.on("show",()=>{win.webContents.send("desktop-visible");win.webContents.send("desktop-visibility",{visible:true,focused:win.isFocused()})});
  win.on("hide",()=>win.webContents.send("desktop-visibility",{visible:false,focused:false}));
  win.on("minimize",()=>win.webContents.send("desktop-visibility",{visible:true,focused:false}));
  win.on("restore",()=>win.webContents.send("desktop-visibility",{visible:true,focused:win.isFocused()}));
  win.on("focus",()=>win.webContents.send("desktop-visibility",{visible:win.isVisible(),focused:true}));
  win.on("blur",()=>win.webContents.send("desktop-visibility",{visible:win.isVisible(),focused:false}));
  win.once("ready-to-show",()=>win.show());

  tray=new Tray(trayImage());
  tray.on("double-click",()=>{win.show();win.focus()});
  updateTray();
  loadRMes();
}

ipcMain.on("unread-count",(_event,count)=>setUnread(count));
ipcMain.on("retry-server",()=>loadRMes());
ipcMain.handle("desktop-settings",()=>loadSettings());
ipcMain.handle("desktop-window-state",()=>({visible:Boolean(win&&!win.isDestroyed()&&win.isVisible()),focused:Boolean(win&&!win.isDestroyed()&&win.isFocused()),minimized:Boolean(win&&!win.isDestroyed()&&win.isMinimized())}));
ipcMain.handle("save-desktop-settings",(_event,next)=>{
  const current=loadSettings();
  const serverUrl=String(next.serverUrl||current.serverUrl).trim();
  try{
    const parsed=new URL(serverUrl);
    if(!["http:","https:"].includes(parsed.protocol))throw new Error("Invalid protocol");
  }catch(_){return {ok:false,error:`Укажите корректный http/https адрес ${BRAND_NAME}`}}
  const cfg={
    serverUrl,
    minimizeToTray:Boolean(next.minimizeToTray),
    startAtLogin:Boolean(next.startAtLogin)
  };
  saveSettings(cfg);
  app.setLoginItemSettings({openAtLogin:cfg.startAtLogin});
  return {ok:true,settings:cfg};
});
ipcMain.on("desktop-reload",()=>{desktopStartPending=false;loadRMes()});

function repositionNotifications(){
  const active=notificationWindows.filter(x=>x&&!x.isDestroyed());
  notificationWindows=active;
  let display;
  try{display=win&&!win.isDestroyed()?screen.getDisplayMatching(win.getBounds()):screen.getPrimaryDisplay()}catch(_){display=screen.getPrimaryDisplay()}
  const area=display.workArea;
  active.forEach((note,index)=>{
    const [w,h]=note.getSize();
    note.setPosition(Math.round(area.x+area.width-w-18),Math.round(area.y+area.height-h-18-index*(h+10)),false);
  });
}
function openNotificationTarget(rel){
  if(!win||win.isDestroyed())return;
  win.show();win.focus();win.flashFrame(false);
  const value=String(rel||"").trim();
  if(!value)return;
  try{
    const target=new URL(value,activeServerUrl||loadSettings().serverUrl||DEFAULT_URL).toString();
    if(isAllowedInternal(target))win.loadURL(target).catch(()=>{});
  }catch(_){}
}
async function showAppNotification(payload={}){
  const title=String(payload.title||BRAND_NAME).slice(0,120);
  const body=String(payload.body||"Новое сообщение").slice(0,500);
  const rel=String(payload.url||"").trim();
  const avatar=String(payload.icon||payload.avatar||"").trim();
  const note=new BrowserWindow({
    width:390,height:112,frame:false,transparent:true,resizable:false,movable:false,
    minimizable:false,maximizable:false,skipTaskbar:true,alwaysOnTop:true,show:false,focusable:true,
    webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,preload:path.join(__dirname,"notification-preload.js")}
  });
  notificationWindows.push(note);
  note.setAlwaysOnTop(true,"pop-up-menu");
  note.__rmesTarget=rel;
  note.webContents.setWindowOpenHandler(()=>({action:"deny"}));
  note.on("closed",()=>{notificationWindows=notificationWindows.filter(x=>x!==note);repositionNotifications()});
  await note.loadFile(path.join(__dirname,"notification.html"),{query:{title,body,avatar}});
  repositionNotifications();
  note.showInactive();
  if(win&&!win.isDestroyed()&&!win.isFocused()){win.flashFrame(true);setTimeout(()=>{if(win&&!win.isDestroyed())win.flashFrame(false)},5200)}
  setTimeout(()=>{if(!note.isDestroyed())note.close()},7000);
}
ipcMain.on("notification-action",(event,action)=>{
  const note=BrowserWindow.fromWebContents(event.sender);
  if(!note)return;
  if(action==="open")openNotificationTarget(note.__rmesTarget||"");
  if(!note.isDestroyed())note.close();
});
ipcMain.handle("desktop-notification",async(_event,payload={})=>{
  try{await showAppNotification(payload);return {ok:true}}catch(err){return {ok:false,error:String(err?.message||err)}}
});

ipcMain.handle("client-update-install",async(_event,payload={})=>{
  try{
    if(autoUpdater&&app.isPackaged){
      if(updateState==="ready"){applyReadyUpdate();return {ok:true,managed:true,state:"installing"}}
      return await checkForUpdates(true);
    }
    const url=String(payload.url||"").trim(),expected=String(payload.sha256||"").trim().toLowerCase();
    if(!url||!isAllowedInternal(url))return {ok:false,error:"Сервер обновления не разрешён."};
    const response=await net.fetch(url,{redirect:"follow",headers:{"X-R-Mes-Desktop":"1","X-R-Mes-Client":"desktop","User-Agent":`RMesDesktop/${app.getVersion()}`}});
    if(!response.ok)return {ok:false,error:`Ошибка загрузки: HTTP ${response.status}`};
    const buffer=Buffer.from(await response.arrayBuffer());
    const actual=crypto.createHash("sha256").update(buffer).digest("hex");
    if(expected&&actual!==expected)return {ok:false,error:"Контрольная сумма обновления не совпала."};
    const name=`RMes-${String(payload.version||"update").replace(/[^0-9A-Za-z._-]/g,"")}-Setup.exe`;
    const file=path.join(app.getPath("temp"),name);
    fs.writeFileSync(file,buffer);
    if(process.platform!=="win32")return {ok:false,error:"Тихая установка этого пакета поддерживается только в Windows."};
    const child=spawn(file,["/S"],{detached:true,stdio:"ignore"});child.unref();
    setTimeout(()=>{forceQuit=true;app.quit()},900);
    return {ok:true};
  }catch(err){return {ok:false,error:String(err?.message||err)}}
});
ipcMain.handle("client-update-check",()=>checkForUpdates(true));
ipcMain.handle("client-update-apply",()=>({ok:applyReadyUpdate()}));

const gotLock=app.requestSingleInstanceLock();
if(!gotLock)app.quit();
else{
  app.on("second-instance",(_event,argv)=>{
    if(win){win.show();win.focus()}
    const deep=argv.find(x=>x.startsWith("rmes://"));
    if(deep&&win)win.loadURL((activeServerUrl||loadSettings().serverUrl||DEFAULT_URL).replace(/\/$/,"")+"/");
  });
  app.whenReady().then(()=>{
    const cfg=loadSettings();
    app.setLoginItemSettings({openAtLogin:Boolean(cfg.startAtLogin)});
    createWindow();
    setupAutoUpdate();
  });
  app.on("activate",()=>{if(win)win.show();else createWindow()});
  app.on("before-quit",()=>{forceQuit=true});
}
