export class Transcription {
  constructor(socket,status,transcript){
    this.socket=socket;this.status=status;this.transcript=transcript;
    this.ready=false;this.done=false;this.stopping=false;this.stopSent=false;
    this.queue=[];this.bytes=0;
    this.completion=new Promise(resolve=>this.resolve=resolve);
    this.timer=setTimeout(()=>this.finish(false,'转写连接中断，录音继续保存'),10000);
    status('转写连接中');
    socket.onmessage=event=>{
      if(this.done)return;
      try{
        const value=JSON.parse(event.data);
        if(value.type==='ready'){
          this.ready=true;
          if(!this.stopping)clearTimeout(this.timer);
          status('实时转写');this.flush();
        }else if(value.type==='transcript')transcript(value);
        else if(value.type==='complete'){
          if(!this.stopSent)throw new Error('unexpected completion');
          this.finish(true,'转写已保存');
        }else if(value.type==='error'||value.type==='unavailable')
          this.finish(false,value.message||'转写连接中断，录音继续保存');
      }catch{this.finish(false,'转写连接异常，录音继续保存')}
    };
    socket.onerror=()=>this.finish(false,'转写连接中断，录音继续保存');
    socket.onclose=()=>this.finish(false,'转写连接中断，录音继续保存');
  }
  push(bytes){
    if(this.done||this.stopping)return;
    this.queue.push(bytes);this.bytes+=bytes.byteLength;
    if(this.bytes>32000){this.finish(false,'转写连接中断，录音继续保存');return}
    this.flush();
  }
  flush(){
    if(this.done||!this.ready||this.socket.readyState!==1)return;
    try{
      if(this.socket.bufferedAmount+this.bytes>64000)throw new Error('backpressure');
      for(const bytes of this.queue)this.socket.send(bytes);
      this.queue=[];this.bytes=0;
      if(this.stopping&&!this.stopSent){
        this.socket.send('stop');this.stopSent=true;
      }
    }catch{this.finish(false,'转写连接中断，录音继续保存')}
  }
  stop(){
    if(!this.done&&!this.stopping){
      this.stopping=true;clearTimeout(this.timer);
      this.timer=setTimeout(()=>this.finish(false,'转写尾句未确认，录音已保存'),18000);
      this.flush();
    }
    return this.completion;
  }
  finish(ok,message){
    if(this.done)return;
    this.done=true;clearTimeout(this.timer);this.queue=[];this.bytes=0;
    this.status(message);this.resolve(ok);this.socket.close();
  }
  close(){this.finish(false,'转写连接中断，录音继续保存')}
}
