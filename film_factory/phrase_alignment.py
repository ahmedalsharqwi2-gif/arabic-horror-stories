"""Measured phrase intervals for whole-phrase captions; no active-word claims."""
import math

def phrase_intervals(events,words,duration,width=5):
    from film_factory.render import norm
    if len(events)!=len(words):raise RuntimeError('Phrase aligner must retain every transcript token')
    for event,word in zip(events,words):
        if norm(event['text'])!=norm(word):raise RuntimeError('Phrase aligner changed the narration')
        if not all(math.isfinite(float(event[k])) for k in ('start','end')):raise RuntimeError('Non-finite speech interval')
        if event['start']<0 or event['end']<event['start'] or event['end']>duration+.1:raise RuntimeError('Speech interval outside recording')
    groups=[];previous=0.
    for lo in range(0,len(words),width):
        chunk=events[lo:lo+width];valid=[x for x in chunk if x['end']>x['start']]
        if not valid:raise RuntimeError('No measured speech in caption phrase')
        start=min(x['start'] for x in valid);end=max(x['end'] for x in valid)
        if end-start<.10 or end-start>12 or start<previous-.10:raise RuntimeError('Missing or overlapping spoken phrase')
        groups.append({'text':' '.join(words[lo:lo+width]),'start':start,'end':end,'measured_phrase':True});previous=end
    return groups

def force_phrase_alignment(wav,words,duration):
    import stable_whisper
    import torch
    torch.set_num_threads(2)
    model=stable_whisper.load_faster_whisper('medium',device='cpu',compute_type='int8')
    result=model.align(str(wav),' '.join(words),language='ar',failure_threshold=0.0,max_word_dur=3.0,fast_mode=False)
    if result is None:raise RuntimeError('No waveform phrase alignment returned')
    events=[{'text':w.word.strip(),'start':float(w.start),'end':float(w.end)} for s in result.segments for w in (s.words or [])]
    groups=phrase_intervals(events,words,duration)
    return events,groups
