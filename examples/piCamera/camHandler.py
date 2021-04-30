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

class cameraManager():
    """
    This class prepares all the settings that can be applied to a picamera.PiCamera and manages the running camera
    with its associated activities.
    
    It sets up for 4 potential video splitter ports, and initialises them to None to show they are unused.
    """
    def __init__(self, parts=('livestream', 'vidrecord')):
        """
        Runs the camera and everything it does as well as other camera related activities
        """
        self.picam=None
        self.cameraTimeout=None
        self.activityports=[None]*4
        self.running=True
        # keep a bunch of attributes about camera settings so the camera doesn't need to be open
        self.picam=None             # set when camera is running, cleared when stopped
        self.cam_framerate = 10
        with picamera.PiCamera() as tempcam:
            self.camType=tempcam.revision
            self.cam_resolution = cam_resolutions[self.camType][1]
            self.cam_resolution_LIST = {'display':cam_resolutions[self.camType][0]}
            self.cam_u_width = self.cam_resolution[0]       # when camera resolution is special, specific values here are used
            self.cam_u_height = self.cam_resolution[1]
            self._cam_rotation = tempcam.rotation
            self.cam_rotation_LIST = {'display': ('0', '90', '180', '270')}
            self._cam_hflip = tempcam.hflip
            self.cam_hflip_LIST = {'display': ('off', 'on'), 'values': (False, True)}
            self._cam_vflip = tempcam.vflip
            self.cam_vflip_LIST = {'display': ('off', 'on'), 'values': (False, True)}
            for cam_attr in ('awb_mode', 'exposure_mode', 'meter_mode', 'drc_strength'):
                 self.make_attr_list(cam_attr, tempcam)
            self.cam_exposure_compensation_LIST = {
                'values': list(range(-25, 26)),
                'display': ('-4 1/6', '-4', '-3 5/6', '-3 2/3', '-3 1/2', '-3 1/3', '-3 1/6', '-3', '-2 5/6', '-2 2/3', '-2 1/2', '-2 1/3', '-2 1/6', '-2', 
                            '-1 5/6', '-1 2/3', '-1 1/2', '-1 1/3', '-1 1/6', '-1', '-5/6', '-2/3', '-1/2', '-1/3', '-1/6', '0', '1/6', '1/3', '1/2', '2/3', '5/6',
                            '1', '1 1/6', '1 1/3', '1 1/2', '1 2/3', '1 5/6', '2', '2 1/6', '2 1/3', '2 1/2', '2 2/3', '2 5/6', 
                            '3', '3 1/6', '3 1/3', '3 1/2', '2 2/3', '3 5/6', '4', '4 1/6') 
            }
            for cam_attr in ('contrast', 'brightness', 'exposure_compensation'):
                setattr(self, '_cam_'+cam_attr, getattr(tempcam, cam_attr))
                catt='_cam_'+cam_attr
            self.zoom_left, self.zoom_top, zoom_width, zoom_height = tempcam.zoom
            self.zoom_right = self.zoom_left+zoom_width
            self.zoom_bottom = self.zoom_top+zoom_height
#        self.live_view_on = False
        self.cam_state = self.cam_summary = 'closed'
        self.autoclose = True
        self.auto_close_timeout = 10
        self.picture_folder = '~/Photos'
        self.picture_path = pathlib.Path(self.picture_folder).expanduser()
        self.picture_path.mkdir(parents=True, exist_ok=True)
        self.picture_filename='picam%y-%m-%d %H:%M:%S.jpg'
        if 'livestream' in parts:
            import camStreamer
            self.streamer = camStreamer.Streamer(self)
        else:
            self.streamer = None
        if 'vidrecord' in parts:
            import camRecorder
            self.vidrecord = camRecorder.VideoRecorder(self)
            self.vidtrigger=None
        else:
            self.vidrecord = None
            self.vidtrigger=None

    def make_attr_list(self, attr, picam):
        alist=getattr(picam, attr.upper()+'S')
        setattr(self, 'cam_'+attr+'_LIST', {
            'display': [str(choice) for choice in alist.keys()],
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
        return self.cam_exposure_compensation_LIST['display'][self._cam_exposure_compensation+25]

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

    def start_camera(self):
        """
        starts the camera using the settings originally passed to the constructor. Does nothing if the camera is already running.
        """
        if self.picam is None:
            cres = '%dx%d' % (self.cam_u_width, self.cam_u_height) if self.cam_resolution=='special' else self.cam_resolution
            self.picam=picamera.PiCamera(
                    resolution=cres,
                    framerate=self.cam_framerate)
            for camval in ('rotation', 'hflip', 'vflip', 'awb_mode', 'exposure_mode', 'meter_mode', 'drc_strength', 'exposure_compensation'):
                setattr(self.picam, camval, getattr(self, '_cam_'+camval))
            self.set_zoom()
            self.cam_state= 'open'
            checkfr=self.picam.framerate
            self.cam_summary = 'open: (%s) %4.2f fps, sensor mode: %d' % (self.picam.resolution, checkfr.numerator/checkfr.denominator, self.picam.sensor_mode)
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
            zp=self.zoom_left, self.zoom_top, self.zoom_right-self.zoom_left, self.zoom_bottom-self.zoom_top
            print('set zoom', zp)
            self.picam.zoom=(zp)

    def single_image(self):
        """
        temporary... takes a single photo from the camera
        """
        self.start_camera()
        filename=self.picture_path/time.strftime(self.picture_filename, time.localtime())
        self.picam.capture(str(filename))

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

    def get_cam_stream(self):
        return self.streamer.get_stream() if not self.streamer is None else None

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



    def liveviewupd(self, watched, agent, newValue, oldValue):
        if watched.getIndex() == 1:
            # turn on live view
            self.startCamera()
            time.sleep(.3)
            self.picam.start_preview()
        else:
            if not self.picam is None:
                self.picam.stop_preview()

    def force_close(self, oldValue, newValue, agent, watched):
        self.stopCamera()

    def monitorloop(self):
        self.log(wv.loglvls.INFO,"cameraManager runloop starts")
        camtimeout=None
        while self.running:
            time.sleep(2)
            if self.picam:
                self.cam_exp_speed.getValue()
                self.cam_analog_gain.getValue()
                self.cam_digital_gain.getValue()
                if self.cam_autoclose.getIndex() > 0:
                    if self.live_view.getIndex() == 0:
                        for port in self.activityports:
                            if port:
                                break
                        else:
                            if camtimeout is None:
                                camtimeout=time.time()+20
                            elif time.time() > camtimeout: 
                                self.stopCamera()
                                camtimeout=None
        self.log(wv.loglvls.INFO,"cameraManager runloop closing down")
        self.stopCamera()
        self.log(wv.loglvls.INFO,"cameraManager runloop finished")

    def startDetectStream(self):
        return None

    def flipActivity(self, actname, withport, start=None, **kwargs):
        """
        starts and stops activities on demand
        
        actname:   name of the activity
        
        actclass:  class to use to create the activity
        
        withport:  if true, a splitter port is allocated and passed to the activity
        
        start   :  if True then the activity is started if not present, otherwise no action
                   if False then the activity is stopped if present, otherwise no action is taken
                   if None then the activity is stopped if present else it is started
        """
        if actname in self.activities and not start is True:
            self.activities[actname].requestFinish()
        elif not actname in self.activities and not start is False:
            if withport:
                self.startPortActivity(actname=actname, **kwargs)
            else:
                self.startActivity(actname=actname, **kwargs)

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
