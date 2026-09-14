export async function api<T>(path:string,body?:unknown):Promise<T>{
 const res=await fetch('/api'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-Pulse-Request':'1'},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await res.json();if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'Check the request and try again.');return data;
}
