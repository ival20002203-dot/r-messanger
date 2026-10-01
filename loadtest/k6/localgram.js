import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Trend, Rate } from 'k6/metrics';

const BASE=(__ENV.BASE_URL||'http://127.0.0.1:8000').replace(/\/$/,'');
const users=new SharedArray('users',()=>JSON.parse(open('./users.json')));
const messageLatency=new Trend('localgram_message_latency',true);
const errors=new Rate('localgram_errors');

export const options={
  scenarios:{
    messenger:{
      executor:'ramping-vus',
      startVUs:0,
      stages:[
        {duration:__ENV.RAMP_UP||'2m',target:Number(__ENV.TARGET_VUS||100)},
        {duration:__ENV.HOLD||'5m',target:Number(__ENV.TARGET_VUS||100)},
        {duration:__ENV.RAMP_DOWN||'1m',target:0},
      ],
      gracefulRampDown:'30s',
    }
  },
  thresholds:{
    http_req_failed:['rate<0.01'],
    http_req_duration:['p(95)<800'],
    localgram_message_latency:['p(95)<700'],
    localgram_errors:['rate<0.02'],
  }
};

let state=null;
function login(){
  const u=users[(__VU-1)%users.length];
  const r=http.post(`${BASE}/api/v1/auth/token/`,JSON.stringify({email:u.email,password:u.password,device_id:`k6-${__VU}`,device_name:`k6 VU ${__VU}`,platform:'k6'}),{headers:{'Content-Type':'application/json'}});
  if(r.status!==200){errors.add(1);throw new Error(`login failed ${r.status}: ${r.body}`)}
  const j=r.json();
  if(j.two_factor_required)throw new Error('Disable LOGIN_EMAIL_2FA only on the isolated load-test environment or prebuild a dedicated load-test auth strategy.');
  const headers={Authorization:`Bearer ${j.access_token}`,'Content-Type':'application/json'};
  const chats=http.get(`${BASE}/api/v1/conversations/`,{headers}).json('results')||[];
  const cid=__ENV.CONVERSATION_ID||(chats[0]&&chats[0].id);
  if(!cid)throw new Error('No conversation available. Set CONVERSATION_ID or create chats for load-test users.');
  return {headers,cid};
}

export default function(){
  if(!state)state=login();
  const body=`k6 ${__VU}/${__ITER} ${Date.now()}`;
  const clientId=`k6-${__VU}-${__ITER}-${Date.now()}`;
  const started=Date.now();
  const sent=http.post(`${BASE}/api/v1/conversations/${state.cid}/messages/`,JSON.stringify({body,client_id:clientId}),{headers:state.headers});
  messageLatency.add(Date.now()-started);
  const ok=check(sent,{'message accepted':r=>r.status===201||r.status===200});errors.add(!ok);
  if(sent.status===401){state=null;return}

  if(__ITER%5===0){
    const history=http.get(`${BASE}/api/v1/conversations/${state.cid}/messages/?limit=40`,{headers:state.headers});
    errors.add(!check(history,{'history 200':r=>r.status===200}));
  }
  if(__ITER%10===0){
    const search=http.get(`${BASE}/api/v1/users/?q=user`,{headers:state.headers});
    errors.add(!check(search,{'search 200':r=>r.status===200}));
  }
  sleep(Number(__ENV.SLEEP_SECONDS||1));
}
