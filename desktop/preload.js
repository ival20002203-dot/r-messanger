const {contextBridge,ipcRenderer}=require("electron");

function unreadCount(){
  try{
    let total=0;
    document.querySelectorAll(".tg-chat-item .tg-unread").forEach(el=>{
      const value=Number((el.textContent||"").replace(/\D/g,""))||1;
      total+=value;
    });
    return total;
  }catch(_){return 0}
}
function publishUnread(){ipcRenderer.send("unread-count",unreadCount())}

window.addEventListener("DOMContentLoaded",()=>{
  publishUnread();
  const observer=new MutationObserver(()=>publishUnread());
  observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true});
  setInterval(publishUnread,15000);
});

const rmesDesktopBridge={
  isDesktop:true,
  getSettings:()=>ipcRenderer.invoke("desktop-settings"),
  getWindowState:()=>ipcRenderer.invoke("desktop-window-state"),
  saveSettings:value=>ipcRenderer.invoke("save-desktop-settings",value),
  retry:()=>ipcRenderer.send("retry-server"),
  reload:()=>ipcRenderer.send("desktop-reload"),
  showNotification:payload=>ipcRenderer.invoke("desktop-notification",payload),
  onVisibility:callback=>{
    if(typeof callback!=="function")return ()=>{};
    const handler=(_event,state)=>callback(state||{});ipcRenderer.on("desktop-visibility",handler);
    return ()=>ipcRenderer.removeListener("desktop-visibility",handler);
  },
  installUpdate:payload=>ipcRenderer.invoke("client-update-install",payload)
  ,checkUpdate:()=>ipcRenderer.invoke("client-update-check")
  ,applyUpdate:()=>ipcRenderer.invoke("client-update-apply")
  ,onUpdateState:callback=>{
    if(typeof callback!=="function")return ()=>{};
    const handler=(_event,state)=>callback(state||{});ipcRenderer.on("client-update-state",handler);
    return ()=>ipcRenderer.removeListener("client-update-state",handler);
  }
};
contextBridge.exposeInMainWorld("RMesDesktop",rmesDesktopBridge);
