import test from 'node:test';
import assert from 'node:assert/strict';
import { Transcription } from './transcription.mjs';

class Socket {
  readyState=0;bufferedAmount=0;sent=[];
  send(value){this.sent.push(value)}
  close(){this.readyState=3;this.onclose?.()}
  message(value){this.onmessage?.({data:JSON.stringify(value)})}
}

test('audio before ready is retained in order; stop waits for final text and completion',async()=>{
  const socket=new Socket(),statuses=[],texts=[];
  const client=new Transcription(socket,s=>statuses.push(s),v=>texts.push(v));
  const first=new ArrayBuffer(6400),last=new ArrayBuffer(800);
  client.push(first);socket.readyState=1;
  const stopping=client.stop();
  let done=false;stopping.then(()=>done=true);
  await Promise.resolve();assert.equal(done,false);
  socket.message({type:'ready'});
  assert.deepEqual(socket.sent,[first,'stop']);
  socket.message({type:'transcript',text:'最后一句。',final:true});
  await Promise.resolve();assert.equal(done,false);
  socket.message({type:'complete'});
  assert.equal(await stopping,true);
  socket.close();
  assert.equal(statuses.at(-1),'转写已保存');
  assert.equal(texts.at(-1).text,'最后一句。');
  client.push(last);assert.deepEqual(socket.sent,[first,'stop']);
});

test('startup buffer overflow and unexpected close report failure',async()=>{
  const socket=new Socket(),statuses=[];
  const client=new Transcription(socket,s=>statuses.push(s),()=>{});
  for(let i=0;i<11;i++)client.push(new ArrayBuffer(6400));
  assert.equal(await client.stop(),false);
  assert.match(statuses.at(-1),/中断/);
  const other=new Socket();
  const second=new Transcription(other,s=>statuses.push(s),()=>{});
  other.close();
  assert.equal(await second.stop(),false);
  assert.match(statuses.at(-1),/中断/);
});

test('an unavailable provider does not claim successful transcription',async()=>{
  const socket=new Socket(),statuses=[];
  const client=new Transcription(socket,s=>statuses.push(s),()=>{});
  socket.message({type:'unavailable',message:'转写未配置'});
  assert.equal(await client.stop(),false);
  assert.equal(statuses.at(-1),'转写未配置');
});

test('ready arriving after stop cannot disable the end-confirmation deadline',async(t)=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const socket=new Socket(),statuses=[];
  const client=new Transcription(socket,s=>statuses.push(s),()=>{});
  let settled=false;
  const stopping=client.stop();stopping.then(()=>settled=true);
  socket.readyState=1;socket.message({type:'ready'});
  t.mock.timers.tick(18001);
  await Promise.resolve();
  assert.equal(settled,true);
  assert.equal(await stopping,false);
  assert.equal(statuses.at(-1),'转写尾句未确认，录音已保存');
});
