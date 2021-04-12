#!/usr/bin/python3
"""
This module is a timing generator for stepper motors.

Timings are generated on demand by a generator that uses various settings held by the class.

Some of these settings can be changed as the generator is running, as can a couple of settings
within the motor instance that contains this class; the generator adapts dynamically to 
these changes.

The generators work in their own time frame so can be used both in real time and to pre-prepare
step timings, this is handled by the code calling these generators.
"""
class stepconstacc():
    """
    generates step timings with constant slope ramping.
    
    A class is used rather than a function to allow certain variables to be monitored  and / or set.
    
    start_tps, max_tps, accel_tps and target_pos are only read by this class and can be changed externally at any time.
    
    when multiple microstep levels are used, the position is counted in the smallest microsteps (so it is always an int) 
    
    Each level is a tuple:
        0: the maximum tps to use for this level
        1: number of microsteps this level moves for each step issued
        
        Note that each level should be 1/2 the number of microsteps of the previous level (when reducing the number of microsteps, the code
        always changes the level on an even step boundary where the old and new levels have a corresponding entry) 
    """
    def __init__(self, *, start_tps, max_tps, accel_tps, dir_delay, step_levels, hold_tick, ustep_factor):
        """
        setup a ramping timer generator.
        
        start_tps   : ticks per second to start at / stop at (minimum speed)
        
        max_tps     : maximum ticks per second to run at
        
        accel_tps   : change in tps to speed up  / slow down
        
        dir_delay   : minimum delay after dir change / microstep mode change before a step issued 
                        (typically very short time just for the driver chip to be ready)
        
        step_levels : defines a number of microstep levels to be used and the speeds at which each is used. None if unused.

        hold_tick   : when at target,this is the time used for holding ticks
        
        ustep_factor: max_microsteps per full step 
        
        Note that start, max and accel_tps are all the full step speed. The class automatically scales this to allow for the active microstep level.
        
        """
        self.start_tps=  float(start_tps)
        self.max_tps =   float(max_tps)
        self.accel_tps=  float(accel_tps)
        self.dir_delay = float(dir_delay)
        self.hold_tick = float(hold_tick)
        if step_levels[-1][0] < self.max_tps:
            raise ValueError('final step mode tps (%5.1f) cannot be slower than max_tps (%5.1f)' % (step_levels[-1][0], self.max_tps))
        prev_level = step_levels[0][1]
        for steplvl in step_levels[1:]:
            assert steplvl[1]*2 == prev_level or steplvl[1] == prev_level, 'this level (%d) vs previous level (%d) invalid.' %(steplvl[1], prev_level)
            prev_level = steplvl[1]
        self.step_levels = step_levels
        self.max_microsteps=ustep_factor

    def logmsg(self, msg):
        self.lastlog = msg

    def clean_stop(self):
        """
        stops the motor with slowdown (if it is running) and then exits the generator.
        """
        self.running=False

    def crash_stop(self):
        self.running=False
        self.crashing=True

    def tickgen(self, current_pos):
        """
        generator function for step times.
        
        yields a sequence of step times, stopping at target. Speed is ramped up and down and various parameters are monitored to update
        the generated steps.
              
        yields:     a 5 - tuple defining the next step action:
            'h',  delay, posn, act, tps  :  no action needed (we are at target position) - delay will be hold time
            None, delay, posn, act, tps  :  step in the current direction, then wait for the specified delay (float in seconds)
            -n,   delay, posn, act, tps  :  set the step direction to backwards using microstep level n
            +n,   delay, posn, act, tps  :  set the step direction to forwards using micro step level n
            
            posn is the step location after the step action

            act is one of:
                'halt'  : motor is stationary
                'fast'  : motor is speeding up
                'slow'  : motor is slowing down
                'max'   : motor is at max speed
            
            tps is the current ticks per second for diagnostic / monitoring

        current_pos : step position motor is at. This is the base from which posn is reported after each step action
        """
        self.running=True
        self.crashing=False
        curr_dir = None
        curr_mode_no = 0
        curr_mode = self.step_levels[0]
        step_fact = curr_mode[1]
        step_scale = int(self.max_microsteps/step_fact)
        lmax_tps = curr_mode[0]
        lmin_tps = 0
        self.logmsg('step for variable microsteps with max microsteps per step = %d' % step_scale)
        currtps=self.start_tps                           # number of (full) steps per second to start at
        currtick = 1/currtps/step_fact
        while self.running:
            offset=self.target_pos-current_pos
            new_dir=-1 if offset< 0 else 1
            deceltime=(currtps-self.start_tps) / self.accel_tps    # time it will take to get to start / stop speed speed from current speed
            averagetps=(currtps+self.start_tps) / 2
            decelsteps = averagetps * deceltime * self.max_microsteps + (2 if self.step_levels is None else self.max_microsteps*2) 
                                    # slight fidget factor because of simple calc below to avoid overshoot
            if abs(offset) <= decelsteps or curr_dir != new_dir:   # check if near target or change dir - slow down
                if currtps <= self.start_tps:                      # reached min speed ?
                    if abs(offset) < step_scale:                   # as  close as poss to target?
#                        self.logmsg('at target')
                        curr_dir = None                            # set current direction to None so we start fast with a set direction
                        yield 'h', self.hold_tick, current_pos, 'halt', 0
#                        print('tickgen holding at target')
                        while abs(self.target_pos-current_pos) < step_scale and self.running:
                            yield 'h', self.hold_tick, current_pos, 'halt', 0
                        print('tickgen hold finished', self.running)
                    elif new_dir != curr_dir:
#                        self.logmsg('change dir: %s using microstep mode %d' % (('fwd' if new_dir > 0 else 'rev'), curr_mode_no))
                        if curr_dir is None:
                            yield new_dir*(curr_mode_no + 1), self.dir_delay, current_pos, 'halt', 0  # if fresh start, then use minimal delay before first step
                        else:
                            yield new_dir*(curr_mode_no + 1), currtick, current_pos, 'halt', 0
                        curr_dir = new_dir
#                        self.logmsg('first step')
                        current_pos += curr_dir*step_scale
                        yield None, currtick, current_pos, 'fast', currtps
                    else:
#                        self.logmsg('final positioning')
                        current_pos += curr_dir*step_scale
                        yield None, currtick, current_pos, 'slow', currtps
                else:                                                      # slowing down
                    currtps -= self.accel_tps * currtick                   # not exactly right cos ramp is finite steps, but simple calc
                    if currtps < self.start_tps:
                        currtps=self.start_tps                             # clamp to slow_tps so we don't get too slow as we near target
                    if currtps < lmin_tps:                                 # time to switch microstep mode?
                        boundary=max(1,round(step_fact / self.step_levels[curr_mode_no-1][1]))
                        if current_pos % boundary == 0:                 # change mode now
                            curr_mode_no -= 1
                            curr_mode = self.step_levels[curr_mode_no]
                            step_fact = curr_mode[1]
                            step_scale = int(self.max_microsteps/step_fact)
                            lmax_tps = lmin_tps
                            lmin_tps = 0 if curr_mode_no == 0 else self.step_levels[curr_mode_no-1][0]
#                            self.logmsg('change step mode to %d with scale now %5.3f' % (curr_mode_no, step_scale))
                            yield curr_dir*(curr_mode_no + 1), 0, current_pos, 'slow', currtps
#                        else:
#                            self.logmsg('delay mode change. pos: %d, scale: %d, calc: %d, ' % (current_pos, step_scale, current_pos % (step_scale/2)))
                    currtick=1/currtps/step_fact
                    current_pos += curr_dir*step_scale
#                    self.logmsg('slower')
                    yield None, currtick, current_pos, 'slow', currtps
            elif currtps == self.max_tps:                                  # speed is max
                current_pos += curr_dir*step_scale
#                self.logmsg('at max speed')
                yield None, currtick, current_pos, 'max', currtps
            elif currtps > self.max_tps:                                   # too fast - did user change max_tps? - slow down
                currtps -= self.accel_tps * currtick                       # not exactly right cos ramp is finite steps, but simple calc
                if currtps < self.start_tps:
                    currtps=self.start_tps                                 # clamp to slow_tps so we don't get too slow as we near target
                if currtps < lmin_tps:                                     # time to switch microstep mode?
                    boundary=max(1,round(step_fact / self.step_levels[curr_mode_no-1][1]))
                    if current_pos % boundary == 0:                 # change mode now
                        curr_mode_no -= 1
                        curr_mode = self.step_levels[curr_mode_no]
                        step_fact = curr_mode[1]
                        step_scale = int(self.max_microsteps/step_fact)
                        lmax_tps = lmin_tps
                        lmin_tps = 0 if curr_mode_no == 0 else self.step_levels[curr_mode_no-1][0]
#                        self.logmsg('change step mode to %d with scale now %5.3f' % (curr_mode_no, step_scale))
                        yield curr_dir*(curr_mode_no + 1), 0, current_pos, 'slow', currtps
#                    else:
#                        self.logmsg('delay mode change. pos: %d, scale: %d, calc: %d, ' % (current_pos, step_scale, current_pos % (step_scale/2)))
                currtick=1/currtps/step_fact
                current_pos += curr_dir*step_scale
#                self.logmsg('slower')
                yield None, currtick, current_pos, 'slow', currtps
            elif currtps < lmax_tps:                                       # go faster
                currtps += self.accel_tps * currtick
                if currtps > self.max_tps:                                 # clamp to max_tps
                    currtps = self.max_tps
#                    self.logmsg('max reached %5.3f' % currtps)
#                else:
#                    self.logmsg('faster %5.3f' % currtps)
                currtick = 1/currtps/step_fact
                current_pos += curr_dir*step_scale
                yield None, currtick, current_pos, 'fast', currtps
            else:                                                          # speed reached max for mode
                currtps += self.accel_tps * currtick
#                boundary=max(1,round(step_fact / self.step_levels[curr_mode_no+1][1]))
                boundary = self.max_microsteps/step_fact
#                print('***new factor: %d, max_micro: %d,  boundary: %d' % (self.step_levels[curr_mode_no+1][1], self.max_microsteps, boundary))
                if current_pos % boundary == 0:                       # change mode now
                    old_fact=step_fact
                    curr_mode_no += 1
                    curr_mode = self.step_levels[curr_mode_no]
                    step_fact = curr_mode[1]
                    step_scale = int(self.max_microsteps/step_fact)
                    lmin_tps = lmax_tps
                    lmax_tps = curr_mode[0]
#                    self.logmsg('change step mode to %d with scale now %5.3f, prev fact: %d, new fact: %d at pos: %d' % (curr_mode_no, step_scale, old_fact, step_fact, current_pos))
                    yield curr_dir*(curr_mode_no + 1), currtick, current_pos, 'fast', currtps
                    currtick = 1/currtps/step_fact
                else:
                    currtick = 1/currtps/step_fact
#                    self.logmsg('delay mode change. pos: %d, scale: %d, tps: %5.3f, tick: %5.3f' % (current_pos, step_scale, currtps, currtick))
                    current_pos += curr_dir*step_scale
                    yield None, currtick, current_pos, 'fast', currtps
        while currtps > self.start_tps and not self.crashing:   # stopped running, so check if need to slow down....
            currtps -= self.accel_tps * currtick                   # not exactly right cos ramp is finite steps, but simple calc
            if currtps < lmin_tps:                                 # time to switch microstep mode?
                boundary=max(1,round(step_fact / self.step_levels[curr_mode_no-1][1]))
                if current_pos % boundary == 0:                 # change mode now
                    curr_mode_no -= 1
                    curr_mode = self.step_levels[curr_mode_no]
                    step_fact = curr_mode[1]
                    step_scale = int(self.max_microsteps/step_fact)
                    lmax_tps = lmin_tps
                    lmin_tps = 0 if curr_mode_no == 0 else self.step_levels[curr_mode_no-1][0]
#                    self.logmsg('stopping - change step mode to %d with scale now %5.3f' % (curr_mode_no, step_scale))
                    yield curr_dir*(curr_mode_no + 1), 0, current_pos, 'slow', currtps
#                else:
#                    self.logmsg('delay mode change. pos: %d, scale: %d, calc: %d, ' % (current_pos, step_scale, current_pos % (step_scale/2)))
            currtick=1/currtps/step_fact
#            self.logmsg('stopping')
            if currtps >= self.start_tps:
                current_pos += curr_dir*step_scale
                yield None, currtick, current_pos, 'slow', currtps
        print('tickgen completed')
