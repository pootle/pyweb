#!/usr/bin/python3
"""
Module to run the camera in video mode with up to 4 differently purposed streams.

each stream can be independently started and stopped. The 4 streams are intended to be used for any combination of:

    streaming live video - simply using mjpeg
    watching for movement - continuously capture (fairly small) images and check for 'movement'
    triggered recording once movement is detected - records while 'movement' detected plus few seconds before and after
    timelapse photos

The camera is setup at a specific resolution and framerate - typically the resolution will use the whole sensor, binned to 
reduce the working size, and a framerate to suit the fastest use case.

The different streams then resize the image to an appropriate size for the particular task. As the GPU does the resizing it is
fast and low latency.

The program uses watcher derived variables to enable easy integration with front end software
"""

import picamera, time
import threading, json, pathlib, fractions

# built in "standard" resolutions - indexed by the camera revision
HQcam=(('special', '4056x3040', '2028x1520', '1012x760', '1080p', '720p', '480p'),'1012x760')
cam_resolutions={
    'ov5647' : (('special', '3280x2464', '1640x1232', '1640x922', '1920x1080', '1280x720', '640x480'),
                '1640x1232'),
                
    'imx219' : (('special', '2592x1944','1296x972','640x480'),
                '1296x972'),
    'testc'  : HQcam,
    'imx477' : HQcam
}

import importlib, traceback

def getclass(modulename, classname):
    """
    fetches a class given the (text) name of the module and class)
    """
    return getattr(importlib.import_module(modulename), classname)

class appHandler():
    """
    some basic housekeeping that might be useful elsewhere
    """
    def __init__(self, parts, settings=None):
        """
        sets up optional extra components for the app that are placed in a dict - self.cparts
        """
        self.cparts={}
        for partname, modulename, partclass, partparams in parts:
            try:
                self.cparts[partname]=getclass(modulename, partclass)(parent=self, **partparams)
            except:
                print('failed to setup component: modulename %s, partclass %s, partparams %s' % (modulename, partclass, partparams))
                traceback.print_exc()
        print('set up with parts', list(self.cparts.keys()))

    def get_settings(self):
        """
        retrieves all the user-setable values for app and component settings as dicts, lists, ints, floats and strings, such
        that they can be json converted to saved to a file for later re-use.
        """
        appatts={attname: getattr(self, attname) for attname in self.saveable_settings}
        appatts['cparts'] = {}
        for partname, part in self.cparts.items():
            if hasattr(part,'saveable_settings'):
                appatts['cparts'][partname]={pattname: getattr(part,pattname) for pattname in part.saveable_settings}
        return appatts

class cameraManager(appHandler):
    """
    This class prepares all the settings that can be applied to a picamera.PiCamera and manages the running camera
    with its associated activities.
    
    It sets up for 4 potential video splitter ports, and initialises them to None to show they are unused.
    
    Attributes of the real camera (instance of piCamera class) are reflected into this class' attributes with '_cam_' prefixed.
    This allows the values to be remembered even when the camera is not running (no instance of the class).
    These attributes are then read / set by users of this class using the attributes 'cam_' + attribute ('no prefix underscore).
    
    For most attributes (those that the camera does not change itself), this class' value is returned, and when set, the set value
    is saved and if the camera is open, the camera's corresponding attribute is also set.
    
    For attributes that the camera can itself change.  
    """
    saveable_settings=(
        'cam_framerate', 'cam_resolution', 'cam_contrast', 'cam_brightness', 'cam_exposure_compensation', 'cam_rotation', 'cam_hflip', 'cam_vflip', 'cam_iso',
        'cam_shutter_speed', 'cam_exposure_speed', 'cam_awb_mode', 'cam_exposure_mode', 'cam_meter_mode', 'cam_drc_strength', 
        'cam_zoom_left', 'cam_zoom_top', 'cam_zoom_right', 'cam_zoom_bottom'
    )
    
    def __init__(self, **kwargs):
        """
        Runs the camera and everything it does as well as other camera related activities
        """
        self.picam=None
        self.cameraTimeout=None
        self.activityports=[None]*4
        self.running=True
        self.picam=None             # set when camera is running, cleared when stopped
        self.cam_framerate = 10
        with picamera.PiCamera() as tempcam:
            self.camType=tempcam.revision
            self.cam_resolution = cam_resolutions[self.camType][1]
            self.cam_resolution_LIST = {'values':cam_resolutions[self.camType][0]}
            self.cam_u_width = self.cam_resolution[0]       # when camera resolution is special, specific values here are used
            self.cam_u_height = self.cam_resolution[1]
            for cam_attr in ('contrast', 'brightness', 'exposure_compensation', 'rotation', 'hflip', 'vflip', 'iso', 'shutter_speed', 'exposure_speed'):
                setattr(self, '_cam_'+cam_attr, getattr(tempcam, cam_attr))
            self.cam_rotation_LIST = {'values': (0, 90, 180, 270), 'display': ('0', '90', '180', '270')}
            self.cam_hflip_LIST = {'display': ('off', 'on'), 'values': (False, True)}
            self.cam_vflip_LIST = {'display': ('off', 'on'), 'values': (False, True)}
            self.cam_iso_LIST = {'values': (0,100, 200, 320, 400, 500, 640, 800), 'display': ('auto','100', '200', '320', '400', '500', '640', '800')}
            for cam_attr in ('awb_mode', 'exposure_mode', 'meter_mode', 'drc_strength'):
                 self.make_attr_list(cam_attr, tempcam)
            self.cam_exposure_compensation_LIST = {
                'values': list(range(-25, 26)),
                'display': ('-4 1/6', '-4', '-3 5/6', '-3 2/3', '-3 1/2', '-3 1/3', '-3 1/6', '-3', '-2 5/6', '-2 2/3', '-2 1/2', '-2 1/3', '-2 1/6', '-2', 
                            '-1 5/6', '-1 2/3', '-1 1/2', '-1 1/3', '-1 1/6', '-1', '-5/6', '-2/3', '-1/2', '-1/3', '-1/6', '0', '1/6', '1/3', '1/2', '2/3', '5/6',
                            '1', '1 1/6', '1 1/3', '1 1/2', '1 2/3', '1 5/6', '2', '2 1/6', '2 1/3', '2 1/2', '2 2/3', '2 5/6', 
                            '3', '3 1/6', '3 1/3', '3 1/2', '2 2/3', '3 5/6', '4', '4 1/6') 
            }
            self.cam_zoom_left, self.cam_zoom_top, zoom_width, zoom_height = tempcam.zoom
            self.cam_zoom_right = self.cam_zoom_left+zoom_width
            self.cam_zoom_bottom = self.cam_zoom_top+zoom_height
        self.cam_state = self.cam_summary = 'closed'
        self.autoclose = True
        self.autoclose_timeout = 10
        super().__init__(**kwargs)

    def make_attr_list(self, attr, picam):
        alist=getattr(picam, attr.upper()+'S')
        setattr(self, 'cam_'+attr+'_LIST', {
            'values': [str(choice) for choice in alist.keys()],
        })
        current=getattr(picam, attr)
        setattr(self, 'cam_'+attr, current)

    @property
    def cam_rotation(self):
        return self._cam_rotation

    @cam_rotation.setter
    def cam_rotation(self, val):
        if not self.picam is None:
            self.picam.rotation = val
        self._cam_rotation = val

    @property
    def cam_hflip(self):
        return self._cam_hflip

    @cam_hflip.setter
    def cam_hflip(self, val):
        if not self.picam is None:
            self.picam.hflip = val
        self._cam_hflip = val

    @property
    def cam_vflip(self):
        return self._cam_vflip

    @cam_vflip.setter
    def cam_vflip(self, val):
        if not self.picam is None:
            self.picam.vflip = val
        self._cam_vflip = val

    @property
    def cam_awb_mode(self):
        return self._cam_awb_mode

    @cam_awb_mode.setter
    def cam_awb_mode(self, val):
        if not self.picam is None:
            self.picam.awb_mode = val
        self._cam_awb_mode = val

    @property
    def cam_exposure_mode(self):
        return self._cam_exposure_mode

    @cam_exposure_mode.setter
    def cam_exposure_mode(self, val):
        if not self.picam is None:
            self.picam.exposure_mode = val
        self._cam_exposure_mode = val

    @property
    def cam_meter_mode(self):
        return self._cam_meter_mode

    @cam_meter_mode.setter
    def cam_meter_mode(self, val):
        if not self.picam is None:
            self.picam.meter_mode = val
        self._cam_meter_mode = val

    @property
    def cam_drc_strength(self):
        return self._cam_drc_strength

    @cam_drc_strength.setter
    def cam_drc_strength(self, val):
        if not self.picam is None:
            self.picam.drc_strength = val
        self._cam_drc_strength = val

    @property
    def cam_contrast(self):
        return self._cam_contrast

    @cam_contrast.setter
    def cam_contrast(self, val):
        clampval = max(-100,min(100,val))
        if not self.picam is None:
            self.picam.contrast = val
        self._cam_contrast = val

    @property
    def cam_brightness(self):
        return self._cam_brightness

    @cam_brightness.setter
    def cam_brightness(self, val):
        clampval = max(0,min(100,val))
        if not self.picam is None:
            self.picam.brightness = val
        self._cam_brightness = val

    @property
    def cam_exposure_compensation(self):
        return self._cam_exposure_compensation

    @cam_exposure_compensation.setter
    def cam_exposure_compensation(self, val):
        if isinstance(val, str):
            ecval=self.cam_exposure_compensation_LIST['display'].index(val)-25
        else:
            ecval = max(-25, min(35,val))
        if not self.picam is None:
            print('setting exposure compensation', ecval)
            self.picam.exposure_compensation = ecval
        self._cam_exposure_compensation = ecval

    @property
    def cam_iso(self):
        return self._cam_iso

    @cam_iso.setter
    def cam_iso(self, val):
        if val in self.cam_iso_LIST['values']:
            newval=val
        elif val in self.cam_iso_LIST['display']:
            newval= self.cam_iso_LIST[self.cam_iso_LIST['display'].index(val)]
        else:
            raise ValueError('%s is not an appropriate value for iso' % val)
        if not self.picam is None:
            self.picam.iso = newval
        self._cam_iso = newval
        
    @property
    def cam_shutter_speed(self):
        return self._cam_shutter_speed

    @cam_shutter_speed.setter
    def cam_shutter_speed(self, val):
        if not self.picam is None:
            self.picam.shutter_speed = val
        self._cam_shutter_speed = val

    @property
    def cam_exposure_speed(self):
        if not self.picam is None:
            self._cam_exposure_speed=self.picam.exposure_speed
        return self._cam_exposure_speed

    def start_camera(self):
        """
        starts the camera using the settings originally passed to the constructor. Does nothing if the camera is already running.
        """
        if self.picam is None:
            cres = '%dx%d' % (self.cam_u_width, self.cam_u_height) if self.cam_resolution=='special' else self.cam_resolution
            self.picam=picamera.PiCamera(
                    resolution=cres,
                    framerate=self.cam_framerate)
            for camval in ('rotation', 'hflip', 'vflip', 'awb_mode', 'exposure_mode', 'meter_mode', 'drc_strength', 'exposure_compensation', 'iso', 'contrast', 'brightness', 'shutter_speed'):
                setattr(self.picam, camval, getattr(self, '_cam_'+camval))
            self.set_zoom()
            self.cam_state= 'open'
            checkfr=self.picam.framerate
            self.cam_summary = 'open: (%s) %4.2f fps, sensor mode: %d' % (self.picam.resolution, checkfr.numerator/checkfr.denominator, self.picam.sensor_mode)
            monthread=threading.Thread(name='activity_mon', target=self.monitor)
            monthread.start()
        return self.picam

    def stop_camera(self):
        """
        stops the camera and releases the associated resources . Does nothing if the camera is not active
        """
        if not self.picam is None:
            try:
                self.picam.close()
            except Exception as e:
                print("camera didn't want to close!", str(e)) 
            self.picam=None
            self.cam_state = 'closed'
            self.cam_summary = 'closed'

    def set_zoom(self):
        if self.picam:
            zp=self.cam_zoom_left, self.cam_zoom_top, self.cam_zoom_right-self.cam_zoom_left, self.cam_zoom_bottom-self.cam_zoom_top
            print('set zoom', zp)
            self.picam.zoom=(zp)

    def _getSplitterPort(self, activity):
        """
        finds the camera port and allocates it, returning the number, None if problem
        """
        try:
            freeport=self.activityports.index(None)
        except ValueError:
            print('unable to find free port for activity %s' % activity)
            return None
        self.activityports[freeport]=activity
        return freeport
       
    def _releaseSplitterPort(self, activity, s_port):
        assert self.activityports[s_port] is activity
        self.activityports[s_port] =None

    def get_resize(self, targetsize):
        """
        returns a reize tuple if the target size is smaller than the currently set size the camera is using, otherwise
        returns None
        """
        camsize=[int(nn) for nn in self.cam_resolution.split('x')]
        if targetsize==camsize or camsize[0] < targetsize[0] or camsize[1] < targetsize[1]:
            return None
        else:
            return targetsize


    def max_shutter(self):
        """
        returns the maximum value shutter speed can be set to given the framerate in use
        """
        return 1_000_000/self.cam_framerate

    def fetchsettings(self):
        """
        override the standard fetchsettings to add in settings for the activities
        """
        acts={}
        for actname, act in self.activities.items():
            acts[actname]=act.fetchsettings() if hasattr(act, 'fetchsettings') else {}
        setts=super().fetchsettings()
        setts['acts']=acts
        return setts

    def changeframerate(self, watched, agent, newValue, oldValue):
        if self.picam:
            self.log(wv.loglvls.INFO,"updating framrate on open camera to %5.3f" % newValue)
            camready=True
            for camuser in self.activityports:
                if not camuser is None:
                    if hasattr(camuser,'pausecamera'):
                        camuser.pausecamera()
                    else:
                        camready=False
            if camready:
                self.picam.framerate = newValue
            else:
                self.log(wv.loglvls.INFO, 'unable to change framerate - camera in use')
            for camuser in self.activityports:
                if not camuser is None:
                    if hasattr(camuser,'pausecamera'):
                        camuser.resumecamera()

    def force_close(self, oldValue, newValue, agent, watched):
        self.stopCamera()

    def monitor(self):
        print('start camera activity monitor')
        lastactive = time.time()
        while True:
            acts=sum([0 if ap is None else 1 for ap in self.activityports])
            if self.autoclose and acts == 0:
                if time.time() > lastactive + self.autoclose_timeout:
                    self.stop_camera()
                    break
            if acts > 0:
                lastactive = time.time()
            checkfr=self.picam.framerate
            self.cam_summary = 'open: (%s) %4.2f fps, sensor mode: %d, active_ports %d' % (self.picam.resolution, checkfr.numerator/checkfr.denominator, self.picam.sensor_mode, acts)
            time.sleep(2)
        print('end   camera activity monitor')

    def close(self):
        self.safeStopCamera()

    def safeStopCamera(self):
        self.running=False
        self.activities['camstream'].closeact()
        return        
        
        
        for actname, actob in self.activities.items():
            try:
                actob.closeact()
                self.log(wv.loglvls.INFO,'activity %s closed' % actname)
            except:
                self.log(wv.loglvls.WARN,'activity %s failed to close' % actname, exc_info=True, stack_info=True)
