"""DJ RUSTY Fire musical engine. GPL-3.0-or-later."""
import colorsys
import math
import random
import re
import struct

SCALES = {'Minor': (0,2,3,5,7,8,10), 'Major': (0,2,4,5,7,9,11),
          'Dorian': (0,2,3,5,7,9,10), 'Pentatonic': (0,3,5,7,10), 'Chromatic': tuple(range(12))}
CHORDS = ('Single', 'Triad', 'Seventh', 'Octaves')
ARP_ORDERS = ('Up', 'Down', 'UpDown', 'Random')
RATES = (1, 2, 3, 4, 6, 8)

def clamp(value, lo, hi):
    return max(lo, min(hi, value))

def relative(value):
    return value if value < 64 else value - 128

def scale_note(degree, root=48, scale='Minor'):
    intervals = SCALES[scale]
    octaves, index = divmod(degree, len(intervals))
    return root + octaves * 12 + intervals[index]

def chord(degree, root, scale, kind):
    offsets = ((0,), (0,2,4), (0,2,4,6), (0,len(SCALES[scale])))[kind]
    return tuple(n for n in (scale_note(degree+d, root, scale) for d in offsets) if 0 <= n <= 127)

def arp_notes(notes, octaves, order):
    result = sorted(set(n+12*o for o in range(octaves) for n in notes if n+12*o <= 127))
    if order == 'Down':
        result.reverse()
    elif order == 'UpDown' and len(result) > 2:
        result += result[-2:0:-1]
    return result

def normalize(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

SYNTH_PRIORITY = ('macro1','macro2','macro3','macro4','cutoff','filtercutoff','fltcutoff',
                  'resonance','filterresonance','attack','decay','sustain','release',
                  'drive','distortion','unison','detune','lfospeed','lforate','lfodepth','reverb','delay','volume')
FX_PRIORITY = ('wet','mix','drywet','cutoff','resonance','drive','threshold','ratio','attack',
               'release','feedback','time','decay','size','lowcut','highcut','gain')

def parameter_order(names, priorities=None):
    remaining = list(range(len(names)))
    chosen = []
    normalized = [normalize(n) for n in names]
    for alias in priorities or SYNTH_PRIORITY:
        alias = normalize(alias)
        exact = [i for i in remaining if normalized[i] == alias]
        matches = exact or [i for i in remaining if alias in normalized[i]]
        if matches:
            chosen.append(matches[0])
            remaining.remove(matches[0])
    return chosen + remaining

def default_step():
    return {'notes': [], 'velocity': 100, 'gate': 0.75, 'probability': 1.0, 'ratchets': 1}

class Sequence:
    def __init__(self, length=64):
        self.length = length
        self.steps = [default_step() for _ in range(length)]

    def toggle(self, step, notes):
        current = self.steps[step]['notes']
        if all(n in current for n in notes):
            self.steps[step]['notes'] = [n for n in current if n not in notes]
        else:
            self.steps[step]['notes'] = sorted(set(current + list(notes)))

    def events(self, step, rng=None):
        s = self.steps[step % self.length]
        if (rng or random).random() >= s['probability']:
            return []
        return [(r/s['ratchets'], s['gate']/s['ratchets'], n, s['velocity'])
                for r in range(s['ratchets']) for n in s['notes']]

    def to_dict(self):
        return {'length': self.length, 'steps': self.steps}

    @classmethod
    def from_dict(cls, data):
        length = int(data['length'])
        if length not in (16,32,48,64):
            raise ValueError('Invalid sequence length')
        seq = cls(length)
        while len(seq.steps) < min(64,len(data['steps'])):
            seq.steps.append(default_step())
        for i,s in enumerate(data['steps'][:64]):
            seq.steps[i] = {'notes': sorted(set(clamp(int(n),0,127) for n in s['notes'])),
                'velocity': clamp(int(s['velocity']),1,127), 'gate': clamp(float(s['gate']),0.05,0.95),
                'probability': clamp(float(s['probability']),0,1), 'ratchets': clamp(int(s['ratchets']),1,4)}
        return seq

def vlq(value):
    out = [value & 127]
    while value > 127:
        value >>= 7
        out.insert(0, (value & 127) | 128)
    return bytes(out)

def midi_bytes(sequence, bpm=120, seed=0):
    events = []
    rng = random.Random(seed)
    for step in range(sequence.length):
        for offset,gate,note,vel in sequence.events(step,rng):
            start = round((step+offset)*120)
            end = start + max(1,round(gate*120))
            events.extend(((start,1,bytes((0x90,note,vel))), (end,0,bytes((0x80,note,0)))))
    tempo = int(60000000/clamp(bpm,10,999))
    track = bytearray(b'\x00\xff\x51\x03' + tempo.to_bytes(3,'big'))
    last = 0
    for tick,_,event in sorted(events):
        track += vlq(tick-last) + event
        last = tick
    track += vlq(max(0,sequence.length*120-last)) + b'\xff\x2f\x00'
    return b'MThd' + struct.pack('>IHHH',6,0,1,480) + b'MTrk' + struct.pack('>I',len(track)) + track

FONT = {'C':('011','100','100','011'), 'E':('111','110','100','111'), 'O':('010','101','101','010'), 'D':('110','101','101','110'), 'J':('001','001','101','010'),
        'R':('110','101','110','101'), 'U':('101','101','101','111'),
        'S':('011','100','001','110'), 'T':('111','010','010','010'),
        'Y':('101','101','010','010'), ' ':('000','000','000','000')}

def animation(t, brightness=0.55):
    scene = int(t//12)%4
    rows = ['0'.join(FONT[c][row] for c in ' JC RECORDS  ') for row in range(4)]
    colors = []
    for pad in range(64):
        y,x = divmod(pad,16)
        hue = (x/20+y/10+t/8)%1
        if scene == 0:
            value = 0.2+0.8*(1+math.sin(x*0.65+t*2)*math.cos(y+t))/2
        elif scene == 1:
            value = 0.2+0.8*(1+math.sin(x/2+y+t*3))/2
        elif scene == 2:
            value = max(0.025,1-((int(t*18)-pad)%64)/14)
        else:
            value = 1 if rows[y][(x+int(t*5))%len(rows[y])] == '1' else 0.015
        colors.append(tuple(int(v*127) for v in colorsys.hsv_to_rgb(hue,0.85,value*brightness)))
    return colors
