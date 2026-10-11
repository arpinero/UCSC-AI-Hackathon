const test = require('node:test');
const assert = require('node:assert/strict');
const {validateBase,validatePath} = require('./security.cjs');
test('connection accepts explicit loopback and private tunnel transport',()=>{
  assert.equal(validateBase('http://127.0.0.1:8787'),'http://127.0.0.1:8787');
  assert.equal(validateBase('https://example-8787.usw3.devtunnels.ms/'),'https://example-8787.usw3.devtunnels.ms');
});
test('rejects arbitrary network destinations, credentials and paths',()=>{
  for(const value of ['file:///etc/passwd','http://example.com','https://devtunnels.ms.evil.com','http://a:b@localhost:8787','http://localhost:8787/proxy','https://localhost/'])assert.throws(()=>validateBase(value));
});
test('IPC exposes only bridge routes',()=>{
  assert.equal(validatePath('/api/runs/0123456789abcdef0123456789abcdef/decision'),'/api/runs/0123456789abcdef0123456789abcdef/decision');
  for(const value of ['/api/../secrets','//other-host/','/api/models?url=http://example.com','/api/runs/a/chat','/api/health#fragment'])assert.throws(()=>validatePath(value));
});
