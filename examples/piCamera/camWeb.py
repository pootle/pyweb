import camHandler
import sys, time, json
sys.path.append('../..')
import flaskextras
from flask import Flask, redirect, url_for, Response, request, jsonify
from markupsafe import escape

class web_picam(flaskextras.webify, camHandler.cameraManager):
    """
    class to web-enable the app, inherits from the app's class and from flaskestras.webify which adds some useful code to handle
    dynamic field updates (these work in conjunction with the standard javascript 'pymon.js')
    """
    def __init__(self):
        """
        """
        updateindex={'index': self.index_updates}
        flaskextras.webify.__init__(self, __name__, updateindex)
        camHandler.cameraManager.__init__(self)

    def index_updates(self):
        """
        called at regular intervals from the web server code for an active page with fields that need updating.
        
        There is only 1 page in this app ('index') and it provides updates for 2 fields (only fields which
        have actually changed value since the last update are sent to the web browser).
        """
        return [
            ('cam_summary', {'value':self.cam_summary}),
            ('vr_status',   {'value':self.vidrecord.vr_status}),
            ('vr_activefile',{'value':self.vidrecord.vr_activefile }),
            
        ]

    @property
    def select_res(self):
        return make_subselect(
                choices=camHandler.cam_resolutions[self.camType],
                selected=self.cam_resolution)

    def record_enable_flip(self, id):
        """
        method called from web browser front end - flips ready state
        """
        if getattr(self, 'vr_web_trigger', None) is None:
            print('TURN ON')
            self.vr_web_trigger=self.vidrecord.ready()
            rdat=((id,{'value': 'disable recorder', 'disabled': False, 'bgcolor': 'pink'}),
                  (id[:-1]+'2',{'disabled': False, 'bgcolor': None}))
        else:
            print('TURN OFF')
            self.vidrecord.unready(self.vr_web_trigger)
            self.vr_web_trigger=None
            rdat=((id,{'value': 'enable recorder', 'disabled': False, 'bgcolor': None}),
                  (id[:-1]+'2', {'value': 'record now', 'disabled': True, 'bgcolor': None}))
        return rdat

    def record_now(self, id):
        if self.vr_web_trigger.trig_on:
            self.vr_web_trigger.clear_trigger()
            rdat=((id,{'value': 'record now', 'bgcolor': None, 'disabled': False}),)
        else:
            self.vr_web_trigger.set_trigger()
            rdat=((id,{'value': 'STOP', 'bgcolor': 'red', 'disabled': False}),)
        return rdat

camapp = web_picam()

def camstreamgen():
    print('start camera stream', file=sys.stderr)
    camstream = camapp.get_cam_stream()
    while True:
        frame, conttype, datalen=camstream.nextframe()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@camapp.route('/camstream')
def live_camera_stream():
    return Response(camstreamgen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@camapp.route('/')
def redir():
    return redirect(url_for('index'))

@camapp.route('/index')
def index():
    with open('templates/index.html', 'r') as tfile:
        template=tfile.read()
    return template.format(app=camapp)    
