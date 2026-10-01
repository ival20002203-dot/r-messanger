const {contextBridge,ipcRenderer}=require("electron");
contextBridge.exposeInMainWorld("RMesNotice",{
  open:()=>ipcRenderer.send("notification-action","open"),
  close:()=>ipcRenderer.send("notification-action","close")
});
