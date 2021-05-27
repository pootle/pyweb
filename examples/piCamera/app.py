import camHandler, camSequence
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
    def __init__(self,
                parts=(('livestream', 'camStreamer', 'Streamer', {}),
                       ('vidrecord', 'camRecorder', 'VideoRecorder',{}),
                       ('vidproc','camSequence','Image_sequence',{'proc_module': 'camSequence', 'proc_class': 'simple'}),)):
        """
        """
        updateindex={'index': self.index_updates}
        flaskextras.webify.__init__(self, __name__, updateindex)
        camHandler.cameraManager.__init__(self, parts=parts)
        self.add_url_rule('/save_app_sets', view_func=self.save_app_setts, methods=('REQUEST',))

    def index_updates(self):
        """
        called at regular intervals from the web server code for an active page with fields that need updating.
        
        There is only 1 page in this app ('index') and it provides updates for 2 fields (only fields which
        have actually changed value since the last update are sent to the web browser).
        """
        return [
            ('cam_summary', {'value':self.cam_summary}),
            ('vr_status',   {'value':self.cparts['vidrecord'].vr_status}),
            ('vr_activefile',{'value':self.cparts['vidrecord'].vr_activefile }),
        ]

    def save_app_setts(self):
        print(self.get_settings())
        return jsonify((('savesetts', {'disabled': False}),))

    @property
    def select_res(self):
        return make_subselect(
                values=camHandler.cam_resolutions[self.camType],
                selected=self.cam_resolution)

camapp = web_picam()

@camapp.route('/')
def redir():
    return redirect(url_for('index'))

@camapp.route('/index')
def index():
    with open('templates/index.html', 'r') as tfile:
        template=tfile.read()
    return template.format(app=camapp)    
