class Capture extends AudioWorkletProcessor {
  constructor(){super();this.samples=new Float32Array(2048);this.offset=0;this.pending=0;this.stopped=false;this.port.onmessage=event=>{if(event.data==='ack')this.pending--;if(event.data==='stop'){if(this.offset)this.send();this.stopped=true;this.port.postMessage({type:'stopped'})}}}
  send(){if(this.pending>=32){this.stopped=true;this.port.postMessage({type:'gap'});return}const samples=this.samples.slice(0,this.offset);this.port.postMessage({type:'samples',samples},[samples.buffer]);this.pending++;this.offset=0}
  process(inputs){if(this.stopped)return true;const channels=inputs[0];if(!channels?.length)return true;const length=channels[0].length;for(let i=0;i<length;i++){let value=0;for(const channel of channels)value+=channel[i];this.samples[this.offset++]=value/channels.length;if(this.offset===2048)this.send();if(this.stopped)break}return true}
}
registerProcessor('meeting-capture',Capture);
