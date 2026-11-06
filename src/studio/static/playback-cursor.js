/* Incremental playhead lookup: only newly-started events and active voices per tick. */
class PlaybackCursor {
  constructor(events, measures) { this.events=events;this.measures=measures;this.reset(); }
  reset(){this.index=0;this.last=-Infinity;this.active=new Set();}
  at(time){
    if(time<this.last)this.reset();
    this.last=time;
    for(const event of this.active)if(event.time+event.duration<=time)this.active.delete(event);
    while(this.index<this.events.length && this.events[this.index].time<=time){
      const event=this.events[this.index++];if(event.time+event.duration>time)this.active.add(event);
    }
    let lo=0,hi=this.measures.length;
    while(lo<hi){const mid=(lo+hi)>>>1;if(this.measures[mid].time<=time)lo=mid+1;else hi=mid;}
    return {ids:new Set([...this.active].map(e=>e.id)),measure:this.measures[lo-1]};
  }
}
if(typeof module!=='undefined')module.exports=PlaybackCursor;
