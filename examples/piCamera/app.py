import camHandler
import sys, time, json, pathlib, traceback
sys.path.append('../..')
import flaskextras
from flask import Flask, redirect, url_for, Response, request, jsonify, render_template, send_from_directory
from markupsafe import escape

class web_picam(flaskextras.webify, camHandler.cameraManager, flaskextras.Webpart):
    """
    class to web-enable the app, inherits from the app's class and from flaskestras.webify which adds some useful code to handle
    dynamic field updates (these work in conjunction with the standard javascript 'pymon.js')
    """
    saveable_defaults=camHandler.cameraManager.saveable_defaults.copy()
    saveable_defaults.update(flaskextras.Webpart.saveable_defaults)
    def __init__(self,
                settings='default.json',
                parts=(('livestream', 'camStreamer', 'Streamer', {}),
                       ('vidrecord', 'camRecorder', 'VideoRecorder',{}),
                       ('vidproc','camGenerator','Web_Image_processor',{}),)):
        """
        """
        self.settings_folder=pathlib.Path('~/camfiles').expanduser()
        with_settings={}
        settingsfile=(self.settings_folder/settings).with_suffix('.json')
        if settingsfile.is_file():
            print('using settings from', settingsfile)
            try:
                with settingsfile.open('r') as sfo:
                    with_settings=json.load(sfo)
            except:
                with_settings={}
                traceback.print_exc()
                print('!!!!App started without saved settings', file=sys.stderr)
        else:
            print('no settings found', settingsfile)
        updateindex={'index': self.index_updates}
        flaskextras.webify.__init__(self, __name__, updateindex, page_templates={'/index.html': 'index.html'})
        flaskextras.Webpart.__init__(self, parent=None, settings=with_settings)
        camHandler.cameraManager.__init__(self, parts=parts, settings=with_settings)
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
        sf=(self.settings_folder/request.args.get('f')).resolve().with_suffix('.json')
        if self.settings_folder in sf.parents:
            with sf.open('w') as sfo:
                sfo.write(json.dumps(self.get_settings(), indent=3, sort_keys=True))
            return jsonify((('savesetts', {'value': 'Save settings', 'disabled': False}),))
        else:
            return jsonify((('savesetts', {'value': 'Save settings', 'disabled': False}),
                            ('alert', "Ooh! Naughty - you can't save there"),))

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
