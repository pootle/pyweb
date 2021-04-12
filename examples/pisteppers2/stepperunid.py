#!/usr/bin/python3

"""
A module to drive a stepper motor via a basic driver chip like ULN2003.

The driver directly controls the individual windings.
In software mode PWM is used to give fine control of the power to each winding. DMA mode only
switches each winding off or on, so fine grained microstepping is not practical, but much higher speeds
can be reached.

In dma mode, 1000 steps per second is easily reached with CPU load in python and pigpio both below 10% each.
In this mode multiple steppers can be driven with minimal performance overhead.

Timing accuracy:
Software mode is subject to random variation due to scheduling and loading constraints within the OS. This is
particularly true on single core systems like the Raspberry pi Zero. On multiple core machines these random
fluctuations will be much less severe, but not entirely absent.

In Dma mode the step timings are very accurate - each step is timed to the nearest micro-second. As long as the
computer can cope with providing the new dma blocks in time, speed is unlimited.

On a Raspberry pi Zero:
in soft mode, a single stepper can be driven at up to 250 - 300 steps per second, at 300 steps 
per second, cpu load is approaching 40% in the python code, and 25% in pigpio. Additional stepper motors will
reduce the maximum achievable speed.

Power and motor heating:
In dma mode, this driver merely switches each winding on or off. Particularly when running slowly (when back EMF is
low), this can result in the motor getting hot. Software mode uses PWM defined in the step table, so current can be
limited in this way.
"""
import time, threading, math
import pigpio

class Unipolar_direct:
    """
    Drives a single unipolar stepper motor using 4 gpio pins driving a set of simple switches (such as a ULN2003).
    
    In soft mode, PWM is used to provide smoother running.
    
    In dma (pigpio - wave) mode each output stage is simply turned on or off, with on used if the value for the pin is 128 - 255.
    Thus more detailed levels of microstepping are not sensible. Also, if the motor is run at low speed in this mode
    the motor can get quite hot so it may not be practical for extended continuous running - this depends on the motor, the speed
    and driving voltage.
    
    Each instance has the following attributes that can be read at any time:
        
    current_pos: The motor position (scaled). In software mode this is always up to date, in DMA mode this is only updated after the end
                 of each DMA block, with default values this means the position can lag by just over .5 seconds.
    
    drive_mode:  The drive mode the motor is in: 'off', 'dma', 'soft'.
    
    drive_state: The motor state:
                'off' : The motor is stopped with no power applied.
                'stop': The motor is stopped, but the coils will be energised to the power level (PWM) in 'stop_power'.
                'halt': The motor is stopped, power still on
                'fast': The motor is speeding up.
                'slow': The motor is slowing down.
                'max' : The motor is at max speed.
    """
    def __init__(self, *, pigp, drvpins, holdpower, stepping_params, unit_scale, current_pos):
        """
        Setup to drive a unipolar stepper motor via buffer (e.g. ULN2003)
        
        pigp           : instance of pigpio
        
        drvpins        : list of 4 pins to drive the 4 windings
        
        steppingparams : dict of stepping tables, each identified by a key.
        
        unit_scale     : target_pos is scaled by this before being passed to the step generator, current_pos is also 
                         scaled when read. The position can this reflect any appropriate measure (degrees or distance for example).
                         set to 1 for no scaling.

        current_pos    : the initial position in scaled units (e.g. degrees) 
        """
        self.pio=pigp
        if not self.pio.connected:
            print('Pigpio not working!')
            raise ValueError('pigpio not connected')
        assert len(drvpins) == 4
        self.pins=[int(p) for p in drvpins]
        for i in self.pins:
            assert  0<i<32
        self.stepping_params = {k:v.copy() for k,v in stepping_params.items()}
        for stepsetname, stepentry in self.stepping_params.items():
            assert stepentry['drive_mode'] in ('soft', 'dma')
            steptable = stepentry['step_tables']
            if stepentry['drive_mode'] == 'dma':
                for steppingdef in steptable:
                    assert steppingdef[0] == 'block', str(steppingdef)
            stepentry['prep_tables'] = tuple((make_step_set(steppingdef, self.pins), steppingdef[2], steppingdef[3]) for steppingdef in steptable)
            print('stepset %s prepared tables:' % stepsetname)
            for stepset in stepentry['prep_tables']:
                print('    table length : %d' % len(stepset[0]))
                print('         max tps : %d' % stepset[1])
                print('      microsteps : %d' % stepset[2])
        self.stepindex=0
        self.output_enable(False)
        self.unit_scale = unit_scale
        self.current_pos = current_pos
        self.current_tps = float('nan')
        self._target_pos = current_pos
        self.drive_mode='off'
        self.drive_state='off'
        self.drive_thread = None
        self.step_gen = None
        self.step_style = 'off'
        self.last_table=list(self.stepping_params.values())[0]['prep_tables'][0][0]
        
    @property
    def target_pos(self):
        return self._target_pos

    @target_pos.setter
    def target_pos(self, val):
        self._target_pos=float(val)
        if not self.step_gen is None:
            self.step_gen.target_pos = round(self._target_pos*self.unit_scale)

    @property
    def max_tps(self):
        if self.step_gen is None:
            return float('nan')
        else:
            return self.step_gen.max_tps

    @max_tps.setter
    def max_tps(self, val):
        if not self.step_gen is None:
            self.step_gen.max_tps = float(val)

    @property
    def acceleration(self):
        if self.step_gen is None:
            return float('nan')
        else:
            return self.step_gen.accel_tps

    @acceleration.setter
    def acceleration(self, val):
        print('accel changed')
        if not self.step_gen is None:
            self.step_gen.accel_tps = float(val)

    def output_enable(self, enable):
        if enable:
            setvals = self.swustep_tables[0][1][self.stepindex] # not any more!
            for pix, p in enumerate(self.pins):
                pval=round(setvals[pix]*self.holdpower)
            self.pio.set_PWM_dutycycle(p, pval)
            print('pin %d set to dutycycle %d' % (p,pval))
            self.log('output pins set to dutycycle %d' % round(self.holdpower*100))
        else:
            print('turning off pins', self.pins)
            for p in self.pins:
                self.pio.set_mode(p,pigpio.OUTPUT)
                self.pio.write(p, 0)

    def crash_stop(self):
        """
        (almost) immediate stop, including stopping the soft_run thread.
        """
        if not self.drive_thread is None:
            self.step_gen.crash_stop()
            while self.is_active():
                time.sleep(.1)
        self.output_enable(False)
        self.log('all outputs off')

    def run_motor(self, step_style):
        """
        starts up a thread to drive the motor in dma mode or software mode using the named entry in steptables.
        """
        if step_style == 'off':
            if not self.drive_thread is None:
                self.step_gen.clean_stop()
        else:
            if self.drive_mode == 'off':
                assert step_style in self.stepping_params,'mode %s not in %s' % (step_style, list(self.stepping_params.keys()))
                self._active_params = self.stepping_params[step_style]
                drivemode=self._active_params['drive_mode']
                sm=[amode[1:] for amode in self._active_params['prep_tables']]
                self.step_gen = self._active_params['stepgen_class'](step_levels = sm, **self._active_params['stepgen_params'])
                self.step_gen.target_pos=round(self.target_pos*self.unit_scale)
                print('step generator setup')
                self.drive_thread = threading.Thread(
                            target=self.soft_track if drivemode=='soft' else self.dma_track,
                            args=(self._active_params,),
                            name='%s run thread' % drivemode)
                self.drive_mode = drivemode
                self.step_style = step_style
                self.drive_thread.start()
            else:
                raise ValueError('motor is already running')

    def clean_stop(self):
        """
        decelerate if running then stop, including stopping the active thread.
        """
        if not self.drive_thread is None:
            self.step_gen.clean_stop()

    def is_active(self):
        if self.drive_thread is None:
            return False
        else:
            if self.drive_thread.is_alive():
                return True
            else:
                self.drive_thread.join()
                self.drive_thread = None
                self.step_gen = None
                self.step_style = 'off'
                return False

    def soft_track(self, step_defs):
        """
        Drives the motor to the position in self.target_pos  using step timings from the step timing generator
        
        self.target_pos can be updated at any time.
        
        Holds position while at target_pos
        
        This runs until the step generator raises StopIteration
        """
        tgen=self.step_gen.tickgen(self.current_pos*self.unit_scale)
        oldlen = len(self.last_table)
        active_table=step_defs['prep_tables'][0][0]
#        stepx=round(self.stepindex*len(active_table)/oldlen)
        stepx = round(len(active_table) * self.stepindex / oldlen)
        pigp=self.pio
        total_overruns = 0
        lastvals=[None, None, None, None]
        act, delay, tickpos, self.drive_state, self.current_tps = next(tgen)
        nextsteptime=time.time()
        self.current_pos = tickpos/self.unit_scale
        holdtime = 0.0
        try:
            while True:
                nextsteptime += delay
                if act is None:
                    if forward:
                        stepx += 1
                        if stepx >= len(steptable):
                            stepx = 0
                    else:
                        stepx -= 1
                        if stepx < 0:
                            stepx=len(steptable)-1
                    pvals=steptable[stepx]
                    if isinstance(active_table, step_set_pwm):
                        for pix, pv in enumerate(pvals):
                            if pv != lastvals[pix]:
                                pigp.set_PWM_dutycycle(self.pins[pix], pv)
                                lastvals[pix]=pv
                    elif isinstance(active_table, step_set_onoff):
                        for pix, pv in enumerate(pvals):
                            if pv != lastvals[pix]:
                                pigp.write(self.pins[pix], pv)
                                lastvals[pix] = pv
                    elif isinstance(active_table, step_set_pinmasks):
                        pigp.clear_bank_1(pvals.pinmasks[1])
                        pigp.set_bank_1(pvals.pinmasks[0])
                    else:
                        print(active_table)
                        raise ValueError()
                    holdtime = 0.0
                elif act == 'h':
                    if step_defs['hold_timeout'] > 0:
                        if not holdtime is None:
                            holdtime += delay
                            if holdtime > step_defs['hold_timeout']:
                                self.output_enable(False)
                                holdtime = None
                                self.drive_state = 'off'
                else:
                    forward = act > 0
                    oldlen = len(active_table)
                    active_table=step_defs['prep_tables'][abs(act)-1][0]
                    if isinstance(active_table, step_set_onoff):
                        for p in self.pins:
                            pigp.set_mode(p,pigpio.OUTPUT)
                    steptable = active_table
                    stepx = round(len(active_table) * stepx / oldlen)
                    holdtime=0.0
                sleeptime = nextsteptime - time.time()
                if sleeptime > 0:
                    time.sleep(sleeptime)
                else:
                    total_overruns -= sleeptime
                act, delay, tickpos, self.drive_state, self.current_tps = next(tgen)
                self.current_pos = tickpos/self.unit_scale 
        except StopIteration:
            pass
        print('total overruns %6.3f' % total_overruns)
        self.last_table=active_table
        self.stepindex = stepx
        self.output_enable(False)
        self.drive_mode='off'
        self.drive_state='off'

    def pulsegen(self, initial_pos, base_time, step_defs):
        """
        Uses the output from a step timing generator to yield a sequence of data used to create pigpio pulses.
        
        This enables a client to drive the stepper motor using DMA for highly accurate and fast timing.

        initial_pos : position baseline at start
        
        base_time   : time baseline at start
        
        step_defs   : list of step tables

        each yield returns:
            0: 2-tuple of gpio pins to turn on and gpio pins to turn off - or None if holding
            1: time after this pulse in microseconds (int)
            2: time after this pulse in seconds (float)
            3: motor position after this pulse (absolute)
            4: motor state
            5: current tps

        The generator raises stop iteration when no further action will be needed.
        """
        tgen=self.step_gen.tickgen(initial_pos*self.unit_scale)
        oldlen = len(self.last_table)
        active_table=step_defs['prep_tables'][0][0]
        stepx = round(len(active_table) * self.stepindex / oldlen)
        assert 0 <= stepx < len(active_table) 
        act, delay, tickpos, dstate, tps = next(tgen)
        next_step_time = 0.0 # current time offset in seconds (floating point)
        microstep_time=0  # current time offset in microseconds (integer)
        active_table=step_defs['prep_tables'][0][0]
        assert isinstance(active_table, step_set_pinmasks)
        sc=0
        try:
            while True:
                if act is None: # do a standard step
                    next_step_time += delay
                    pulse_delay = round(next_step_time * 1000000)-microstep_time
                    microstep_time += pulse_delay
                    try:
                        yield active_table.pinmasks[stepx], microstep_time, next_step_time, tickpos, dstate, tps
                        sc += 1
                    except:
                        print('active table pinmasks len: %d, index: %d, at step: %d' % (len(active_table.pinmasks), stepx, sc))
                        raise
                    if dir > 0:
                        stepx += 1
                        if stepx >= len(active_table):
                            stepx = 0
                    else:
                        stepx -= 1
                        if stepx < 0:
                            stepx = len(active_table)-1
                elif act == 'h':# we're holding position
                    next_step_time += delay
                    pulse_delay = round(next_step_time * 1000000)-microstep_time
                    microstep_time += pulse_delay                 
                    yield None,  microstep_time, next_step_time, tickpos, dstate, tps
                    sc += 1
                else:           # set direction / microstep level     ** NOTE the 1st output should always be a set direction / step mode
                    dir = act > 0
                    oldlen = len(active_table)
                    active_table=step_defs['prep_tables'][abs(act)-1][0]
                    assert isinstance(active_table, step_set_pinmasks)
                    stepx =  round(len(active_table) * stepx / oldlen)
                    assert 0 <= stepx < len(active_table) 
                act, delay, tickpos, dstate, tps = next(tgen)
        except StopIteration:
            print('pulsegen stops')
        self.last_table=active_table
        self.stepindex = stepx
        print('pulsegen stop iteration')

    def dma_track(self, step_defs):
        tgen=self.pulsegen(self.current_pos, 0, step_defs)
        pigp=self.pio
        self.pio.wave_clear()
        moredata=True
        pendingwaves=[]
        buffends=[]
        maxpulses=1000          # limit the number of pulses per wave
        maxwaves=3              # target number of waves
        maxtime=500000          # limit the time for 
        wavepercent=100//maxwaves
        sentbuffs=[]
        savedbuffs=[]
        print('dma track starts')
        holdtimeout=None
        try:
            thisp = next(tgen)
        except StopIteration:
            moredata=False
        while moredata:
            while len(pendingwaves) < maxwaves and moredata:
                bufftime=maxtime
                if len(savedbuffs) > 0:
                    nextbuff=savedbuffs.pop(0)
                    nextbuff.clear()
                else:
                    nextbuff=[]
                while len(nextbuff) < maxpulses and bufftime >= 0:
                    try:
                        nextp = next(tgen)    #pinonoff, ustime, sectime, posn
                    except StopIteration:
                        nextp=None
                        moredata=False
                    if nextp is None:
                        if not nextp is None:
                            nextbuff.append(pigpio.pulse(*thisp[0], 1))
                        moredata=False
                        thisp=nextp
                        break
                    else:
                        dtime=nextp[1]-thisp[1]
                        assert dtime >= 0
                        if thisp[0] is None:
                            holding=True
                            sectime=dtime/1000000
                            time.sleep(sectime)
                        else:
                            holding=False
                            nextbuff.append(pigpio.pulse(*thisp[0], dtime))
                        thisp=nextp
                        bufftime -= dtime
                    mposn=thisp[3] # update motor's last known position in this buffer
                    mstate=thisp[4]
                    mtps=thisp[5]
                if len(nextbuff) > 0:
                    try:
                        pcount=self.pio.wave_add_generic(nextbuff)
                    except Exception as ex:
                        '''oh dear we screwed up - let's print the the data we sent'''
                        print('FAIL in wave_add_generic' + str(ex))
                        for i, p in enumerate(nextbuff):
                            print('%4d: on: %8x, off: %8x, delay: %8d' % (i, p.gpio_on, p.gpio_off, p.delay ))
                        raise
                    cbcount=self.pio.wave_get_cbs()
                    waveid=self.pio.wave_create_and_pad(wavepercent)
                    sentbuffs.append(nextbuff)
                    pendingwaves.append(waveid)
                    buffends.append((mposn, holding, mstate, mtps))
                    self.pio.wave_send_using_mode(waveid, pigpio.WAVE_MODE_ONE_SHOT_SYNC)
                    holdtimeout=None
                else:
                    savedbuffs.append(nextbuff)
                    if holdtimeout is None:
                        print('zerobuff start hold timeout', nextp, holding)
                        holdtimeout=time.time()+step_defs['hold_timeout']
                    elif holdtimeout > 0 and time.time() > holdtimeout:
                        self.output_enable(False)
                        holdtime = None
                        self.drive_state = 'off'
                        holdtimeout = 0
                    if nextp is None or thisp is None:
                        time.sleep(.1)
                    else:
                        time.sleep(nextp[1]-thisp[1])
                    break
            while len(pendingwaves) > 0 and self.pio.wave_tx_at() != pendingwaves[0]:
                endposn=None
                donebuf = pendingwaves.pop(0)
                try:
                    self.pio.wave_delete(donebuf)
                    print('wave %d complete, remains: %s' % (donebuf, len(pendingwaves)))
                except pigpio.error:                            
                    print('wave delete failed for wave %d with %s' % (donebuf, pendingwaves))
                    raise
                endposn, isholding, mstate, mtps = buffends.pop(0)
                savedbuffs.append(sentbuffs.pop(0))
                if not endposn is None:
                    self.current_pos = endposn/self.unit_scale 
                    self.halted=isholding
                    self.drive_state=mstate
                    self.current_tps=mtps
#                    print('dmatrack sets holding', isholding)
            if len(pendingwaves) >= maxwaves: # check if we have room for another wave right now - if not, wait a bit
                time.sleep(.1)
        print('final waves %d' % len(pendingwaves))
        while len(pendingwaves) > 0:
            time.sleep(.2)
            current=self.pio.wave_tx_at()
            if current == 9999 or pendingwaves.index(current) != 0:
                donebuf = pendingwaves.pop(0)
                print('wave %d complete' % donebuf )
                self.pio.wave_delete(donebuf)
                endposn, isholding, mstate, mtps = buffends.pop(0)
                if not endposn is None:
                    self.current_pos = endposn/self.unit_scale
                    self.drive_state=mstate
                    self.current_tps=mtps
            elif current ==pendingwaves[0]:
                pass
#                    self.log(loglvls.DEBUG,'wave %d running' % current)
            else:
                print('BBBBBBBBBBBBBBBBBBBBBBBBBBAArg')
        self.halted = True
        self.pio.wave_clear()
        time.sleep(.1)
        self.output_enable(False)
        self.drive_mode='off'
        self.drive_state='off'
        print('dmatrack exits')

    def log(self, msg):
        print(msg)

class stepset(tuple):
    """
    base class for a full cycle of step definitions
    """
    pass

class step_set_pwm(stepset):
    pass

class step_set_onoff(stepset):
    pass

class step_set_pinmasks(step_set_onoff):
    def setpins(self, drivepins):
        self.pinmasks=[
            (sum([2**pinno if pvals[pix] == 1 else 0 for pix, pinno in enumerate(drivepins)]), 
             sum([2**pinno if pvals[pix] == 0 else 0 for pix, pinno in enumerate(drivepins)])) for pvals in self]

def check_shape(powers, minval, maxval):
    assert len(powers) >= 4
    assert math.log(len(powers), 2).is_integer()
    for ent in powers:
        assert len(ent) == 4
        for pow in ent:
            assert minval <= pow <= maxval
    return [bytes(ent) for ent in powers]

def make_step_set(powerdefs, drivepins):
    if powerdefs[0]=='pwm':
        stepinf = step_set_pwm(check_shape(powerdefs[1], 0, 255))
    elif powerdefs[1]=='onoff':
        stepinf = step_set_pwm(check_shape(powerdefs[1], 0, 1))
    elif powerdefs[0]=='block':
        stepinf = step_set_pinmasks(check_shape(powerdefs[1], 0, 1))
        stepinf.setpins(drivepins)
    return stepinf
        
