#!/usr/bin/python3

import sys
sys.path.append('../..')
import stepgenconstacc as sg, stepperunid as sud, simpleweb, netinf
import time, pigpio, threading

from unidsettings import stepping_params, drivepins

class webstepper(sud.Unipolar_direct, simpleweb.webify):
    def get_pages(self):
        """
        This method is called by the web server as it starts. It returns the list of pages the app will
        respond to and details how to handle each of them
        """
        return {
            'GET': {
                ''              : ('redirect', '/index.html'),
                'index.html'    : ('app_page', {'template': 'index.html'}),
            },
        }

    def get_updates(self, pageid):
        """
        called at regular intervals from the web server code for an active page with fields that need updating
        """
        self.is_active()
        if pageid == 'index':
            return [
                ('current_pos', '%5.1f' % self.current_pos),
                ('drive_state', self.drive_state),
                ('drive_mode', self.drive_mode),
                ('max_tps-f','%7.2f'%self.max_tps),
                ('current_tps', '%9.2f' % self.current_tps),
                ('acceleration-f', '%7.2f' % self.acceleration),
                ]
        return {}

    @property
    def dmselect(self):
        cc=['off']+list(self.stepping_params.keys())
        yyy = simpleweb.make_subselect(cc, self.step_style)
        return yyy

    @property
    def set_motor_mode(self):
        return None

    @set_motor_mode.setter
    def set_motor_mode(self, val):
        self.run_motor(val)

if __name__ == '__main__':
    steps_per_unit=2049*4*8/360
    pio=pigpio.pi(show_errors=False)
    if pio.connected:
        mot=webstepper( pigp=pio, 
                        drvpins=drivepins, 
                        holdpower=0.3, 
                        stepping_params=stepping_params,
                        unit_scale = steps_per_unit,
                        current_pos = 0)
        server = simpleweb.MultiServer(app=mot, port=8000)
        serverthread = threading.Thread(target=server.serve_forever, name='webserver')
        serverthread.start()
        netinf.showserverIP(8000)
        try:
            while True:
                time.sleep(3)
        except KeyboardInterrupt:
            server.tidyclose()
            mot.clean_stop()
            while mot.is_active():
                time.sleep(1)
            time.sleep(0.5)
            pio.stop()
            print('close on keyboard interrupt')
        except:
            mot.crash_stop()
            server.tidyclose()
            pio.stop()
            raise
    else:
        print('pigpio failed to open. Is the daemon running?')
    