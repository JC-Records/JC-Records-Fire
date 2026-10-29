"""Exact-name synth pages. Names verified in FL Studio 2026; no fuzzy routing."""
from rusty_core import normalize

def synth_layout(plugin,names):
    key=normalize(plugin)
    pages=[]
    if key=='harmor':
        for part in ('A','B'):
            prefix=part+' - '
            def h(items):return [prefix+x for x in items]
            pages.extend([
                (part+' FILTER',h(['Filter 1 frequency','Filter 1 resonance / noise amount','Filter 1 envelope amount','Filter 1 width'])),
                (part+' AMP ENV',h(['Volume - Attack time scale','Volume - Decay time scale','Volume - Sustain level offset','Volume - Release time scale'])),
                (part+' TIME',h(['Pluck decay length','Time blur attack','Time blur decay','Blur mix'])),
                (part+' PHASER',h(['Phaser mix','Phaser width','Phaser offset','Phaser offset motion speed'])),
                (part+' FILTER ENV',h(['Filter 1 frequency - Attack time scale','Filter 1 frequency - Decay time scale','Filter 1 frequency - Sustain level offset','Filter 1 frequency - Release time scale']))])
    elif key=='flex':
        pages=[('FILTER',['Filter cutoff','Filter resonance','Filter env amt','Post filter cutoff']),
               ('AMP ENVELOPE',['Volume envelope attack','Volume envelope decay','Volume envelope sustain','Volume envelope release']),
               ('FILTER ENV',['Filter envelope attack','Filter envelope decay','Filter envelope sustain','Filter envelope release']),
               ('DELAY',['Delay mix','Delay time','Delay feedback','Delay color']),
               ('REVERB',['Reverb mix','Reverb decay','Reverb size','Reverb mod'])]
        # FLEX names these slots after the preset macros. Verify surrounding API layout.
        if len(names)>=21 and names[0]=='Volume envelope attack' and names[18]=='Filter cutoff':
            pages.extend([('MACROS 1-4',list(range(10,14))),('MACROS 5-8',list(range(14,18)))])
    else:return None
    normalized=[normalize(n) for n in names]
    order=[];titles=[]
    for title,slots in pages:
        resolved=[]
        for slot in slots:
            if isinstance(slot,int):resolved.append(slot)
            else:
                matches=[i for i,n in enumerate(normalized) if n==normalize(slot)]
                resolved.append(matches[0] if len(matches)==1 else None)
        # Keep missing slots empty, never silently substitute an unrelated control.
        if any(p is not None for p in resolved):
            order.extend(resolved);titles.append(title)
    remaining=[i for i,n in enumerate(names) if n.strip() and i not in order]
    for start in range(0,len(remaining),4):
        group=remaining[start:start+4]
        order.extend(group+[None]*(4-len(group)));titles.append('MORE '+str(start//4+1))
    return order,titles

def short_parameter_name(name):
    value=name
    for old,new in [('A - ',''),('B - ',''),('Volume envelope ',''),('Filter envelope ',''),
                    ('Volume - ',''),('Filter 1 frequency - ','F1 '),('Filter 2 frequency - ','F2 '),
                    ('Filter 1 resonance / noise amount','F1 Resonance'),('Filter 1 frequency','F1 Freq'),
                    ('Filter 1 envelope amount','F1 Env Amt'),('Filter 1 width','F1 Width'),
                    ('Attack time scale','Attack'),('Decay time scale','Decay'),('Sustain level offset','Sustain'),
                    ('Release time scale','Release'),('Phaser offset motion speed','Phaser Speed'),
                    ('Pluck decay length','Pluck Time'),('Time blur attack','Blur Attack'),('Time blur decay','Blur Decay')]:
        value=value.replace(old,new)
    return value
