import http from 'k6/http';
import ws from 'k6/ws';
import { check } from 'k6';
import { SharedArray } from 'k6/data';
import { Counter, Trend } from 'k6/metrics';

const BASE=(__ENV.BASE_URL||'http://127.0.0.1:8000').replace(/\/$/,'');
const WS_BASE=BASE.replace(/^http:/,'ws:').replace(/^https:/,'wss:');
const users=new SharedArray('users',()=>JSON.parse(open('./users.json')));
const wsConnected=new Counter('localgram_ws_connected');
const wsErrors=new Counter('localgram_ws_errors');
const wsConnectTime=new Trend('localgram_ws_connect_ms',true);

export const options={
  scenarios:{
    websocket_users:{
      executor:'ramping-vus',
      startVUs:0,
      stages:[
        {duration:__ENV.RAMP_UP||'2m',target:Number(__ENV.TARGET_VUS||100)},
        {duration:__ENV.HOLD||'5m',target:Number(__ENV.TARGET_VUS||100)},
        {duration:__ENV.RAMP_DOWN||'1m',target:0},
      ],
      gracefulRampDown:'15s',
    }
  },
  thresholds:{
    localgram_ws_connect_ms:['p(95)<1500'],
    localgram_ws_errors:['count<50'],
  }
};

function auth(){
  const u=users[(__VU-1)%users.length];
  if(u.access_token&&u.conversation_id)return {token:u.access_token,cid:u.conversation_id};
  const r=http.post(`${BASE}/api/v1/auth/token/`,JSON.stringify({
    email:u.email,password:u.password,device_id:`k6-ws-${__VU}`,
    device_name:`k6 websocket ${__VU}`,platform:'k6'
  }),{headers:{'Content-Type':'application/json'}});
  if(r.status!==200)throw new Error(`token login failed ${r.status}`);
  const j=r.json();
  if(j.two_factor_required)throw new Error('LOGIN_EMAIL_2FA must be disabled only in the isolated load-test environment.');
  const headers={Authorization:`Bearer ${j.access_token}`};
  const chats=http.get(`${BASE}/api/v1/conversations/`,{headers}).json('results')||[];
  const cid=__ENV.CONVERSATION_ID||u.conversation_id||(chats[0]&&chats[0].id);
  if(!cid)throw new Error('No conversation. Provide conversation_id in users.json or CONVERSATION_ID.');
  return {token:j.access_token,cid};
}

export default function(){
  const a=auth();
  const started=Date.now();
  const response=ws.connect(
    `${WS_BASE}/ws/chat/${a.cid}/?access_token=${encodeURIComponent(a.token)}`,
    {},
    socket=>{
      wsConnectTime.add(Date.now()-started);
      wsConnected.add(1);
      socket.on('open',()=>socket.send(JSON.stringify({type:'read',message_id:0})));
      socket.on('error',()=>wsErrors.add(1));
      socket.setInterval(()=>socket.send(JSON.stringify({type:'typing',typing:false})),30000);
      socket.setTimeout(()=>socket.close(),Number(__ENV.WS_HOLD_MS||300000));
    }
  );
  check(response,{'websocket status 101':r=>r&&r.status===101})||wsErrors.add(1);
}
