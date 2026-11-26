/* Firestore simulado para pruebas: guarda en un servidor local compartido entre "equipos" y aplica las mismas reglas que firestore.rules */
const SRV="http://localhost:8001/__db";
let store={};const listeners=[];
const email=()=>{try{return (JSON.parse(sessionStorage.getItem("mockUser"))||{}).email||""}catch(e){return ""}};
let gen=0,vuelo=0;
async function pull(){try{const g=gen;const r=await fetch(SRV,{cache:"no-store"});const n=await r.json();if(vuelo||g!==gen||window.__mockOffline)return;const ch=JSON.stringify(n)!==JSON.stringify(store);store=n;if(ch)notify()}catch(e){}}
setInterval(()=>{if(!window.__mockOffline)pull()},250);
function notify(){listeners.slice().forEach(l=>l.fire())}
const deny=()=>{const e=new Error("Missing or insufficient permissions.");e.code="permission-denied";return e};
const esp=p=>store["espacios/"+p.split("/")[1]];
function puedeLeer(path){const seg=path.split("/");const e=esp(path),m=email();
  if(seg.length===2)return !!m&&(!e||e.miembros.includes(m));
  return !!m&&!!e&&e.miembros.includes(m)&&["eventos","pend","datos"].includes(seg[2])}
function puedeEscribir(path,nuevo,viejo){const seg=path.split("/"),m=email();
  if(seg.length===2){if(!viejo)return seg[1]==="fondacio"&&m==="carpo0622@gmail.com"&&JSON.stringify(nuevo.admins)===JSON.stringify([m])&&JSON.stringify(nuevo.miembros)===JSON.stringify([m]);
    return viejo.admins.includes(m)&&nuevo.admins.includes(m)&&nuevo.admins.every(a=>nuevo.miembros.includes(a))}
  return puedeLeer(path)}
export function initializeFirestore(){return {}}
export function getFirestore(){return {}}
export function persistentLocalCache(){return {}}
export function persistentMultipleTabManager(){return {}}
export function serverTimestamp(){return new Date().toISOString()}
export function arrayUnion(...v){return {__u:v}}
export function arrayRemove(...v){return {__r:v}}
export function doc(base,...seg){const p=base&&base.path?[base.path,...seg]:seg;return {path:p.join("/"),type:"doc",id:p[p.length-1]}}
export function collection(base,...seg){return {path:[base.path,...seg].join("/"),type:"col"}}
function snapDoc(path){const d=store[path];return {exists:()=>!!d,data:()=>d?JSON.parse(JSON.stringify(d)):undefined,id:path.split("/").pop()}}
export async function getDoc(ref){if(!window.__mockOffline)await pull();if(!puedeLeer(ref.path))throw deny();return snapDoc(ref.path)}
async function commit(ops){
  for(const o of ops){const viejo=store[o.path];
    if(o.op==="update"){const n=JSON.parse(JSON.stringify(viejo||{}));for(const [k,v] of Object.entries(o.data)){
        if(v&&v.__u)n[k]=[...new Set([...(n[k]||[]),...v.__u])];else if(v&&v.__r)n[k]=(n[k]||[]).filter(x=>!v.__r.includes(x));else n[k]=v}o.data=n;o.op="set"}
    if(o.op==="set"&&!puedeEscribir(o.path,o.data,viejo))throw deny();
    if(o.op==="delete"&&!puedeLeer(o.path))throw deny();
    if(o.op==="set")store[o.path]=o.data;else delete store[o.path]}
  notify();
  if(window.__mockOffline){(window.__cola=window.__cola||[]).push(...ops);return}
  gen++;vuelo++;try{await fetch(SRV,{method:"POST",body:JSON.stringify(ops)})}finally{vuelo--;gen++}
}
window.__mockFlush=async()=>{const c=window.__cola||[];window.__cola=[];gen++;if(c.length)await fetch(SRV,{method:"POST",body:JSON.stringify(c)});gen++;await pull()};
export async function setDoc(ref,data){await commit([{op:"set",path:ref.path,data:JSON.parse(JSON.stringify(data))}])}
export async function updateDoc(ref,data){await commit([{op:"update",path:ref.path,data}])}
export function writeBatch(){const ops=[];return {set(r,d){ops.push({op:"set",path:r.path,data:JSON.parse(JSON.stringify(d))})},delete(r){ops.push({op:"delete",path:r.path})},commit:()=>commit(ops)}}
export function onSnapshot(ref,cb,err){let last=null,vivo=true;
  const l={fire(){if(!vivo)return;
    if(!puedeLeer(ref.path)){vivo=false;err&&err(deny());return}
    let snap;
    if(ref.type==="doc")snap=snapDoc(ref.path);
    else{const pre=ref.path+"/";const docs=Object.keys(store).filter(k=>k.startsWith(pre)&&!k.slice(pre.length).includes("/")).map(snapDoc);snap={docs}}
    const j=JSON.stringify(ref.type==="doc"?snap.data():snap.docs.map(d=>[d.id,d.data()]));if(j===last)return;last=j;cb(snap)}};
  listeners.push(l);pull().then(()=>l.fire());return()=>{vivo=false}}
