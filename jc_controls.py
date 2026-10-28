"""JC Records Fire control expansion. GPL-3.0-or-later."""
import time
import channels, device, general, midi, mixer, patterns, playlist, plugins, transport, ui
from rusty_core import clamp, default_step, relative, scale_note, chord, SCALES, CHORDS, ARP_ORDERS, RATES

class JCControls:
    def __init__(self):
        super().__init__()
        self.knob_mode = 'CHANNEL'
        self.clip_track, self.clip_block = 1, 0
        self.clip_held = {}
        self.drum_channels = False
        self.mix_view = 'VOLUME'
        self.arp_page = False
        self.chord_mode = False
        self.note_hold = False
        self.sustained = set()
        self.knob_feedback = None
        self.config['brightness'] = 1.0

    def fx_slots(self, track):
        return [slot for slot in range(10)
                if plugins.isValid(track,slot) and plugins.getParamCount(track,slot)>0]

    def target(self):
        target=super().target()
        if self.knob_mode=='USER2':
            track,slot=target
            slots=self.fx_slots(track)
            if slots and slot not in slots:
                self.fx_slot=slots[0]
                return track,self.fx_slot
        return target

    def scan_parameters(self, now, force=False):
        if self.knob_mode=='USER2':
            target=self.target()
            if not self.fx_slots(target[0]):
                signature=(target,'Built-in mixer EQ',8)
                if force or signature!=self.param_signature:
                    self.param_page=0
                self.param_signature,self.param_target=signature,target
                self.param_names=['Bass gain','Mid gain','Treble gain','Stereo separation',
                                  'Bass frequency','Mid frequency','Treble frequency','Track volume']
                self.param_order=list(range(8))
                self.scan_names=self.param_names[:]
                self.scan_cursor=0
                self.last_scan=now
                return
        super().scan_parameters(now,force)

    def panic(self):
        for targets in getattr(self,'clip_held',{}).values():
            for track,block in targets:
                playlist.triggerLiveClip(track,block,midi.TLC_Release)
        if hasattr(self,'clip_held'):
            self.clip_held.clear()
        if hasattr(self,'sustained'): self.sustained.clear()
        super().panic()

    def sequence(self):
        seq = super().sequence()
        while len(seq.steps) < 64:
            seq.steps.append(default_step())
        return seq

    def change_mode(self, mode):
        super().change_mode(mode)
        if mode == 'MIXER':
            self.knob_mode = 'MIXER'
        elif mode == 'PERFORM':
            self.notify('CLIPS | SHIFT=mixer')
        self.param_signature = None

    def set_length(self, steps):
        steps = int(clamp(steps,16,64 if self.mode == 'MELODY' else 256))
        if self.mode == 'MELODY':
            self.sequence().length = steps
        patterns.setPatternLength(patterns.patternNumber(),steps//4)
        self.page = min(self.page,steps//16-1)
        self.notify(str(steps)+' steps | '+str(steps//16)+' bars')

    def step_length(self):
        if self.mode == 'MELODY':
            return self.sequence().length
        return max(16,int(patterns.getPatternLength(patterns.patternNumber())*4))

    def clip_ready(self):
        if not playlist.getPerformanceModeState():
            self.notify('Enable FL Performance mode')
            return False
        return True

    def clip_stop(self, track):
        if self.clip_ready() and track <= playlist.trackCount():
            playlist.triggerLiveClip(track,-1,midi.TLC_Fill)

    def event(self, event):
        status=event.status & 0xF0
        key=event.data1
        # The four encoders send note messages when touched, CC only when turned.
        # Consume touch/release without waking displays or changing any state.
        if status in (0x80,0x90) and 16<=key<=19:
            event.handled=True
            return
        down=status==0x90 and event.data2>0
        if not down or key in (48,49) or not self.safe():
            return super().event(event)
        handled=True
        if key==47:
            self.change_mode('MIXER' if self.shift else 'PERFORM')
        elif key==46 and self.shift:
            self.panic()
            self.drum_channels=not self.drum_channels
            self.change_mode('DRUM')
            self.notify('DRUM '+('Channel rack' if self.drum_channels else 'FPC / notes'))
        elif key==45 and self.alt and self.shift:
            self.arp_page=not self.arp_page
            self.notify('ARP knobs '+('ON' if self.arp_page else 'OFF'))
        elif key==45 and self.alt:
            self.change_mode('NOTE')
            self.chord_mode=True
            self.chord_kind=max(1,self.chord_kind)
            self.notify('CHORD | rows=inversions')
        elif key==45 and not self.shift:
            self.change_mode('NOTE')
            self.chord_mode=False
            self.chord_kind=0
            self.notify('NOTE | single notes')
        elif key==38 and self.alt and self.mode=='NOTE':
            enabled=not self.note_hold
            self.panic()
            self.note_hold=enabled
            if enabled: self.latch=False
            self.notify('NOTE HOLD '+('ON | tap to release' if enabled else 'OFF'))
        elif key==38 and self.mode=='NOTE':
            self.panic()
            self.note_hold=False
            self.latch=not self.latch
            self.notify('ARP latch '+('ON' if self.latch else 'OFF'))
        elif key==36 and self.mode=='NOTE' and self.chord_mode:
            self.panic()
            self.chord_kind=1+self.chord_kind%3
            self.notify('CHORD '+CHORDS[self.chord_kind])
        elif key==26:
            modes=('CHANNEL','MIXER','USER1','USER2')
            self.knob_mode=modes[(modes.index(self.knob_mode)+(-1 if self.shift else 1))%4]
            if self.alt:
                self.change_mode('MIXER')
            self.scan_parameters(time.monotonic(),True)
            self.notify(self.knob_mode+' knobs')
        elif key in (34,35):
            d=-1 if key==34 else 1
            if self.mode in ('STEP','MELODY') and not self.alt:
                if self.shift:
                    self.set_length(self.step_length()+d*16)
                else:
                    maximum=3 if self.mode=='MELODY' else 15
                    self.page=clamp(self.page+d,0,maximum)
                    if (self.page+1)*16>self.step_length():
                        self.set_length((self.page+1)*16)
                    self.notify('Steps '+str(self.page*16+1)+'-'+str(self.page*16+16))
            elif self.mode=='PERFORM':
                self.clip_block=max(0,self.clip_block+d*16)
            elif self.mode=='MIXER' and not self.alt and self.knob_mode!='USER2':
                self.mix_bank=clamp(self.mix_bank+d*4,0,max(0,mixer.trackCount()-6))
            elif self.shift and self.knob_mode=='USER2':
                slots=self.fx_slots(self.target()[0])
                if slots:
                    self.fx_slot=slots[(slots.index(self.fx_slot)+d)%len(slots)]
                self.scan_parameters(time.monotonic(),True)
            else:
                self.param_page=clamp(self.param_page+d,0,max(0,(len(self.param_order)-1)//4))
        elif key in (31,32) and self.mode=='PERFORM':
            self.clip_track=clamp(self.clip_track+(4 if key==31 else -4),1,max(1,playlist.trackCount()-3))
        elif 36<=key<=39 and self.mode in ('STEP','MELODY','DRUM'):
            c=self.channel_bank+key-36
            if c<channels.channelCount():
                if self.alt:
                    self.panic(); channels.selectOneChannel(c)
                elif self.shift:
                    channels.soloChannel(c)
                else:
                    channels.muteChannel(c)
        elif 36<=key<=39 and self.mode=='MIXER':
            t=1+self.mix_bank+key-36
            if t<mixer.trackCount()-1:
                if self.alt:
                    mixer.armTrack(t)
                elif self.shift:
                    mixer.soloTrack(t)
                else:
                    mixer.muteTrack(t)
        elif 36<=key<=39 and self.mode=='PERFORM':
            self.clip_stop(self.clip_track+key-36)
        elif 40<=key<=43 and self.mode=='MIXER':
            t=1+self.mix_bank+key-40
            if t<mixer.trackCount()-1:
                mixer.setTrackNumber(t)
        elif key==25 and self.mode=='MIXER' and self.alt and not self.shift:
            self.mix_view='PAN' if self.mix_view=='VOLUME' else 'VOLUME'
            self.notify('Mixer pads: '+self.mix_view)
        else:
            handled=False
        if handled:
            event.handled=True
            self.last_action=time.monotonic()
            self.sleeping=False
        else:
            super().event(event)

    def pad_notes(self,pad):
        if self.chord_mode and self.mode=='NOTE':
            row,col=divmod(pad,16)
            notes=list(chord(col,self.root,self.scale,max(1,self.chord_kind)))
            # Bottom row: root position; rows above: successive inversions.
            for _ in range(3-row):
                if notes: notes.append(notes.pop(0)+12)
            return tuple(n for n in notes if 0<=n<=127)
        return super().pad_notes(pad)

    def pad(self,pad,down,velocity):
        if self.mode=='NOTE' and self.note_hold:
            if down and pad in self.sustained:
                self.sustained.remove(pad)
                return super().pad(pad,False,velocity)
            if not down and pad in self.held:
                self.sustained.add(pad)
                return

        if self.mode=='PERFORM':
            if not down:
                target=self.clip_held.pop(pad,None)
                if target:
                    for track,block in target:
                        playlist.triggerLiveClip(track,block,midi.TLC_Release)
                return
            if not self.clip_ready():
                return
            row,col=divmod(pad,16)
            track,block=self.clip_track+row,self.clip_block+col
            if track>playlist.trackCount():
                return
            if self.alt:
                self.clip_stop(track)
                return
            tracks=range(self.clip_track,min(self.clip_track+4,playlist.trackCount()+1)) if self.shift else (track,)
            self.clip_held[pad]=[]
            for t in tracks:
                if playlist.getLiveBlockStatus(t,block,0)&1:
                    playlist.triggerLiveClip(t,block,midi.TLC_MuteOthers,1.0)
                    self.clip_held[pad].append((t,block))
            return
        if self.mode=='DRUM' and down:
            row,col=divmod(pad,16)
            index=(3-row)*4+(col%4)+(col//4)*16
            c=self.selected()
            if self.drum_channels:
                c=self.channel_bank+index
                if c>=channels.channelCount():
                    return
                ch=channels.getChannelIndex(c); notes=(60,)
            else:
                ch=self.global_channel()
                if c>=0 and plugins.isValid(c) and plugins.getPluginName(c)=='FPC':
                    count=plugins.getPadInfo(c,-1,0,0)
                    if index>=count:
                        return
                    notes=(plugins.getPadInfo(c,-1,1,index),)
                else:
                    notes=(clamp(self.root-12+index,0,127),)
            self.held[pad]=('notes',ch,notes)
            vel=127 if self.shift else (55 if self.alt else self.config['velocity'])
            self.voice_on(('pad',pad),ch,notes,int(vel))
            return
        if self.mode=='MIXER' and down and self.mix_view=='PAN' and not(self.shift or self.alt):
            row,col=divmod(pad,16); t=1+self.mix_bank+row
            if t<mixer.trackCount()-1:
                mixer.setTrackNumber(t)
                mixer.setTrackPan(t,0 if col in (7,8) else (col/15*2-1))
            return
        super().pad(pad,down,velocity)

    def show_knob_value(self,title,label,value):
        self.notify(label+' '+value)
        self.knob_feedback=(title,label,value)
        # Update OLED now; pad animation frame rate must not delay knob feedback.
        if self.screen_ok:
            import screen
            for row,text in enumerate(self.knob_feedback):
                screen.displayText(1,0,row,text,False)
            screen.update()
            self.last_text=self.knob_feedback

    def notify(self,message):
        self.knob_feedback=None
        super().notify(message)

    def knob(self,knob,delta):
        if not delta:return
        self.knob_feedback=None
        self._turn_knob(knob,delta)
        if self.knob_feedback is not None:return
        if self.mode in ('STEP','MELODY') and self.held:return
        if self.mode=='NOTE' and (self.shift or self.alt or self.arp_page):return
        label=None;value=None
        if self.knob_mode in ('USER1','USER2'):
            if self.knob_mode=='USER2' and self.param_signature and self.param_signature[1]=='Built-in mixer EQ':
                t=self.param_target[0];label=self.param_names[self.param_page*4+knob]
                if knob<3:
                    value=(mixer.getEqGain(t,knob,0) if self.param_page==0 else mixer.getEqFrequency(t,knob,0))
                else:value=mixer.getTrackStereoSep(t) if self.param_page==0 else mixer.getTrackVolume(t)
            elif self.param_page*4+knob<len(self.param_order):
                p=self.param_order[self.param_page*4+knob];label=self.param_names[p]
                value=plugins.getParamValue(p,*self.param_target)
        elif self.knob_mode=='CHANNEL' and self.selected()>=0:
            c=self.selected();label=('Volume','Pan','Pitch','Mixer route')[knob]
            if knob==3:
                self.show_knob_value('CHANNEL',label,str(channels.getTargetFxTrack(c)));return
            value=(channels.getChannelVolume,channels.getChannelPan,channels.getChannelPitch)[knob](c)
        elif self.knob_mode=='MIXER':
            t=1+self.mix_bank+knob if self.mode=='MIXER' else mixer.trackNumber()
            if self.mode=='MIXER':
                pan=self.shift or self.mix_view=='PAN';label='Pan' if pan else 'Volume'
                value=mixer.getTrackPan(t) if pan else mixer.getTrackVolume(t)
            else:
                label=('Volume','Pan','Stereo separation','Bass gain')[knob]
                value=(mixer.getTrackVolume(t) if knob==0 else mixer.getTrackPan(t) if knob==1
                       else mixer.getTrackStereoSep(t) if knob==2 else mixer.getEqGain(t,0,0))
        if label is not None:self.show_knob_value(self.knob_mode+' KNOB '+str(knob+1),label,'%.1f%%'%(value*100))

    def _turn_knob(self,knob,delta):
        if self.mode=='NOTE' and (self.shift or self.arp_page):
            was=self.shift
            self.shift=True
            try:
                return super().knob(knob,delta)
            finally:
                self.shift=was
        if self.mode=='NOTE' and self.alt:
            if knob==0:
                self.config['velocity']=clamp(self.config['velocity']+delta,1,127)
            elif knob==1:
                self.root=clamp(self.root+delta,0,96)
            elif knob==2:
                self.chord_kind=(self.chord_kind+delta)%4
            else:
                self.config['brightness']=clamp(self.config['brightness']+delta/100,0.1,1)
            self.notify('Note / light setting updated')
            return
        if self.mode in ('STEP','MELODY') and self.held:
            return super().knob(knob,delta)
        if self.knob_mode=='CHANNEL':
            c=self.selected()
            if c<0:return
            step=delta/(1000 if self.shift else 100)
            if knob==0: channels.setChannelVolume(c,clamp(channels.getChannelVolume(c)+step,0,1))
            elif knob==1: channels.setChannelPan(c,clamp(channels.getChannelPan(c)+step,-1,1))
            elif knob==2: channels.setChannelPitch(c,clamp(channels.getChannelPitch(c)+step,-1,1))
            else: channels.setTargetFxTrack(c,clamp(channels.getTargetFxTrack(c)+delta,0,mixer.trackCount()-2))
            self.notify(('Volume','Pan','Pitch','Mixer route')[knob])
            return
        if self.knob_mode=='MIXER':
            t=1+self.mix_bank+knob if self.mode=='MIXER' else mixer.trackNumber()
            if t>=mixer.trackCount()-1:return
            step=delta/(1000 if self.alt else 100)
            if self.mode=='MIXER':
                if self.shift or self.mix_view=='PAN':mixer.setTrackPan(t,clamp(mixer.getTrackPan(t)+step,-1,1))
                else:mixer.setTrackVolume(t,clamp(mixer.getTrackVolume(t)+step,0,1))
            elif knob==0:mixer.setTrackVolume(t,clamp(mixer.getTrackVolume(t)+step,0,1))
            elif knob==1:mixer.setTrackPan(t,clamp(mixer.getTrackPan(t)+step,-1,1))
            elif knob==2:mixer.setTrackStereoSep(t,clamp(mixer.getTrackStereoSep(t)+step,-1,1))
            else:mixer.setEqGain(t,0,clamp(mixer.getEqGain(t,0,0)+step,0,1))
            return
        if self.knob_mode=='USER2':
            self.scan_parameters(time.monotonic(),self.target()!=self.param_target)
            if self.param_signature[1]=='Built-in mixer EQ':
                track=self.param_target[0]
                step=delta/(1000 if self.shift else 100)
                if knob<3:
                    if self.param_page==0:
                        mixer.setEqGain(track,knob,clamp(mixer.getEqGain(track,knob,0)+step,0,1))
                    else:
                        mixer.setEqFrequency(track,knob,clamp(mixer.getEqFrequency(track,knob,0)+step,0,1))
                elif self.param_page==0:
                    mixer.setTrackStereoSep(track,clamp(mixer.getTrackStereoSep(track)+step,-1,1))
                else:
                    mixer.setTrackVolume(track,clamp(mixer.getTrackVolume(track)+step,0,1))
                self.notify('Track %d | '%track+self.param_names[self.param_page*4+knob])
                return
        super().knob(knob,delta)

    def send_leds(self):
        states={}
        def led(k,v):states[k]=v
        # Round mute LEDs are single-colour: off / dim / full (0 / 1 / 2).
        def row_state(muted,solo):
            return (2 if int(time.monotonic()*4)%2 else 0) if solo else (1 if muted else 2)
        # The separate rectangular indicators (CC 40-43) are red/green.
        def indicator(muted,solo):
            return (4 if int(time.monotonic()*4)%2 else 0) if solo else (3 if muted else 4)
        # Light every addressable control; state uses brighter values.
        for key in (31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53):
            led(key,1)
        led(27,16 | {'CHANNEL':1,'MIXER':2,'USER1':4,'USER2':8}[self.knob_mode])
        led({'STEP':44,'MELODY':44,'NOTE':45,'DRUM':46,'MIXER':47,'PERFORM':47}[self.mode],4)
        led(48,2 if self.shift else 1);led(49,2 if self.alt else 1)
        led(50,4 if transport.getLoopMode() else 3)
        led(51,3 if transport.isPlaying() else 1)
        led(52,1 if transport.isPlaying() else 4)
        led(53,3 if transport.isRecording() else 1)
        for row in range(4):
            if self.mode in ('STEP','MELODY','DRUM'):
                c=self.channel_bank+row
                if c<channels.channelCount():
                    led(36+row,row_state(channels.isChannelMuted(c),channels.isChannelSolo(c)))
                    led(40+row,indicator(channels.isChannelMuted(c),channels.isChannelSolo(c)))
            elif self.mode=='MIXER':
                t=1+self.mix_bank+row
                if t<mixer.trackCount()-1:
                    led(36+row,row_state(mixer.isTrackMuted(t),mixer.isTrackSolo(t)))
                    led(40+row,indicator(mixer.isTrackMuted(t),mixer.isTrackSolo(t)))

        # Send one final value per button, avoiding a dim-then-bright flicker.
        for key,value in states.items():
            device.midiOutNewMsg(0xB0|(key<<8)|(value<<16),key)

    def decorate_colors(self,colors,now):
        def tint(rgb,power):
            return tuple(int(clamp(v*power,0,127)) for v in rgb)
        if self.mode=='PERFORM':
            palette=((127,20,65),(12,95,127),(127,95,10),(75,20,127))
            ready=playlist.getPerformanceModeState()
            for pad in range(64):
                row,col=divmod(pad,16);track=self.clip_track+row
                status=playlist.getLiveBlockStatus(track,self.clip_block+col,0) if ready and track<=playlist.trackCount() else 0
                base=palette[(self.clip_block+col)//4%4]
                colors[pad]=((40,127,75) if status&4 else
                    (tint((127,115,65),1 if int(now*5)%2 else 0.3) if status&2 else (tint(base,0.7) if status&1 else (0,0,0))))
        elif self.mode=='NOTE':
            for pad in range(64):
                notes=self.pad_notes(pad)
                root=bool(notes and notes[0]%12==self.root%12)
                # Root notes are gold; other pitches form an ice-blue keyboard.
                colors[pad]=(127,88,12) if root else tint((20,65,127),0.35+(notes[0]%12)/24 if notes else 0.2)
                if self.chord_mode:
                    row,col=divmod(pad,16)
                    palette=((127,55,8),(95,20,127),(15,110,95),(127,20,65),(50,65,127),(127,85,10),(35,127,40))
                    colors[pad]=tint(palette[col%len(SCALES[self.scale])%7],0.45+0.12*(3-row))
                if pad in self.held:colors[pad]=(127,127,127)
                if pad in self.sustained:colors[pad]=(25,127,85)
        elif self.mode=='DRUM':
            palette=((127,35,4),(127,8,42),(90,15,127),(8,110,105))
            for pad in range(64):
                row,col=divmod(pad,16)
                index=(3-row)*4+(col%4)+(col//4)*16
                c=self.selected()
                valid=True
                if self.drum_channels:valid=self.channel_bank+index<channels.channelCount()
                elif c>=0 and plugins.isValid(c) and plugins.getPluginName(c)=='FPC':
                    valid=index<plugins.getPadInfo(c,-1,0,0)
                colors[pad]=tint(palette[col//4],0.55+0.12*(3-row)) if valid else (0,0,0)
                if pad in self.held:colors[pad]=(127,127,127)
        elif self.mode=='MELODY':
            seq=self.sequence()
            for pad in range(64):
                row,col=divmod(pad,16)
                active=scale_note(self.pitch_bank+3-row,self.root,self.scale) in seq.steps[self.page*16+col]['notes']
                base=(65+col*3,8,127-col*3)
                colors[pad]=tint(base,1 if active else (0.17 if col%4==0 else 0.065))
                if self.seq_enabled and transport.isPlaying() and self.seq_tick is not None and self.seq_tick%seq.length==self.page*16+col:
                    colors[pad]=(127,127,127) if active else (25,35,45)
        elif self.mode=='MIXER':
            for row in range(4):
                t=1+self.mix_bank+row
                if t>=mixer.trackCount()-1:
                    colors[row*16:row*16+16]=[(0,0,0)]*16
                    continue
                if self.mix_view=='PAN':
                    pos=round((mixer.getTrackPan(t)+1)*7.5)
                    for col in range(16):
                        base=(10,85,127) if col<8 else (127,15,100)
                        colors[row*16+col]=tint(base,1 if col==pos else (0.3 if col in (7,8) else 0.06))
                else:
                    value=mixer.getTrackVolume(t);level=round(value*15)
                    peak=clamp(round(mixer.getTrackPeaks(t,2)*15),0,15)
                    muted=mixer.isTrackMuted(t)
                    for col in range(16):
                        base=(8,127,45) if col<10 else ((127,80,4) if col<13 else (127,12,5))
                        colors[row*16+col]=tint((127,8,8) if muted else base,0.35 if muted and col<=level and value>0 else (0.85 if col<=level and value>0 else 0.045))
                        if col==peak and peak>0:colors[row*16+col]=(127,127,127)
        elif self.mode=='STEP':
            for pad in range(64):
                row,col=divmod(pad,16);c=self.channel_bank+row
                active=c<channels.channelCount() and channels.getGridBit(c,self.page*16+col)
                pressed=pad in self.held
                power=1 if active or pressed else 0
                if active and not pressed and channels.isChannelMuted(c):power=0.25
                colors[pad]=self.row_color(row,power)
        return colors

    def display_lines(self,lines):
        if self.sleeping:return ('JC Records','FIRE AFTER DARK','Touch to wake')
        if time.monotonic()<self.message_until:return self.knob_feedback or lines
        if self.knob_mode=='USER2' and not (self.mode=='NOTE' and (self.shift or self.arp_page)):
            if self.param_signature and self.param_signature[1]=='Built-in mixer EQ':
                return ('USER2 EQ T%d P%d'%(self.param_target[0],self.param_page+1),
                        'Bass / Mid / Treble' if self.param_page==0 else 'Bass/Mid/Treble freq',
                        '4: Stereo separation' if self.param_page==0 else '4: Track volume')
            return ('USER2 FX%d T%d P%d'%(self.fx_slot+1,self.target()[0],self.param_page+1),lines[1],lines[2])
        if self.mode=='NOTE' and not (self.shift or self.arp_page):
            title=('CHORD '+CHORDS[self.chord_kind] if self.chord_mode else 'NOTE')+(' HOLD' if self.note_hold else '')
            return (title,self.scale+' Root '+str(self.root),'Held %d | ALT+M3 hold'%len(self.sustained))
        if self.mode=='PERFORM':return ('CLIP PERFORMANCE','Tracks %d-%d'%(self.clip_track,self.clip_track+3),'Blocks %d-%d'%(self.clip_block+1,self.clip_block+16))
        if self.mode=='NOTE' and (self.shift or self.arp_page):return ('ARP '+('ON' if self.arp else 'OFF'),'%d/beat Gate %d%%'%(RATES[self.arp_rate],self.arp_gate*100),'%d oct %s'%(self.arp_octaves,ARP_ORDERS[self.arp_order]))
        if self.knob_mode=='CHANNEL':return (self.mode+' | CHANNEL','Volume / Pan','Pitch / Mixer route')
        if self.knob_mode=='MIXER':return ('MIXER '+self.mix_view,'Four faders' if self.mode=='MIXER' else 'Volume / Pan','SHIFT=pan ALT=fine' if self.mode=='MIXER' else 'Stereo / Low EQ')
        return (self.mode+' '+self.knob_mode+' P'+str(self.param_page+1),lines[1],lines[2])
