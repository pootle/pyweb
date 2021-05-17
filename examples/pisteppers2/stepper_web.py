#!/usr/bin/python3

import sys
sys.path.append('../..')
import stepgenconstacc as sg, stepperunid as sud, flaskextras, netinf
import time, pigpio
from flask import redirect, url_for

from unidsettings import stepping_params, drivepins

class webstepper(flaskextras.webify, sud.Unipolar_direct):
    def __init__(self):
        """
        in addition to constructing the base classes, initialise a couple of variables used to run the 
        progress bar.
        """
        steps_per_unit=2049*4*8/360
        pio=pigpio.pi(show_errors=False)
        if pio.connected:
            sud.Unipolar_direct.__init__(self, pigp=pio, 
                        drvpins=drivepins, 
                        holdpower=0.3, 
                        stepping_params=stepping_params,
                        unit_scale = steps_per_unit,
                        current_pos = 0)
            netinf.showserverIP(5000)
            updateindex={'index': self.index_updates}
            flaskextras.webify.__init__(self, __name__, updateindex)
        else:
            raise RuntimeError('pigpio init failure - is the daemon running?') 

    def index_updates(self):
        """
        called at regular intervals from the web server code for the index page with fields that need updating
        """
        self.is_active()
        return [
            ('current_pos', {'value': '%5.1f' % self.current_pos}),
            ('drive_state', {'value': self.drive_state}),
            ('drive_mode',  {'value': self.drive_mode}),
            ('max_tps',     {'value': '%7.2f'%self.max_tps}),
            ('current_tps', {'value': '%9.2f' % self.current_tps}),
            ('acceleration',{'value': '%7.2f' % self.acceleration}),
            ]

    @property
    def step_style_LIST(self):
        return {'values': list(self.stepping_params.keys())}

    def start_stop_motor(self,id):
        if self.drive_state=='off':
            self.run_motor(self.step_style)
            rdat=((id,{'value': 'STOP', 'bgcolor': 'red', 'disabled': False}),)
        else:
            self.run_motor('off')
            rdat=((id,{'value': 'Run Motor', 'bgcolor': None, 'disabled': False}),)
        return rdat

onemotor = webstepper()

@onemotor.route('/')
def redir():
    return redirect(url_for('index'))

@onemotor.route('/index')
def index():
    with open('templates/index.html', 'r') as tfile:
        template=tfile.read()
    return template.format(app=onemotor)    
    