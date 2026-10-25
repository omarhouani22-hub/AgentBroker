'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {verifyRecoveryCheckpoint}=require('./agentvault_recovery_verify.js');
(async()=>{
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 assert.equal(await verifyRecoveryCheckpoint(fixture.key,fixture.checkpoint),fixture.checkpoint.digest);
 await assert.rejects(verifyRecoveryCheckpoint(fixture.wrong_key,fixture.checkpoint));
 await assert.rejects(verifyRecoveryCheckpoint(fixture.key,{...fixture.checkpoint,vault_id:'b'.repeat(32)}));
 await assert.rejects(verifyRecoveryCheckpoint(fixture.key,{...fixture.checkpoint,digest:'0'.repeat(64)}));
 const token=Buffer.from(fixture.checkpoint.encrypted,'base64');token[40]^=1;
 await assert.rejects(verifyRecoveryCheckpoint(fixture.key,{...fixture.checkpoint,encrypted:token.toString('base64')}));
 console.log('PASS: valid bytes; wrong key, tenant, digest and tamper rejected');
})().catch(e=>{console.error(e.message);process.exitCode=1;});
