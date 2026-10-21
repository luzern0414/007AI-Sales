/** Stateful windowed-sinc low-pass conversion; called outside the audio thread. */
export class Resampler {
  constructor(inputRate, outputRate = 16000) {
    this.inputRate = inputRate;
    this.outputRate = outputRate;
    this.step = inputRate / outputRate;
    this.half = 32;
    this.cutoff = Math.min(0.47, (0.47 * outputRate) / inputRate);
    this.buffer = [];
    this.base = 0;
    this.total = 0;
    this.count = 0;
  }
  push(input) {
    for (const x of input) this.buffer.push(x);
    this.total += input.length;
    return this.produce(false);
  }
  finish() {
    return this.produce(true);
  }
  produce(final) {
    const output = [];
    const limit = Math.floor((this.total * this.outputRate) / this.inputRate);
    while (this.count < limit) {
      const position = this.count * this.step,
        center = Math.floor(position);
      if (!final && center + this.half >= this.total) break;
      let value = 0,
        weight = 0;
      for (
        let index = center - this.half + 1;
        index <= center + this.half;
        index++
      ) {
        const distance = index - position,
          window = 0.5 + 0.5 * Math.cos((Math.PI * distance) / this.half);
        const coefficient =
          (distance === 0
            ? 2 * this.cutoff
            : Math.sin(2 * Math.PI * this.cutoff * distance) /
              (Math.PI * distance)) * window;
        const sample =
          index < 0 || index >= this.total ? 0 : this.buffer[index - this.base];
        value += sample * coefficient;
        weight += coefficient;
      }
      output.push(Math.max(-1, Math.min(1, value / weight)));
      this.count++;
    }
    const discard = Math.max(
      0,
      Math.floor(this.count * this.step) - this.half - 1 - this.base,
    );
    if (discard) {
      this.buffer.splice(0, discard);
      this.base += discard;
    }
    return output;
  }
}
