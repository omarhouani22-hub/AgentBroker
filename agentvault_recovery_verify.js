'use strict';
// Native Web Crypto only. No network or persistent storage.
function recoveryDecode64(value) {
 const normalized=value.replace(/\s/g,'').replace(/-/g,'+').replace(/_/g,'/');
 return Uint8Array.from(atob(normalized),c=>c.charCodeAt(0));
}
async function verifyRecoveryCheckpoint(savedKey, checkpoint) {
 let keyBytes;
 try {
  keyBytes=recoveryDecode64(savedKey.trim());
  if(keyBytes.length!==32)throw Error('Invalid key');
  const token=recoveryDecode64(new TextDecoder().decode(recoveryDecode64(checkpoint.encrypted)));
  if(token.length<73||token[0]!==128||(token.length-57)%16!==0)throw Error('Invalid token');
  const signing=await crypto.subtle.importKey('raw',keyBytes.slice(0,16),{name:'HMAC',hash:'SHA-256'},false,['verify']);
  if(!await crypto.subtle.verify('HMAC',signing,token.slice(-32),token.slice(0,-32)))throw Error('Authentication failed');
  const decrypting=await crypto.subtle.importKey('raw',keyBytes.slice(16),{name:'AES-CBC'},false,['decrypt']);
  const raw=new Uint8Array(await crypto.subtle.decrypt({name:'AES-CBC',iv:token.slice(9,25)},decrypting,token.slice(25,-32)));
  const prefix=new TextEncoder().encode(checkpoint.vault_id+'\0');
  if(!prefix.every((byte,i)=>raw[i]===byte))throw Error('Wrong vault');
  const payload=raw.slice(prefix.length);
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',payload)),b=>b.toString(16).padStart(2,'0')).join('');
  const length=payload.length;raw.fill(0);payload.fill(0);
  if(digest!==checkpoint.digest||length!==checkpoint.byte_count)throw Error('Integrity mismatch');
  return digest;
 } finally {if(keyBytes)keyBytes.fill(0);}
}
if(typeof module!=='undefined')module.exports={verifyRecoveryCheckpoint};
