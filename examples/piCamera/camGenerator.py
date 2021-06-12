#!/usr/bin/python3
"""
Base for camera image stream processing using a generator
"""
from picamera.array import PiRGBAnalysis
from camHandler import getclass
import time, threading, traceback, pathlib, png
from flask import jsonify, request
from flaskextras import Webpart
import numpy as np

class RGBhandler(PiRGBAnalysis):
    """
    extends the piCamera RGBAnalysis class to use a trigger as each frame received.
    
    This allows analysis code to use a generator (via get _generator) to process a sequence of images
    """
    def __init__(self, genmanager, fsize):
        super().__init__(genmanager.gs_picam, size=fsize)
        self.genmgr=genmanager
        self.fc=0

    def analyze(self,nar):
        with self.genmgr.gs_trigger:
            self.genmgr.lastframe=nar
            self.genmgr.gs_trigger.notify_all()
        self.genmgr.gs_framecount += 1

class Image_gen(Webpart):
    """
    This class is written to work with camHandler and provides a generator to "yield" sequences of rgb images from the camera.
    
    It sets up a single source stream from the camera, and can support multiple consumers
    
    This class has attributes that defines the basic parameters(such as width and height of image desired), and provides a 
    generator that yields images. Activity is monitored  and the source is automatically shut down after an inactivity period.
    
    Using a generator allows a processing function to run a loop with local variables to process each image and potentially
    to run through a sequence of different processing actions.

    See the class    
    
    """
    def __init__(self, handler=RGBhandler, **kwargs):
        """
        initialisation just sets up the vars used. These values can be changed at any time, but only take effect when 
        start_recording is next called. If already running, changes only take effect after stopping and running again.
        
        parent:
            camHandler instance managing the camera
        
        handler:
            class used to accept images from piCamera and notify all the "users" when an image is received. The default
        """
        super().__init__(**kwargs)
        self.gs_width = 64                  # resize the camera feed for streaming
        self.gs_height = 48
        self.gs_timeout = 30                # inactive time till stop recording
        self.gs_splitter_port=None
        self.gs_picam=None
        self.gs_handler = handler
        self.gs_status='off'  
        self.gs_camthread=None
        self.gs_protect=threading.Lock()
        self.gs_trigger=None
        self.gs_framecount = 0
        self.gs_last_active = 0

    def get_generator(self):
        """
        returns a generator, having setup a stream, trigger and monitor (in a new thread) if not already running. 
        This allows multiple consumers from a single stream. The stream is closed down after a timeout period of inactivity.
        """
        with self.gs_protect:
            if self.gs_trigger is None:
                self.gs_trigger = threading.Condition()
                self.gs_splitter_port=self.camhand._getSplitterPort(self)
                self.gs_picam=self.camhand.start_camera()
                self.gs_framecount = 0
                self.gs_recording_ok = True
                self.gs_monthread=threading.Thread(name='gen_monitor', target=self.monitor)
                self.gs_monthread.start()
        while self.gs_recording_ok:
            with self.gs_trigger:
                self.gs_trigger.wait()
            self.gs_lastactive=time.time()
            yield self.lastframe

    def monitor(self):
        """
        Typically sun in a separate thread, this fires up the camera, and then monitors the recording and whether images are being
        processed. Everything is shutdown after a period of inactivity.
        """
        fsize=self.camhand.get_resize((self.gs_width, self.gs_height))
        self.gs_picam.start_recording(self.gs_handler(self, fsize), format='rgb', resize=fsize, splitter_port=self.gs_splitter_port)
        print('frame sequence processor started with res ', fsize)
        started=time.time()
        lastsecs = 0
        self.gs_status="active: %d seconds" % lastsecs
        self.gs_last_active = time.time()
        try:
            tnow = time.time()
            while tnow - self.gs_timeout < self.gs_last_active:
                self.gs_picam.wait_recording(2, splitter_port=self.gs_splitter_port)
                tnow=time.time()
                if int(tnow-started) > lastsecs+5:
                    lastsecs += 5
                    self.gs_status="active: %d seconds" % lastsecs
        except:
            print('argh')
            self.gs_recording_ok = False
            traceback.print_exc()
        finally:
            self.gs_picam.stop_recording(splitter_port=self.gs_splitter_port)
            self.gs_monthread=None
            self.gs_picam=None
            self.camhand._releaseSplitterPort(self, self.gs_splitter_port)
            print("frame sequence processor stops")
            self.gs_status="off"

    def auto_expose(self, agen):
        """
        This method tries to set he exposure time / iso speed so that:
            iso is as low as possible
            exposure time is less than the max_shutter() (typically based on the requested video frame rate)
            the absolute max value of any pixel (RGB all separate) is between 220 and 245
        
        It assumes the camera settings are stable on entry and adjusts shutter speed  / iso then waits 2 seconds
        and repeats until in range at lowest practical iso
        
        on return, camera's iso and shutter speed should ensure the above conditions
        """ 
        fc=0
        max_shutter = self.camhand.max_shutter()
        cur_shutter = self.camhand.picam.exposure_speed
        print(' max shuuter speed at this framew rate: %d' % max_shutter)
        print('     exposure: %7.3f    time in 1/1000 second' % (cur_shutter/1000))
        ag=self.camhand.picam.analog_gain
        dg=self.camhand.picam.digital_gain
        print('iso: %d, analogue gain: %5.3f, digital gain: %5.3f' % (self.camhand.cam_iso, ag.numerator/ag.denominator, dg.numerator/dg.denominator))
        img=next(agen)
        maxrgb=np.max(img, axis=(0,1))
        print(maxrgb)
        absmax=max(maxrgb)
        while absmax < 220 or absmax > 245 and self.gs_procactive:
            if absmax > 245:
                if self.camhand.cam_iso > 100 and cur_shutter < max_shutter/4:
                    self.camhand.cam_iso = self.camhand.cam_iso // 2 
                new_shutter = cur_shutter // 2
            elif absmax < 100:
                new_shutter = cur_shutter * 2
            elif absmax < 160:
                new_shutter = round(cur_shutter * 1.5)
            elif absmax < 190:
                new_shutter = round(cur_shutter * 1.2)
            else:
                new_shutter = round(cur_shutter * 1.05)
            while new_shutter > max_shutter:
                new_iso = self.camhand.cam_iso * 2
                if new_iso > 800:
                    print('I am sorry dave I need a slower frame rate')
                    break
                self.camhand.cam_iso = new_iso
                new_shutter //= 2
            self.camhand.cam_shutter_speed = new_shutter
            tbase=time.time()
            img=next(agen)
            while time.time()-2 < tbase:
                img=next(agen)
            cur_shutter = self.camhand.picam.exposure_speed
            print('     exposure: %7.3f    time in 1/1000 second' % (cur_shutter/1000))
            ag=self.camhand.picam.analog_gain
            dg=self.camhand.picam.digital_gain
            print('iso: %d, analogue gain: %5.3f, digital gain: %5.3f' % (self.camhand.cam_iso, ag.numerator/ag.denominator, dg.numerator/dg.denominator))
            maxrgb=np.max(img, axis=(0,1))
            print(maxrgb)
            absmax=max(maxrgb)
        return True if self.gs_procactive else False                 

    def testtestx(self):
        agen=self.get_generator()
        fc=0
        while self.gs_procactive:
            img = next(agen)
            if fc%10==0:
                print(img.shape)
                print('%d frames' % fc)
                print('     exposure: %5.1f    time in 1/1000 second' % (self.camhand.picam.exposure_speed/1000))
                ag=self.camhand.picam.analog_gain
                print('analogue gain: %5.3f' % (ag.numerator/ag.denominator))
                ag=self.camhand.picam.digital_gain
                print(' digital gain: %5.3f' % (ag.numerator/ag.denominator))
                print(np.max(img, axis=(0,1)))
                print(np.mean(img, axis=(0,1)))
            fc += 1
        self.gs_testthread = None
        print('%d frames processed' % fc)

class Web_Image_processor(Image_gen):
    """
    extends the basic class with bits to support the web front end
    """
    def __init__(self, **kwargs):
        """
        setup to process images after a button push on the web front end.
        
        establishes an attribute for the thread (so we can see if it is active) and sets up so that a button push on the web page triggers Web_run_processor 
        """
        super().__init__(**kwargs)
        self.gs_testthread=None
        self.gs_frameproc_btn_text = 'start frame proc'
        self.camhand.add_url_rule('/testgen', view_func=self.Web_run_processor, methods=('REQUEST',)) # add the url handler to start processing a live stream

    def Web_run_processor(self):
        """
        Called when a button (with id frameproc_btn) on the web page is clicked
        """
        if self.gs_testthread is None:
            """If there is no active thread then start a thread and set the button to stop processing"""
            self.gs_procactive=True
            self.gs_testthread = threading.Thread(name='test proccing',target=self.processor)
            self.gs_testthread.start()
            self.gs_frameproc_btn_text = 'start frame proc'
            rdat = (('gs_frameproc_btn', {'value': self.gs_frameproc_btn_text, 'bgcolor': 'red', 'disabled': False}),)
        else: # otherwise just set a flag to stop the process an re-enable the button
            self.gs_procactive=False
            self.gs_frameproc_btn_text = 'stop frame proc'
            rdat = (('gs_frameproc_btn', {'value': self.gs_frameproc_btn_text, 'bgcolor': None, 'disabled': False}),)
        return jsonify(rdat)

    def processor(self):
        """
        a simple processor that just starts the camera / generator and waits 2 secs before calling auto_expose.
        
        Once suto expose completes it exits 
        """
        self.camhand.cam_iso=100
        agen = self.get_generator()
        tbase=time.time()
        while time.time()-2 < tbase:
            img=next(agen)
        self.auto_expose(agen)
        self.gs_testthread = None
        
