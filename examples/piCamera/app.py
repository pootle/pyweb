import camHandler
import sys, time, json, pathlib
sys.path.append('../..')
import flaskextras
from flask import Flask, redirect, url_for, Response, request, jsonify, render_template, send_from_directory
from markupsafe import escape

class web_picam(flaskextras.webify, camHandler.cameraManager, flaskextras.Webpart):
    """
    class to web-enable the app, inherits from the app's class and from flaskestras.webify which adds some useful code to handle
    dynamic field updates (these work in conjunction with the standard javascript 'pymon.js')
    """
    saveable_settings=camHandler.cameraManager.saveable_settings+flaskextras.Webpart.saveable_settings
    def __init__(self,
                parts=(('livestream', 'camStreamer', 'Streamer', {}),
                       ('vidrecord', 'camRecorder', 'VideoRecorder',{}),
                       ('vidproc','camGenerator','Web_Image_processor',{}),)):
        """
        """
        updateindex={'index': self.index_updates}
        flaskextras.webify.__init__(self, __name__, updateindex, page_templates={'/index.html': 'index.html'})
        flaskextras.Webpart.__init__(self, parent=None)
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
            ('cam_exposure_speed', {'value': self.cam_exposure_speed}),
            ('vr_status',   {'value':self.cparts['vidrecord'].vr_status}),
            ('vr_activefile',{'value':self.cparts['vidrecord'].vr_activefile }),
            ('gs_status', {'value': self.cparts['vidproc'].gs_status}),
            ('gs_frameproc_btn', {'value': 'start frame proc', 'bgcolor': None} if self.cparts['vidproc'].gs_frameproc_btn_text == 'start frame proc' 
                    else {'value': 'stop frame proc' , 'bgcolor': 'red'}),
        ]

    def save_app_setts(self):
        for kv in self.get_settings().items():
            print('%22s: %s' % kv)
        return jsonify((('savesetts', {'disabled': False}),))

    @property
    def select_res(self):
        return make_subselect(
                values=camHandler.cam_resolutions[self.camType],
                selected=self.cam_resolution)

camapp = web_picam()

maskfolder=pathlib.Path('/home/pi/camfiles/masks')

@camapp.route('/masks')
def maskfiles():
    files = [afile.name for afile in  maskfolder.iterdir() if afile.is_file() and afile.suffix == '.png']
    return render_template('files.html',files=files, header="available mask files", basep='maskfile')

@camapp.route('/maskfile/<filename>')
def maskfile(filename):
    target=maskfolder/filename
    if not target.is_file():
        abort(404, "I'm sorry Dave, I couldn't find that file")
    else:
        return send_from_directory(directory= str(maskfolder), filename= filename, as_attachment=True)
