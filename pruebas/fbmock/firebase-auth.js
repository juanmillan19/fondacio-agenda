const subs=[];let cur=null;
try{const u=sessionStorage.getItem("mockUser");if(u)cur=JSON.parse(u)}catch(e){}
export function getAuth(){return {}}
export class GoogleAuthProvider{setCustomParameters(){}}
export function onAuthStateChanged(a,cb){subs.push(cb);setTimeout(()=>cb(cur),10);return()=>{}}
function set(u){cur=u;sessionStorage.setItem("mockUser",JSON.stringify(u));subs.forEach(f=>f(u))}
export async function signInWithPopup(){const e=window.__mockLogin;if(!e){const er=new Error("closed");er.code="auth/popup-closed-by-user";throw er}
  const u={email:e,uid:"uid-"+e};set(u);return {user:u}}
export async function signOut(){cur=null;sessionStorage.removeItem("mockUser");subs.forEach(f=>f(null))}
