# name=JC Records Fire 0.2 Beta
# supportedDevices=FL STUDIO FIRE
# author=JC Records / Codex; see THIRD_PARTY.md
# GPL-3.0-or-later
"""Standalone Akai Fire controller. Requires FL Studio MIDI scripting API 45+."""
import colorsys
import heapq
import json
import math
import os
import random
import time
import traceback
import channels
import device
import general
import midi
import mixer
import patterns
import plugins
import transport
import ui
import rusty_core
from rusty_core import *
try:
    import screen
except ImportError:
    screen = None

# FL executes the device entry point as a string, without __file__.
# Imported support modules retain their real source path.
HOME = os.path.dirname(os.path.abspath(rusty_core.__file__))

class Fire:
    def __init__(self):
        self.mode = 'STEP'
        self.shift = self.alt = False
        self.root, self.scale, self.chord_kind = 48, 'Minor', 0
        self.page = self.channel_bank = self.pitch_bank = self.mix_bank = 0
        self.knob_mode, self.param_page, self.fx_slot = 'USER1', 0, 0
        self.arp, self.latch = False, False
        self.arp_rate, self.arp_order, self.arp_octaves, self.arp_gate = 3, 0, 1, 0.6
        self.arp_index, self.arp_clock = 0, None
        self.held, self.latched = {}, set()
        self.voices, self.queue, self.serial = {}, [], 0
        self.seq_enabled, self.seq_tick = False, None
        self.sequences, self.sequence_key = {}, None
        self.copy_step = None
        self.last_action = time.monotonic()
        self.last_frame = self.last_scan = 0
        self.sleeping = False
        self.last_colors, self.last_text = None, None
        self.message, self.message_until = '', 0
        self.param_signature, self.param_names, self.param_order = None, [], []
        self.param_target = None
        self.scan_names, self.scan_cursor = [], 0
        self.last_context = None
        self.last_beats = None
        self.last_error = None
        self.screen_ok = False
        self.config = {'sleep_seconds': 90, 'brightness': 0.55, 'frame_rate': 15,
                       'velocity': 100, 'parameter_profiles': {}}
        path = os.path.join(HOME, 'settings.json')
        if os.path.isfile(path):
            with open(path, encoding='utf-8-sig') as f:
                self.config.update(json.load(f))

    def selected(self):
        return channels.channelNumber()

    def global_channel(self):
        c = self.selected()
        return channels.getChannelIndex(c) if c >= 0 else -1

    def sequence(self):
        key = (patterns.patternNumber(), self.global_channel())
        if key not in self.sequences:
            self.sequences[key] = Sequence()
        self.sequence_key = key
        return self.sequences[key]

    def notify(self, message):
        self.message, self.message_until = message, time.monotonic()+2.5
        ui.setHintMsg('JC Records: '+message)

    def init(self):
        if general.getVersion() < 33:
            self.notify('Requires scripting API 45+')
        if screen:
            try:
                screen.init(128,64,20,18,0xFFFFFF,0)
                header = int.from_bytes(bytes((0xF0,0x47,0x7F,0x43,0x0E)), 'little')
                screen.setup(header, 3600, 3600, 5, 2, 4000)
                self.screen_ok = True
            except Exception as exc:
                print('JC Records OLED unavailable:',exc)
        device.setHasMeters()
        print('JC Records Fire 0.2 initialized | API',general.getVersion(),'| output',device.isAssigned())
        self.notify('JC Records Fire | Beta 0.2')
        self.render(time.monotonic())

    def voice_on(self, owner, channel, notes, velocity):
        self.voice_off(owner)
        if channel < 0:
            return
        notes = tuple(n for n in notes if 0 <= n <= 127)
        # Reference counted by ownership so overlapping chords release correctly.
        existing = {(ch,n) for ch,ns in self.voices.values() for n in ns}
        self.voices[owner] = (channel, notes)
        for n in notes:
            if (channel,n) not in existing:
                channels.midiNoteOn(channel,n,velocity)

    def voice_off(self, owner):
        value = self.voices.pop(owner,None)
        if value:
            channel,notes = value
            remaining = {(ch,n) for ch,ns in self.voices.values() for n in ns}
            for n in notes:
                if (channel,n) not in remaining:
                    channels.midiNoteOn(channel,n,0)

    def panic(self):
        self.queue.clear()
        for owner in list(self.voices):
            self.voice_off(owner)
        self.held.clear()
        self.latched.clear()
        self.arp_clock = self.seq_tick = None
        self.arp_index = 0

    def schedule(self, start, duration, ch, notes, velocity):
        self.serial += 1
        owner = ('timed',self.serial)
        heapq.heappush(self.queue,(start,self.serial,1,owner,ch,notes,velocity))
        heapq.heappush(self.queue,(start+duration,self.serial,0,owner,ch,notes,velocity))

    def process_queue(self, now):
        while self.queue and self.queue[0][0] <= now:
            when,serial,on,owner,ch,notes,vel = heapq.heappop(self.queue)
            if on:
                # Ignore a note whose release is already due after a UI stall.
                if any(q[3] == owner and q[2] == 0 and q[0] <= now for q in self.queue):
                    continue
                self.voice_on(owner,ch,notes,vel)
            else:
                self.voice_off(owner)

    def target(self):
        if self.knob_mode == 'USER2':
            c = self.selected()
            track = mixer.trackNumber() if self.mode == 'MIXER' else (channels.getTargetFxTrack(c) if c >= 0 else 0)
            return track,self.fx_slot
        return self.selected(),-1

    def scan_parameters(self, now, force=False):
        if now-self.last_scan < 0.5 and not force and self.scan_cursor == 0:
            return
        self.last_scan = now
        target = self.target()
        index,slot = target
        valid = index >= 0 and plugins.isValid(index,slot)
        signature = (target,plugins.getPluginName(index,slot),plugins.getParamCount(index,slot)) if valid else (target,'No exposed plugin',0)
        if signature != self.param_signature or force:
            self.param_signature, self.param_target = signature,target
            self.scan_names, self.scan_cursor = [],0
            self.param_names, self.param_order = [],[]
            self.param_page = 0
        count = signature[2]
        if len(self.scan_names) < count:
            end = min(count, self.scan_cursor+64)
            for p in range(self.scan_cursor,end):
                self.scan_names.append(plugins.getParamName(p,index,slot))
            self.scan_cursor = end
            if end == count:
                self.param_names = self.scan_names[:]
                profiles = self.config['parameter_profiles']
                priority = profiles.get(signature[1], FX_PRIORITY if slot >= 0 else SYNTH_PRIORITY)
                self.param_order = parameter_order(self.param_names,priority)
                self.scan_cursor = 0

    def safe(self):
        return not hasattr(general,'safeToEdit') or general.safeToEdit()

    def change_mode(self, mode):
        self.panic()
        self.mode, self.page = mode,0
        self.notify(mode)

    def pad_notes(self, pad):
        row,col = divmod(pad,16)
        degree = (3-row)*5+col
        return chord(degree,self.root,self.scale,self.chord_kind)

    def pad(self, pad, down, velocity):
        if not down:
            previous = self.held.pop(pad,None)
            if previous and previous[0] == 'step' and not previous[4]:
                _,c,s,pat,_ = previous
                if pat == patterns.patternNumber() and self.safe():
                    channels.setGridBit(c,s,1-channels.getGridBit(c,s))
            self.voice_off(('pad',pad))
            if not self.held and not self.latch and self.arp:
                self.queue.clear()
                for owner in list(self.voices):
                    self.voice_off(owner)
            return
        if self.mode == 'STEP':
            row,col = divmod(pad,16)
            c,s = self.channel_bank+row,self.page*16+col
            if c >= channels.channelCount():
                return
            if c != self.selected():
                self.panic()
                channels.selectOneChannel(c)
                self.last_context = (self.global_channel(),patterns.patternNumber(),bool(transport.isPlaying()))
            self.held[pad] = ['step',c,s,patterns.patternNumber(),False]
            if self.shift:
                channels.setGridBit(c,s,1)
                channels.setStepParameterByIndex(c,patterns.patternNumber(),s,midi.pVelocity,127)
                self.held[pad][4] = True
        elif self.mode == 'MELODY':
            row,col = divmod(pad,16)
            step = self.page*16+col
            self.held[pad] = ('melody',step)
            seq = self.sequence()
            if self.alt and self.copy_step is not None:
                seq.steps[step] = json.loads(json.dumps(self.copy_step))
            elif self.shift:
                self.copy_step = json.loads(json.dumps(seq.steps[step]))
                self.notify('Copied step '+str(step+1))
            else:
                seq.toggle(step,chord(self.pitch_bank+3-row,self.root,self.scale,self.chord_kind))
        elif self.mode in ('NOTE','DRUM'):
            notes = self.pad_notes(pad) if self.mode == 'NOTE' else (36+pad,)
            if self.mode == 'DRUM':
                # 16 pads per visible row, MIDI 36..99; configurable by octave keys.
                notes = (clamp(self.root-12+pad,0,127),)
                c = self.selected()
                if c >= 0 and plugins.isValid(c) and plugins.getPluginName(c) == 'FPC':
                    count = plugins.getPadInfo(c,-1,0,0)
                    if pad < count:
                        notes = (plugins.getPadInfo(c,-1,1,pad),)
                    else:
                        return
            ch = self.global_channel()
            self.held[pad] = ('notes',ch,notes)
            if self.arp and self.mode == 'NOTE':
                if self.latch:
                    active = [v for p,v in self.held.items() if p != pad and v[0] == 'notes']
                    if not active:
                        self.latched.clear()
                    self.latched.update(notes)
            else:
                self.voice_on(('pad',pad),ch,notes,int(self.config['velocity']))
        elif self.mode == 'MIXER':
            row,col = divmod(pad,16)
            track = 1+self.mix_bank+row
            if track >= mixer.trackCount()-1:
                return
            mixer.setTrackNumber(track)
            if self.shift:
                mixer.muteTrack(track)
            elif self.alt:
                mixer.soloTrack(track)
            else:
                mixer.setTrackVolume(track,col/15)
                self.notify(mixer.getTrackName(track)+' '+str(round(mixer.getTrackVolume(track,1),1))+' dB')

    def knob(self, knob, delta):
        if not delta:
            return
        held_steps = [v for v in self.held.values() if v[0] == 'step']
        if self.mode == 'STEP' and held_steps:
            params = (midi.pVelocity,midi.pPan,midi.pPitch,midi.pModX)
            val = 0
            for v in held_steps:
                _,c,s,pat,_ = v
                if pat != patterns.patternNumber():
                    continue
                v[4] = True
                channels.setGridBit(c,s,1)
                old = channels.getCurrentStepParam(c,s,params[knob])
                val = clamp(old+delta,0,127)
                channels.setStepParameterByIndex(c,pat,s,params[knob],val)
            self.notify(('Velocity','Pan','Pitch','Mod X')[knob]+' '+str(val))
            return
        if self.mode == 'MELODY' and self.held:
            for s in {v[1] for v in self.held.values() if v[0] == 'melody'}:
                step = self.sequence().steps[s]
                key = ('velocity','gate','probability','ratchets')[knob]
                lo,hi,scale = ((1,127,1),(0.05,0.95,0.01),(0,1,0.01),(1,4,1))[knob]
                step[key] = clamp(step[key]+delta*scale,lo,hi)
                self.notify(key+' '+str(round(step[key],2)))
            return
        if self.shift and self.mode == 'NOTE':
            self.queue.clear()
            for owner in list(self.voices):
                if owner[0] == 'timed':
                    self.voice_off(owner)
            self.arp_clock = None
            if knob == 0:
                self.arp_rate = clamp(self.arp_rate+delta,0,len(RATES)-1)
            elif knob == 1:
                self.arp_gate = clamp(self.arp_gate+delta*0.02,0.1,0.95)
            elif knob == 2:
                self.arp_octaves = clamp(self.arp_octaves+delta,1,4)
            else:
                self.arp_order = (self.arp_order+delta)%4
            self.notify('ARP '+str(RATES[self.arp_rate])+'/beat '+ARP_ORDERS[self.arp_order]+' x'+str(self.arp_octaves))
            return
        if self.mode == 'MIXER' and self.knob_mode == 'MIXER':
            track = 1+self.mix_bank+knob
            if track < mixer.trackCount()-1:
                if self.shift:
                    mixer.setTrackPan(track,clamp(mixer.getTrackPan(track)+delta/100,-1,1))
                else:
                    mixer.setTrackVolume(track,clamp(mixer.getTrackVolume(track)+delta/(1000 if self.alt else 100),0,1))
            return
        self.scan_parameters(time.monotonic(), self.target() != self.param_target)
        offset = self.param_page*4+knob
        if offset < len(self.param_order):
            param = self.param_order[offset]
            index,slot = self.param_target
            value = clamp(plugins.getParamValue(param,index,slot)+delta/(1000 if self.shift else 100),0,1)
            plugins.setParamValue(value,param,index,slot)
            self.notify(self.param_names[param]+' '+str(round(value*100,1))+'%')
        elif self.knob_mode == 'USER1' and self.selected() >= 0 and not plugins.isValid(self.selected()):
            c = self.selected()
            if knob == 0:
                channels.setChannelVolume(c,clamp(channels.getChannelVolume(c)+delta/100,0,1))
            elif knob == 1:
                channels.setChannelPan(c,clamp(channels.getChannelPan(c)+delta/100,-1,1))
            elif knob == 2:
                channels.setChannelPitch(c,clamp(channels.getChannelPitch(c)+delta/100,-1,1))
            else:
                channels.setTargetFxTrack(c,clamp(channels.getTargetFxTrack(c)+delta,0,mixer.trackCount()-2))
            self.notify(('Channel volume','Channel pan','Channel pitch','Mixer routing')[knob])
        else:
            self.notify('No parameter / still scanning')

    def dump_parameters(self):
        folder = os.path.join(HOME,'Diagnostics')
        os.makedirs(folder,exist_ok=True)
        path = os.path.join(folder,'parameters-'+str(time.time_ns())+'.json')
        data = {'plugin': self.param_signature, 'parameters': list(enumerate(self.param_names)), 'knob_order': self.param_order}
        with open(path,'w',encoding='utf-8') as f:
            json.dump(data,f,indent=2)
        self.notify('Parameter report saved')

    def save(self):
        folder = os.path.join(HOME,'Sessions')
        os.makedirs(folder,exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns())[-6:]
        path = os.path.join(folder,'Rusty-'+stamp+'.json')
        data = {'version':1,'sequences': [{'pattern':p,'channel':c,'data':seq.to_dict()} for (p,c),seq in self.sequences.items()]}
        with open(path,'w',encoding='utf-8') as f:
            json.dump(data,f,indent=2)
        self.notify('Session saved')
        print('JC Records session:',path)

    def load(self):
        folder = os.path.join(HOME,'Sessions')
        files = sorted(f for f in os.listdir(folder) if f.endswith('.json')) if os.path.isdir(folder) else []
        if not files:
            self.notify('No saved session')
            return
        with open(os.path.join(folder,files[-1]),encoding='utf-8') as f:
            data = json.load(f)
        loaded = {(int(x['pattern']),int(x['channel'])):Sequence.from_dict(x['data']) for x in data['sequences']}
        self.panic()
        self.seq_enabled = False
        self.sequences = loaded
        self.notify('Loaded latest | SEQ OFF')

    def export(self):
        folder = os.path.join(HOME,'Exports')
        os.makedirs(folder,exist_ok=True)
        p,c = patterns.patternNumber(),self.global_channel()
        stamp = time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns())[-6:]
        path = os.path.join(folder,'Rusty-P%d-C%d-%s.mid'%(p,c,stamp))
        with open(path,'wb') as f:
            f.write(midi_bytes(self.sequence(),mixer.getCurrentTempo()))
        self.notify('MIDI saved in Exports')
        print('JC Records MIDI:',path)

    def event(self, event):
        status = event.status & 0xF0
        if status not in (0x80,0x90,0xB0):
            return
        key,value = event.data1,event.data2
        if not (16 <= key <= 19 or 25 <= key <= 53 or 54 <= key <= 118):
            return
        event.handled = True
        self.last_action = time.monotonic()
        self.sleeping = False
        down = status != 0x80 and value > 0
        if key == 48:
            self.shift = down
            return
        if key == 49:
            self.alt = down
            return
        if 54 <= key <= 117 and status != 0xB0:
            if not down or self.safe():
                self.pad(key-54,down,value)
            return
        if key == 52 and down:
            self.panic()
            transport.stop()
            return
        if not self.safe():
            return
        if status == 0xB0 and 16 <= key <= 19:
            self.knob(key-16,relative(value))
            return
        if status == 0xB0 and key == 118:
            delta = relative(value)
            self.panic()
            if self.shift:
                p = clamp(patterns.patternNumber()+delta,1,999)
                patterns.jumpToPattern(p)
            elif channels.channelCount():
                channels.selectOneChannel(clamp(self.selected()+delta,0,channels.channelCount()-1))
            return
        if not down:
            return
        if key == 44:
            self.change_mode('MELODY' if self.shift else 'STEP')
        elif key == 45:
            if self.shift:
                self.panic()
                self.arp = not self.arp
                self.notify('ARP '+('ON' if self.arp else 'OFF'))
            else:
                self.change_mode('NOTE')
        elif key == 46:
            self.change_mode('DRUM')
        elif key == 47:
            self.change_mode('MIXER')
        elif key == 26:
            self.knob_mode = 'USER2' if self.knob_mode == 'USER1' else 'USER1'
            self.scan_parameters(time.monotonic(),True)
            self.notify(self.knob_mode+' knobs')
        elif key in (34,35):
            delta = -1 if key == 34 else 1
            if self.alt and self.mode in ('STEP','MELODY'):
                self.page = clamp(self.page+delta,0,3)
            elif self.shift and self.knob_mode == 'USER2':
                self.fx_slot = clamp(self.fx_slot+delta,0,9)
                self.scan_parameters(time.monotonic(),True)
            else:
                self.param_page = clamp(self.param_page+delta,0,max(0,(len(self.param_order)-1)//4))
        elif key in (31,32):
            delta = 1 if key == 31 else -1
            self.panic()
            if self.mode == 'STEP':
                self.channel_bank = clamp(self.channel_bank+delta*4,0,max(0,channels.channelCount()-1))
            elif self.mode == 'MIXER':
                self.mix_bank = clamp(self.mix_bank+delta*4,0,max(0,mixer.trackCount()-6))
            elif self.mode == 'MELODY':
                self.pitch_bank = clamp(self.pitch_bank+delta*4,-21,42)
            else:
                self.root = clamp(self.root+delta*(1 if self.shift else 12),0,96)
        elif 36 <= key <= 39:
            if self.mode in ('STEP','MELODY'):
                self.page = key-36
            elif self.mode == 'NOTE':
                self.panic()
                if key == 36:
                    self.chord_kind = (self.chord_kind+1)%4
                elif key == 37:
                    names = list(SCALES)
                    self.scale = names[(names.index(self.scale)+1)%len(names)]
                elif key == 38:
                    self.latch = not self.latch
                else:
                    self.arp_order = (self.arp_order+1)%4
            elif self.mode == 'MIXER':
                t = 1+self.mix_bank+key-36
                if t < mixer.trackCount()-1:
                    mixer.muteTrack(t)
        elif key == 25:
            if self.shift and self.alt:
                self.dump_parameters()
            elif self.alt and self.mode == 'MELODY':
                self.panic()
                self.seq_enabled = not self.seq_enabled
                if self.seq_enabled and hasattr(patterns,'setPatternLength'):
                    pat = patterns.patternNumber()
                    if patterns.getPatternLength(pat) < self.sequence().length//4:
                        patterns.setPatternLength(pat,self.sequence().length//4)
                self.notify('Melody playback '+('ON' if self.seq_enabled else 'OFF'))
            elif self.shift:
                self.scan_parameters(time.monotonic(),True)
                self.notify('Rescanning parameters')
            elif self.selected() >= 0:
                channels.showEditor(self.selected())
        elif 40 <= key <= 43:
            offset = key-40
            if self.mode == 'MIXER':
                track = 1+self.mix_bank+offset
                if track < mixer.trackCount()-1:
                    mixer.setTrackNumber(track)
            elif self.mode == 'STEP':
                c = self.channel_bank+offset
                if c < channels.channelCount():
                    if self.shift:
                        channels.muteChannel(c)
                    else:
                        self.panic()
                        channels.selectOneChannel(c)
        elif key == 33:
            if self.shift and self.alt:
                self.load()
            elif self.shift:
                self.save()
            elif self.alt:
                self.export()
            else:
                ui.showWindow(midi.widPianoRoll if self.mode == 'MELODY' else midi.widBrowser)
        elif key == 50:
            transport.setLoopMode()
        elif key == 51:
            transport.start()
        elif key == 53:
            transport.record()

    def idle(self):
        now = time.monotonic()
        context = (self.global_channel(),patterns.patternNumber(),bool(transport.isPlaying()))
        if self.last_context is not None and context != self.last_context:
            self.panic()
        self.last_context = context
        ch,pat,playing = context
        if not self.safe():
            self.panic()
            return
        bpm = max(10,mixer.getCurrentTempo())
        beat_seconds = 60/bpm
        # Host ticks anchor playback; stopped arp uses the monotonic clock.
        beats = transport.getSongPos(midi.SONGLENGTH_ABSTICKS)/max(1,general.getRecPPQ()) if playing else now/beat_seconds
        if playing and self.last_beats is not None and (beats < self.last_beats or beats-self.last_beats > 1):
            self.panic()
        self.last_beats = beats if playing else None
        if self.seq_enabled and playing and ch >= 0:
            tick = int(beats*4)
            if tick != self.seq_tick:
                self.seq_tick = tick
                seq = self.sequence()
                for offset,gate,note,vel in seq.events(tick):
                    delay = max(0,(offset-(beats*4-tick))*beat_seconds/4)
                    self.schedule(now+delay,gate*beat_seconds/4,ch,(note,),vel)
        notes = set(self.latched) if self.latch else set()
        for v in self.held.values():
            if v[0] == 'notes':
                notes.update(v[2])
        if self.arp and self.mode == 'NOTE' and notes and ch >= 0:
            tick = int(beats*RATES[self.arp_rate])
            if tick != self.arp_clock:
                self.arp_clock = tick
                pool = arp_notes(notes,self.arp_octaves,ARP_ORDERS[self.arp_order])
                if pool:
                    note = random.choice(pool) if self.arp_order == 3 else pool[self.arp_index%len(pool)]
                    self.arp_index += 1
                    self.schedule(now,beat_seconds/RATES[self.arp_rate]*self.arp_gate,ch,(note,),self.config['velocity'])
        self.process_queue(now)
        self.scan_parameters(now)
        self.sleeping = (not playing and not self.held and not self.latched and
                         now-self.last_action > max(10,self.config['sleep_seconds']))
        if now-self.last_frame >= 1/clamp(self.config['frame_rate'],5,30):
            self.last_frame = now
            self.render(now)

    def row_color(self, row, intensity=1.0):
        # Top to bottom: cyan, purple, amber, green; Fire RGB is 7-bit.
        palette = ((0,100,110),(95,12,120),(120,65,0),(12,110,30))
        return tuple(int(c*intensity) for c in palette[row % 4])

    def render(self, now):
        dim = (2,3,5)
        colors = [self.row_color(pad//16,0.08) for pad in range(64)]
        if self.sleeping:
            colors = animation(now-self.last_action,self.config['brightness'])
        elif self.mode == 'STEP':
            tick = mixer.getSongStepPos()%self.step_length() if transport.isPlaying() else -1
            for pad in range(64):
                row,col = divmod(pad,16)
                c,s = self.channel_bank+row,self.page*16+col
                if c < channels.channelCount():
                    colors[pad] = self.row_color(row,1.0 if channels.getGridBit(c,s) else (0.16 if col%4 == 0 else 0.07))
                    if s == tick:
                        colors[pad] = (90,90,90)
        elif self.mode == 'MELODY':
            seq = self.sequence()
            for pad in range(64):
                row,col = divmod(pad,16)
                n = scale_note(self.pitch_bank+3-row,self.root,self.scale)
                active = n in seq.steps[self.page*16+col]['notes']
                colors[pad] = self.row_color(row,1.0 if active else 0.08)
                if self.seq_enabled and transport.isPlaying() and self.seq_tick is not None and self.seq_tick%seq.length == self.page*16+col:
                    colors[pad] = (100,100,100) if active else (10,15,20)
        elif self.mode in ('NOTE','DRUM'):
            for pad in range(64):
                if self.mode == 'NOTE':
                    root = self.pad_notes(pad)
                    colors[pad] = self.row_color(pad//16,0.85 if root and root[0]%12 == self.root%12 else 0.35)
                else:
                    colors[pad] = self.row_color(pad//16,0.6)
                if pad in self.held:
                    colors[pad] = (100,100,100)
        elif self.mode == 'MIXER':
            for row in range(4):
                track = 1+self.mix_bank+row
                if track >= mixer.trackCount()-1:
                    continue
                value = mixer.getTrackVolume(track)
                level = round(value*15)
                peak = clamp(round(mixer.getTrackPeaks(track,2)*15),0,15)
                muted = mixer.isTrackMuted(track)
                for col in range(16):
                    colors[row*16+col] = ((35,3,3) if muted else self.row_color(row)) if col <= level and value > 0 else self.row_color(row,0.07)
                    if col == peak and peak > 0:
                        colors[row*16+col] = (100,60,8)
        if not self.sleeping:
            colors = self.decorate_colors(colors,now)
            brightness = clamp(float(self.config['brightness']),0.05,1)
            colors = [tuple(int(v*brightness) for v in color) for color in colors]
        if colors != self.last_colors and device.isAssigned():
            payload = bytes(v for pad,color in enumerate(colors) for v in (pad,)+color)
            device.midiOutSysex(bytes((0xF0,0x47,0x7F,0x43,0x65,len(payload)>>7,len(payload)&127))+payload+b'\xf7')
            self.last_colors = colors
        self.send_leds()
        if self.sleeping:
            lines = ('JC Records','FIRE AFTER DARK','Touch to wake')
        else:
            title = self.mode+' '+('USER2'+str(self.fx_slot+1) if self.knob_mode == 'USER2' else 'USER1')+' P'+str(self.param_page+1)
            if self.mode in ('STEP','MELODY'):
                title = self.mode+' '+str(self.page*16+1)+'-'+str(self.page*16+16)
            if self.mode == 'NOTE':
                title = self.scale+' '+CHORDS[self.chord_kind]+(' ARP' if self.arp else '')
            entries = self.param_order[self.param_page*4:self.param_page*4+4]
            labels = [self.param_names[p][:9] for p in entries]
            while len(labels) < 4:
                labels.append('--')
            lines = (title,labels[0]+' / '+labels[1],labels[2]+' / '+labels[3])
            if self.mode == 'MIXER' and self.knob_mode == 'MIXER':
                names = [mixer.getTrackName(1+self.mix_bank+i)[:9] if 1+self.mix_bank+i < mixer.trackCount()-1 else '--' for i in range(4)]
                lines = ('MIXER | 4 FADERS', names[0]+' / '+names[1], names[2]+' / '+names[3])
            if now < self.message_until:
                lines = (title,self.message[:21],self.message[21:42])
        lines = self.display_lines(lines)
        if self.screen_ok and lines != self.last_text:
            for row,text in enumerate(lines):
                screen.displayText(1,0,row,text,False)
            screen.update()
            self.last_text = lines

    def project_load(self, status):
        if status == 0:
            self.panic()
            if self.sequences:
                self.save()
            self.sequences.clear()
            self.seq_enabled = False
            self.last_context = None
            self.param_signature = None

    def deinit(self):
        self.panic()
        if self.sequences:
            self.save()
        if device.isAssigned():
            payload = bytes(v for pad in range(64) for v in (pad,0,0,0))
            device.midiOutSysex(bytes((0xF0,0x47,0x7F,0x43,0x65,2,0))+payload+b'\xf7')
        if self.screen_ok:
            screen.deInit()

from jc_controls import JCControls

class Fire(JCControls, Fire):
    pass

FireController = Fire()

def guarded(method,*args):
    try:
        method(*args)
    except Exception as exc:
        try:
            FireController.panic()
        except Exception:
            pass
        error = str(exc)
        if error != FireController.last_error:
            FireController.last_error = error
            traceback.print_exc()
            ui.setHintMsg('JC Records error: '+error)

def OnInit():
    guarded(FireController.init)

def OnMidiMsg(event):
    guarded(FireController.event,event)

def OnIdle():
    guarded(FireController.idle)

def OnDeInit():
    guarded(FireController.deinit)

def OnProjectLoad(status):
    guarded(FireController.project_load,status)

def OnRefresh(flags):
    FireController.last_frame = 0

def OnDirtyMixerTrack(track):
    FireController.last_frame = 0


def OnDirtyChannel(channel, flags):
    # These are event codes, not bit masks. A changed channel identity can
    # invalidate saved index destinations; stop and reset the internal bank.
    if flags in (getattr(midi,'CE_Delete',1),getattr(midi,'CE_Replace',2)):
        FireController.panic()
        FireController.seq_enabled = False
        FireController.param_signature = None
        if FireController.sequences:
            guarded(FireController.save)
            FireController.sequences.clear()
        FireController.notify('Channel changed | melody bank reset')
