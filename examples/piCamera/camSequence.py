#!/usr/bin/python3
"""
Base for camera image stream processing 
"""
from picamera.array import PiRGBAnalysis
from camHandler import getclass
import time, threading, traceback, pathlib, png
from flask import jsonify, request

class Image_sequence():
    """
    This class is written to work with camHandler and provides a sequence of rgb or yuv images from the camera.
    
    Create your own handler class by inheriting from picamera.array.PiRGBAnalysis and overriding the analyze method.
    (see https://picamera.readthedocs.io/en/release-1.13/recipes2.html#unencoded-video-capture)
    """
    def __init__(self, parent, proc_module, proc_class):
        """
        initialisation just sets up the vars used. These values can be changed at any time, but only take effect when 
        "run" is called. If already running, changes only take effect after stopping and running again.
        """
        self.is_width = 64                    # resize the camera feed for streaming
        self.is_height = 48
        self.is_folder = '~/camfiles/masks'
        self.is_splitter_port=None
        self.is_picam=None
        self.camhand=parent
        self.is_running=None
        self.is_status='off'  
        self.is_monthread=None
        self.proc_class = getclass(proc_module, proc_class)
        parent.add_url_rule('/flip-proc-frames', view_func=self.flip_processing, methods=('REQUEST',))
        parent.add_url_rule('/fetchmasksize', view_func=self.fetch_mask_size)
        parent.add_url_rule('/savemask', view_func=self.save_mask, methods=('POST',))
        parent.add_url_rule('/fetchmask', view_func=self.fetch_mask)

    def flip_processing(self):
        print('do it now')
        if self.is_running:
            self.is_running=False
            rdat=(('frameproc_btn',{'value': 'start frame proc', 'disabled': False, 'bgcolor': None}),)
        else:
            self.run(self.proc_class)
            rdat=(('frameproc_btn',{'value': 'stop processing', 'disabled': False, 'bgcolor': "red"}),)
        return jsonify(rdat)
        
    def fetch_mask_size(self):
        return jsonify({'width': self.is_width, 'height': self.is_height})

    def fetch_mask(self):
        mpath=pathlib.Path(self.is_folder).expanduser()
        mname=request.args.get('name')
        fpath=(mpath/mname).with_suffix('.png')
        if fpath.is_file():
            imgpng=png.Reader(str(fpath))
            img=imgpng.asDirect()
            dat=[list(x) for x in img[2]]
            res={'width': img[0], 'height': img[1], 'mask': dat, 'name': mname}
            return jsonify(res)
        else:
            return jsonify({'msg':'no sudh file: %s' % str(fpath)})
#        {'width':99, 'height': 99, 'mask': stuff, 'name': }

    def save_mask(self):
        print(request.json['name'])
        mpath=pathlib.Path(self.is_folder).expanduser()
        mpath.mkdir(parents=True, exist_ok=True)
        fpath=(mpath/request.json['name']).with_suffix('.png')
        print('saving to %s' % fpath)
        maskdata=request.json['mask']
        pw = png.Writer(len(maskdata[0]), len(maskdata), greyscale=True, bitdepth=1)
        with fpath.open('wb') as fff:
            pw.write(fff,maskdata)
        return jsonify({'message': 'saved to %s' % fpath})

    def run(self, handlerclass):
        """
        Starts the camera if necessary, the runs a new thread which sets up an instance of the passed handler class.
        
        The thread loops on wait_recording to catch any errors and exits after "stop" is called.
        
        The handler class' analyze' method will be called for each frame in turn.
        """
        self.is_splitter_port=self.camhand._getSplitterPort(self)
        self.is_picam=self.camhand.start_camera()
        self.is_monthread = threading.Thread(name='analyze', target=self.monitor, args=[handlerclass])
        self.is_monthread.start()

    def monitor(self, handlerclass):
        fsize=(self.is_width, self.is_height)
        with handlerclass(self.camhand, fsize) as handler:
            self.is_picam.start_recording(handler, format='rgb', resize=fsize, splitter_port=self.is_splitter_port)
            print('video stream started at ', (self.is_width, self.is_height))
            self.is_running=True
            started=time.time()
            lastsecs = 0
            self.is_status="active: %d seconds" % lastsecs 
            try:
                while self.is_running:
                    self.is_picam.wait_recording(1, splitter_port=self.is_splitter_port)
                    tnow=time.time()
                    if int(tnow-started) > lastsecs+5:
                        lastsecs += 5
                        self.is_status="active: %d seconds" % lastsecs 
            except:
                print('argh')
                traceback.print_exc()
            finally:
                self.is_picam.stop_recording(splitter_port=self.is_splitter_port)
                self.is_monthread=None
                self.is_picam=None
                self.camhand._releaseSplitterPort(self, self.is_splitter_port)
                self.is_running=False
                print("frame sequence processor stops")

class simple(PiRGBAnalysis):
    def __init__(self, camhand, fsize):
        super().__init__(camhand.picam, size=fsize)
        self.camhand=camhand
        self.fc=0

    def analyze(self,nar):
        self.fc +=1
        if self.fc % 25 == 0:
            print('%d frames' % self.fc)
            print(nar.shape)
            print('current iso', self.camhand.picam.iso)

#    def tune_exposure(self, nar):
#        if self.fc == 50:
#            print(self.camhand.cam_iso)
#        if self.fc > 50 and self.fc % 5 == 0:
#            print('current iso', self.camhand.picam.iso)
