"""Run outside FL Studio: python tests/test_fire.py. Host mocks are not hardware validation."""
import importlib.util
import pathlib
import random
import struct
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rusty_core import *

class CoreTests(unittest.TestCase):
    def test_chords_follow_scale(self):
        self.assertEqual(chord(0,48,'Minor',1),(48,51,55))
        self.assertEqual(chord(0,48,'Major',2),(48,52,55,59))
        self.assertEqual(scale_note(-1,48,'Minor'),46)
        self.assertTrue(all(0 <= n <= 127 for n in chord(8,120,'Major',2)))

    def test_relative_encoders(self):
        self.assertEqual([relative(x) for x in (0,1,3,127,125)], [0,1,3,-1,-3])

    def test_parameter_mapping_keeps_all(self):
        names = ['Other','Release','Cutoff','Macro 1','Macro 2','Resonance']
        order = parameter_order(names)
        self.assertEqual(order[:3],[3,4,2])
        self.assertEqual(sorted(order),list(range(len(names))))
        self.assertEqual(parameter_order(['x','y']),[0,1])

    def test_arp_orders(self):
        self.assertEqual(arp_notes([60,64,67],1,'UpDown'),[60,64,67,64])
        self.assertEqual(arp_notes([120],3,'Up'),[120])
        self.assertEqual(arp_notes([60,64],1,'Down'),[64,60])

    def test_sequence_probability_ratchets_roundtrip(self):
        seq = Sequence()
        seq.toggle(0,(60,64,67))
        seq.steps[0]['ratchets'] = 4
        self.assertEqual(len(seq.events(0)),12)
        self.assertEqual(Sequence.from_dict(seq.to_dict()).to_dict(),seq.to_dict())
        seq.steps[0]['probability'] = 0
        self.assertEqual(seq.events(0),[])
        seq.toggle(0,(60,64,67))
        self.assertEqual(seq.steps[0]['notes'],[])

    def test_midi_binary_structure_and_paired_notes(self):
        seq = Sequence(16)
        seq.toggle(0,(48,51,55))
        seq.steps[0]['ratchets'] = 4
        data = midi_bytes(seq)
        self.assertEqual(data[:4],b'MThd')
        self.assertEqual(struct.unpack('>IHHH',data[4:14]),(6,0,1,480))
        self.assertEqual(struct.unpack('>I',data[18:22])[0],len(data)-22)
        i,tick,active = 22,0,set()
        def read_vlq():
            nonlocal i
            v = 0
            while True:
                b = data[i]; i += 1
                v = (v<<7)|(b&127)
                if b < 128:
                    return v
        count = 0
        while i < len(data):
            tick += read_vlq()
            status = data[i]; i += 1
            if status == 0xFF:
                kind = data[i]; i += 1
                length = read_vlq(); i += length
                if kind == 0x2F:
                    self.assertEqual(tick,1920)
                    break
            else:
                note,vel = data[i:i+2]; i += 2
                if status == 0x90:
                    self.assertNotIn(note,active)
                    active.add(note); count += 1
                else:
                    self.assertIn(note,active); active.remove(note)
        self.assertEqual(count,12)
        self.assertFalse(active)

    def test_animation_is_valid_midi(self):
        for t in range(60):
            frame = animation(t)
            self.assertEqual(len(frame),64)
            self.assertTrue(all(0 <= c <= 127 for rgb in frame for c in rgb))
        self.assertNotEqual(animation(0),animation(1))

class HostTests(unittest.TestCase):
    def setUp(self):
        self.notes=[]; self.grid={}; self.params={}; self.volumes={}; self.sysex=[]
        self.channel=0; self.pattern=1; self.playing=False; self.ticks=0; self.safe=True
        self.plugin_names=['Other','Cutoff','Resonance','Attack','Release']
        def mod(name,**members):
            m=types.ModuleType(name)
            m.__dict__.update(members)
            sys.modules[name]=m
            return m
        self.channels=mod('channels',channelNumber=lambda:self.channel,channelCount=lambda:8,
            getChannelIndex=lambda c:c+10,
            midiNoteOn=lambda c,n,v:self.notes.append((c,n,v)),
            selectOneChannel=lambda c:setattr(self,'channel',c),
            getGridBit=lambda c,s:self.grid.get((c,s),0),
            setGridBit=lambda c,s,v:self.grid.__setitem__((c,s),v),
            getCurrentStepParam=lambda c,s,p:100,
            setStepParameterByIndex=lambda c,p,s,k,v:self.params.__setitem__((c,p,s,k),v),
            getTargetFxTrack=lambda c:c+1,showEditor=lambda c:None)
        self.device=mod('device',isAssigned=lambda:True,setHasMeters=lambda:None,
            midiOutSysex=lambda s:self.sysex.append(s),midiOutNewMsg=lambda *a:None)
        mod('general',getVersion=lambda:44,getRecPPQ=lambda:96,safeToEdit=lambda:self.safe)
        mod('midi',pPitch=0,pVelocity=1,pPan=4,pModX=5,pModY=6,pShift=7,pRepeat=8,SONGLENGTH_ABSTICKS=2,widPianoRoll=3,widBrowser=4)
        mod('mixer',trackNumber=lambda:3,trackCount=lambda:127,getCurrentTempo=lambda:120,
            getSongStepPos=lambda:0,getTrackVolume=lambda t,mode=0:self.volumes.get(t,0.5),
            setTrackVolume=lambda t,v:self.volumes.__setitem__(t,v),getTrackPeaks=lambda t,m:0.3,
            isTrackMuted=lambda t:False,setTrackNumber=lambda t:None,getTrackName=lambda t:'Track '+str(t),
            muteTrack=lambda t:None,soloTrack=lambda t:None)
        mod('patterns',patternNumber=lambda:self.pattern,jumpToPattern=lambda p:setattr(self,'pattern',p))
        self.plugins=mod('plugins',isValid=lambda *a:True,getPluginName=lambda *a:'Test Synth',
            getParamCount=lambda *a:len(self.plugin_names),getParamName=lambda p,*a:self.plugin_names[p],
            getParamValue=lambda *a:0.5,setParamValue=lambda v,p,*a:self.params.__setitem__(p,v))
        mod('transport',isPlaying=lambda:self.playing,isRecording=lambda:False,
            getSongPos=lambda mode:self.ticks,stop=lambda:setattr(self,'playing',False),
            start=lambda:setattr(self,'playing',True),record=lambda:None,setLoopMode=lambda:None)
        mod('ui',setHintMsg=lambda s:None,showWindow=lambda w:None)
        mod('screen')
        self.channels.isChannelSolo=lambda c:False
        self.channels.isChannelMuted=lambda c:False
        self.length=4
        sys.modules['patterns'].getPatternLength=lambda p:self.length
        sys.modules['patterns'].setPatternLength=lambda p,v:setattr(self,'length',v)
        sys.modules['transport'].getLoopMode=lambda:0
        sys.modules['mixer'].isTrackSolo=lambda t:False
        self.clips=[]
        mod('playlist',getPerformanceModeState=lambda:True,trackCount=lambda:20,
            getLiveBlockStatus=lambda *a:1,triggerLiveClip=lambda *a:self.clips.append(a))
        for k,v in dict(TLC_Release=32,TLC_Fill=2,TLC_MuteOthers=1).items():setattr(sys.modules['midi'],k,v)
        sys.modules.pop('jc_controls',None)
        spec=importlib.util.spec_from_file_location('rusty_host',ROOT/'device_DJ_RUSTY_Fire.py')
        self.module=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.fire=self.module.Fire()
        scratch=pathlib.Path.cwd()/'work'/'test-runs'; scratch.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=scratch)
        assert pathlib.Path(self.tmp.name).resolve().is_relative_to(scratch.resolve())
        self.addCleanup(self.tmp.cleanup)
        self.module.HOME=self.tmp.name

    def event(self,key,value=127,status=0x90):
        e=types.SimpleNamespace(status=status,data1=key,data2=value,handled=False)
        self.fire.event(e)
        return e

    def test_button_led_message_and_cache_slot(self):
        packets=[]
        self.device.midiOutNewMsg=lambda msg,slot:packets.append((msg,slot))
        self.fire.send_leds()
        self.assertTrue(all(msg&255==0xB0 and (msg>>8)&255==slot for msg,slot in packets))
        self.assertTrue(set(range(31,54)).issubset({slot for _,slot in packets}))

    def test_mute_solo_led_states_follow_host(self):
        from unittest.mock import patch
        import jc_controls
        packets=[]
        self.device.midiOutNewMsg=lambda msg,slot:packets.append((slot,(msg>>16)&127))
        self.channels.isChannelMuted=lambda c:c==1
        self.channels.isChannelSolo=lambda c:c==2
        with patch.object(jc_controls.time,'monotonic',return_value=0.3):
            self.fire.send_leds()
        values=dict(packets)
        self.assertEqual([values[k] for k in (36,37,38)],[2,1,2])
        self.assertEqual([values[k] for k in (40,41,42)],[4,3,4])
        self.assertEqual(len(packets),len(values))
        with patch.object(jc_controls.time,'monotonic',return_value=0.6):
            self.fire.send_leds()
        self.assertEqual(dict(packets)[38],0)
        self.assertEqual(dict(packets)[42],0)
        self.fire.mode='MIXER'
        sys.modules['mixer'].isTrackMuted=lambda t:t==1
        sys.modules['mixer'].isTrackSolo=lambda t:t==2
        with patch.object(jc_controls.time,'monotonic',return_value=0.6):
            self.fire.send_leds()
        self.assertEqual([dict(packets)[k] for k in (36,37,38)],[1,0,2])
        self.assertEqual([dict(packets)[k] for k in (40,41,42)],[3,0,4])

    def test_chord_mode_and_inversions(self):
        f=self.fire; f.alt=True; self.event(45); f.alt=False
        self.assertTrue(f.chord_mode)
        self.assertEqual(f.pad_notes(48),(48,51,55))
        self.assertEqual(f.pad_notes(32),(51,55,60))
        self.event(102); self.assertEqual(len(f.held[48][2]),3)
        self.event(45)
        self.assertFalse(f.chord_mode); self.assertFalse(f.voices)
        self.assertEqual(len(f.pad_notes(48)),1)

    def test_synth_hold_toggles_and_stop_releases(self):
        f=self.fire; self.event(45); f.alt=True; self.event(38); f.alt=False
        self.event(102); self.event(102,0)
        self.assertTrue(f.voices); self.assertIn(48,f.sustained)
        self.event(102); self.event(102,0)
        self.assertFalse(f.voices); self.assertFalse(f.sustained)
        self.event(103); self.event(103,0); self.event(52)
        self.assertFalse(f.voices); self.assertFalse(f.sustained)

    def test_hold_disable_releases_and_latch_is_separate(self):
        f=self.fire; f.mode='NOTE'; f.alt=True; self.event(38); f.alt=False
        self.event(102); self.event(102,0)
        self.event(38)
        self.assertFalse(f.note_hold); self.assertTrue(f.latch); self.assertFalse(f.voices)

    def test_step_only_active_or_pressed_pads_are_coloured(self):
        f=self.fire
        self.grid[(0,2)]=1; self.grid[(1,2)]=1
        self.event(54)
        f.render(100)
        self.assertEqual(f.last_colors[0],f.row_color(0))
        self.assertEqual(f.last_colors[1],(0,0,0))
        self.assertEqual(f.last_colors[2],f.row_color(0))
        self.assertEqual(f.last_colors[18],f.row_color(1))
        self.event(54,0); self.event(54); self.event(54,0); f.render(101)
        self.assertEqual(f.last_colors[0],(0,0,0))

    def test_empty_clips_and_unavailable_fpc_pads_are_dark(self):
        f=self.fire; f.mode='PERFORM'
        sys.modules['playlist'].getLiveBlockStatus=lambda *a:0
        f.render(100); self.assertTrue(all(c==(0,0,0) for c in f.last_colors))
        f.mode='DRUM'; self.plugins.getPluginName=lambda *a:'FPC'
        self.plugins.getPadInfo=lambda *a:32
        f.render(101)
        self.assertNotEqual(f.last_colors[48],(0,0,0))
        self.assertEqual(f.last_colors[56],(0,0,0))

    def test_idle_timeout_default_is_ten_minutes(self):
        self.assertEqual(self.fire.config['sleep_seconds'],600)

    def test_round_buttons_mute_and_shift_solo(self):
        calls=[]
        self.channels.muteChannel=lambda c:calls.append(('mute',c))
        self.channels.soloChannel=lambda c:calls.append(('solo',c))
        self.event(37); self.fire.shift=True; self.event(38)
        self.assertEqual(calls,[('mute',1),('solo',2)])

    def test_step_arrow_grows_pattern_and_retains_steps(self):
        self.grid[(0,1)]=1
        self.event(35)
        self.assertEqual((self.fire.page,self.length),(1,8))
        self.fire.shift=True; self.event(35)
        self.assertEqual(self.length,12)
        self.assertEqual(self.grid[(0,1)],1)

    def test_performance_scene_release_all_tracks(self):
        self.event(47); self.fire.shift=True; self.event(54)
        self.assertEqual(len(self.clips),4)
        self.event(54,0)
        self.assertEqual(len(self.clips),8)
        self.assertTrue(all(c[2]==32 for c in self.clips[4:]))
        self.assertFalse(self.fire.clip_held)

    def test_performance_mode_switch_releases_clip(self):
        self.event(47); self.event(54); self.event(45)
        self.assertEqual(self.clips[-1],(1,0,32))
        self.assertFalse(self.fire.clip_held)

    def test_user_banks_cycle_and_render_all_modes(self):
        modes=[]
        for _ in range(4):
            self.event(26); modes.append(self.fire.knob_mode)
        self.assertEqual(modes,['MIXER','USER1','USER2','CHANNEL'])
        for mode in ('STEP','MELODY','NOTE','DRUM','PERFORM','MIXER'):
            self.fire.mode=mode; self.fire.render(100)
        self.assertEqual(self.fire.config['brightness'],1)

    def test_short_melody_preserves_hidden_notes_on_save(self):
        seq=self.fire.sequence(); seq.toggle(50,(60,))
        self.fire.mode='MELODY'; self.fire.set_length(16)
        restored=Sequence.from_dict(seq.to_dict())
        self.assertEqual(restored.steps[50]['notes'],[60])
        self.assertEqual(restored.length,16)

    def test_fl_entrypoint_loads_without_file_global(self):
        source=(ROOT/'device_DJ_RUSTY_Fire.py').read_text(encoding='utf-8-sig')
        namespace={'__name__':'__main__'}
        exec(compile(source,'<string>','exec'),namespace)
        self.assertNotIn('__file__',namespace)
        self.assertEqual(pathlib.Path(namespace['HOME']).resolve(),ROOT)
        self.assertIn('FireController',namespace)

    def test_shared_chord_notes_only_release_last_owner(self):
        f=self.fire
        f.voice_on('a',10,(60,64),100); f.voice_on('b',10,(64,67),100)
        f.voice_off('a')
        self.assertNotIn((10,64,0),self.notes)
        f.voice_off('b')
        self.assertEqual(self.notes.count((10,64,0)),1)

    def test_channel_change_releases_original_destination(self):
        self.fire.idle()
        self.event(45); self.event(54)
        self.channel=1; self.fire.idle()
        self.assertTrue(any(c==10 and v==0 for c,n,v in self.notes))
        self.assertFalse(self.fire.voices)

    def test_step_tap_and_hold_edit_are_distinct(self):
        self.event(54); self.event(54,0)
        self.assertEqual(self.grid[(0,0)],1)
        self.event(54); self.event(16,1,0xB0); self.event(54,0)
        self.assertEqual(self.grid[(0,0)],1)
        self.assertEqual(self.params[(0,1,0,1)],101)

    def test_step_channel_change_does_not_drop_held_pad(self):
        self.fire.idle(); self.event(70); self.fire.idle(); self.event(70,0)
        self.assertEqual(self.grid[(1,0)],1)

    def test_stop_flushes_arp_and_pending_notes(self):
        f=self.fire; f.mode='NOTE'; f.arp=True
        self.event(54); f.idle(); self.event(52)
        self.assertFalse(f.voices); self.assertFalse(f.queue); self.assertFalse(f.held)

    def test_mixer_fader_does_not_touch_master(self):
        self.fire.shift=True; self.event(47); self.fire.shift=False; self.event(69)
        self.assertEqual(self.volumes[1],1)
        self.event(54)
        self.assertEqual(self.volumes[1],0)
        self.assertNotIn(0,self.volumes)

    def test_paged_parameters_and_clamping(self):
        f=self.fire; f.mode='NOTE'; f.knob_mode='USER1'; f.scan_parameters(100,True)
        self.assertEqual(f.param_names[f.param_order[0]],'Cutoff')
        self.event(35); self.assertEqual(f.param_page,1)
        f.knob(0,10000)
        self.assertTrue(all(v<=1 for v in self.params.values()))

    def test_incremental_scan_completes_for_large_plugins(self):
        self.plugin_names=['Param '+str(n) for n in range(201)]
        for now in (100,101,102,103):
            self.fire.scan_parameters(now)
        self.assertEqual(len(self.fire.param_order),201)
        self.assertEqual(len(set(self.fire.param_order)),201)

    def test_sysex_packet_is_well_formed(self):
        self.fire.render(100)
        data=self.sysex[-1]
        self.assertEqual(data[:7],bytes((240,71,127,67,101,2,0)))
        self.assertEqual(len(data),264); self.assertEqual(data[-1],247)
        self.assertTrue(all(x<128 for x in data[1:-1]))

    def test_save_load_and_export(self):
        f=self.fire; f.sequence().toggle(0,(60,64,67)); f.save()
        f.sequences.clear(); f.load()
        self.assertEqual(f.sequence().steps[0]['notes'],[60,64,67])
        f.export()
        self.assertEqual(len(list(pathlib.Path(self.tmp.name).glob('Exports/*.mid'))),1)

    def test_modal_blocks_edits_but_releases_notes(self):
        self.fire.mode='NOTE'; self.event(54); self.safe=False; self.event(54,0)
        self.assertFalse(self.fire.voices)
        self.event(55)
        self.assertFalse(self.fire.voices)

    def test_queued_expired_notes_not_burst_after_stall(self):
        f=self.fire; f.schedule(10,0.1,10,(60,),100); f.process_queue(20)
        self.assertFalse(self.notes)

    def test_arp_parameter_edit_preserves_held_chord(self):
        f=self.fire; f.mode='NOTE'; f.arp=True; f.chord_kind=1
        self.event(54); f.idle(); f.shift=True; f.knob(0,1)
        self.assertIn(0,f.held)
        self.assertEqual(len(f.held[0][2]),3)

    def test_native_short_pattern_extended_for_four_pages(self):
        pattern_module=sys.modules['patterns']
        lengths=[]
        pattern_module.getPatternLength=lambda p:4
        pattern_module.setPatternLength=lambda p,n:lengths.append((p,n))
        self.fire.mode='MELODY'; self.fire.alt=True; self.event(25)
        self.assertEqual(lengths,[(1,16)])
        self.assertTrue(self.fire.seq_enabled)

    def test_fpc_uses_actual_kit_note(self):
        self.plugins.getPluginName=lambda *a:'FPC'
        self.plugins.getPadInfo=lambda c,s,opt,p:32 if opt == 0 else 42+p
        self.fire.mode='DRUM'; self.event(102)
        self.assertIn((10,42,100),self.notes)
        self.event(102,0)
        self.assertIn((10,42,0),self.notes)

    def test_melody_plays_and_host_stop_cleans_up(self):
        f=self.fire; f.seq_enabled=True; f.sequence().toggle(0,(60,64,67))
        self.playing=True; f.idle()
        self.assertEqual(len([v for c,n,v in self.notes if v>0]),3)
        self.playing=False; f.idle()
        self.assertFalse(f.voices)
        self.assertFalse(f.queue)

    def test_touch_and_release_never_edit_or_wake(self):
        f=self.fire; f.sleeping=True
        before=(f.last_action,f.knob_mode,f.param_page)
        for shift in (False,True):
            f.shift=shift
            for k in range(16,20):
                for status,value in ((0x90,127),(0x90,0),(0x80,0)):
                    self.assertTrue(self.event(k,value,status).handled)
        self.assertTrue(f.sleeping)
        self.assertEqual(before,(f.last_action,f.knob_mode,f.param_page))
        self.assertFalse(self.params)
        self.assertFalse(self.notes)

    def test_shift_pad_does_not_accent_without_turn(self):
        f=self.fire;f.shift=True
        self.event(54)
        self.assertFalse(self.params)
        self.assertFalse(self.grid)
        self.event(54,0)
        self.assertEqual(self.grid[(0,0)],1)
        self.assertFalse(self.params)

    def test_step_repeat_and_modifiers_require_hold_and_rotation(self):
        f=self.fire
        self.channels.getCurrentStepParam=lambda c,s,p:self.params.get((c,1,s,p),0 if p==8 else 64)
        self.event(54);f.shift=True
        self.event(19,127,0x90)
        self.assertFalse(self.params)
        self.event(19,1,0xB0)
        self.assertEqual(self.params[(0,1,0,8)],1)
        self.assertEqual(f.knob_feedback[1: ],('Note repeat','1/4'))
        self.event(17,1,0xB0)
        self.assertEqual(self.params[(0,1,0,6)],65)
        self.event(18,1,0xB0)
        self.assertEqual(self.params[(0,1,0,7)],65)
        self.event(16,1,0xB0)
        self.assertEqual(self.params[(0,1,0,1)],72)
        self.event(54,0)
        self.assertEqual(self.grid[(0,0)],1)
        f.shift=False
        count=len(self.params)
        self.event(19,0,0x80)
        self.assertEqual(len(self.params),count)

    def test_knob_oled_updates_immediately_with_actual_percentage(self):
        f=self.fire;f.knob_mode='USER1';f.scan_parameters(1,True)
        self.plugins.getParamValue=lambda p,*a:self.params.get(p,0.5)
        calls=[];screen=sys.modules['screen']
        screen.displayText=lambda *a:calls.append(a)
        screen.update=lambda:calls.append('update')
        f.screen_ok=True
        self.event(16,1,0xB0)
        self.assertIn('51.0%',f.knob_feedback[2])
        self.assertEqual(calls[-1],'update')
        self.event(16,1,0xB0)
        self.assertEqual(f.knob_feedback[2],'52.0%')
        self.assertEqual(f.display_lines(('old','old','old')),f.knob_feedback)

    def test_knob_indicators_enable_bit_control(self):
        packets=[]
        self.device.midiOutNewMsg=lambda msg,slot:packets.append((slot,(msg>>16)&127))
        for mode,value in [('CHANNEL',17),('MIXER',18),('USER1',20),('USER2',24)]:
            self.fire.knob_mode=mode
            self.fire.send_leds()
            self.assertEqual(dict(packets)[27],value)

    def test_user2_selects_loaded_effect_and_skips_empty_slots(self):
        f=self.fire; f.knob_mode='USER2'; f.mode='DRUM'
        self.plugins.isValid=lambda track,slot=-1:slot in (2,7)
        f.scan_parameters(1,True)
        self.assertEqual(f.param_target,(1,2))
        writes=[]
        self.plugins.setParamValue=lambda v,p,t,s:writes.append((v,p,t,s))
        f.knob(0,1)
        self.assertEqual(writes[0][2:],(1,2))
        f.shift=True; self.event(35)
        self.assertEqual(f.fx_slot,7)
        self.event(35)
        self.assertEqual(f.fx_slot,2)

    def test_user2_builtin_eq_pages_and_parameter_writes(self):
        f=self.fire; f.knob_mode='USER2'; f.mode='DRUM'
        self.plugins.isValid=lambda *a:False
        mx=sys.modules['mixer']; writes=[]
        mx.getEqGain=lambda *a:0.5
        mx.setEqGain=lambda t,b,v:writes.append(('gain',t,b,v))
        mx.getEqFrequency=lambda *a:0.5
        mx.setEqFrequency=lambda t,b,v:writes.append(('freq',t,b,v))
        mx.getTrackStereoSep=lambda t:0
        mx.setTrackStereoSep=lambda t,v:writes.append(('stereo',t,v))
        f.scan_parameters(1,True)
        self.assertEqual(len(f.param_order),8)
        for k in range(4):f.knob(k,1)
        self.assertEqual([w[0] for w in writes],['gain','gain','gain','stereo'])
        self.assertTrue(all(w[1]==1 for w in writes))
        self.event(35)
        self.assertEqual(f.param_page,1)
        f.knob(0,1); f.knob(3,1)
        self.assertEqual(writes[-1][:3],('freq',1,0))
        self.assertAlmostEqual(self.volumes[1],0.51)
        f.scan_parameters(100)
        self.assertEqual(f.param_page,1)
        f.message_until=0
        self.assertIn('USER2 EQ',f.display_lines(('','',''))[0])

    def test_user2_recovers_when_effect_is_added_or_removed(self):
        f=self.fire;f.knob_mode='USER2'
        self.plugins.isValid=lambda *a:False
        f.scan_parameters(1,True)
        self.assertEqual(f.param_signature[1],'Built-in mixer EQ')
        self.plugins.isValid=lambda t,s=-1:s==4
        f.scan_parameters(2)
        self.assertEqual(f.param_target,(1,4))
        self.assertEqual(len(f.param_order),5)
        self.plugins.isValid=lambda *a:False
        f.scan_parameters(3)
        self.assertEqual(f.param_signature[1],'Built-in mixer EQ')

    def test_fx_target_uses_drum_route_or_selected_mixer(self):
        f=self.fire; f.knob_mode='USER2'; f.mode='DRUM'
        self.assertEqual(f.target(),(1,0))
        f.mode='MIXER'
        self.assertEqual(f.target(),(3,0))

    def test_melody_changes_do_not_write_native_piano_roll(self):
        self.fire.mode='MELODY'; self.event(102)
        self.assertTrue(self.fire.sequence().steps[0]['notes'])
        self.assertFalse(self.grid)

if __name__ == '__main__':
    unittest.main(verbosity=2)

