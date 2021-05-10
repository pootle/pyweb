#!/usr/bin/python3
"""
streams images to (multiple) clients from the picamera by calling start_recording and passing over successive frames.

It stops recording when there have beem no active clients for the timeout period
"""
import time, threading, io, sys

from enum import Flag, auto

from picamera.exc import PiCameraNotRecording

class Streamer():
    """
    This class is written to work with camHandler and provide an mjpeg stream from the camera on demand, typically.
    to provide a live stream from the camera (but any source of a sequence of jpegs could be used).
    
    It allows multiple streams to be driven from the source stream.
    """
    def __init__(self, camhand):
        """
        initialisation just sets up the vars used.
        """
        self.ls_width = 640                     # resize the camera feed for streaming
        self.ls_height = 480
        self.ls_frame_skip = 0                  # number of camera frames to skip between output frames
        self.ls_skip_count = self.ls_frame_skip  # counter for frame skip
        self.ls_timeout = 120                   # set a 2 minute timeout - stops recording after no frames have been read for this time
        self.ls_lastactive = 0                  # last time a frame was read
        self.ls_protect=threading.Lock()
        self.ls_condition=None
        self.camhand=camhand
        self.monitor_active = False

    def get_stream(self):
        """
        When we get a stream request, check if already running and if not start everything up and return self.
        
        This is called by an http handler request thread.
        
        THE HTTP thread (there can be several) then loops calling nextframe
        
        Note that start_recording internally runs a thread that will call write as each frame arrives.
        
        This also starts a thread to monitor activity. Once all running streams have stopped, we call stop_recording and release resoources
        
        The monitor thread will also exit at this point
        """
        with self.ls_protect:
            if self.ls_condition is None:
                resize=self.camhand.get_resize([self.ls_width, self.ls_height])
                self.ls_condition = threading.Condition()
                self.ls_buffer = io.BytesIO()
                self.ls_lastactive = time.time()
                self.ls_splitter_port=self.camhand._getSplitterPort(self)
                self.ls_picam=self.camhand.start_camera()
                self.ls_monthread=threading.Thread(name='livestream', target=self.monitor)
                self.ls_picam.start_recording(self, format='mjpeg', splitter_port=self.ls_splitter_port, resize=resize)
                self.monitor_active=True
                self.ls_monthread.start()
                self.ls_framecount = 0
            return self

    def write(self, buf):
        """
        called by the camera software from its own thread.
        
        record the next frame and notify all those waiting
        """
        if buf.startswith(b'\xff\xd8'):  # looks like we always get a complete frame, soo we don't need to be clever
            if self.ls_skip_count <= 0: 
                # New frame, set it as current frame and wake up all streams 
                with self.ls_condition:
                    self.ls_frame=buf
                    self.ls_condition.notify_all()
                    self.ls_skip_count = self.ls_frame_skip
            else:
                self.ls_skip_count -= 1
        else:
            prints('boops', file=sys.stderr)
        return len(buf)

    def nextframe(self):
        """
        The http handler thread(s) calls this to get each successive frame.
        
        It waits for a new frame to arrive, then updates the lastactive timestamp and returns the frame
        """
        with self.ls_condition:
            self.ls_condition.wait()
            self.ls_lastactive=time.time()
        self.ls_framecount += 1
        if self.ls_framecount % 20==0:
            print('Framecount: %d' % self.ls_framecount, file=sys.stderr)
        return self.ls_frame, 'image/jpeg', len(self.ls_frame)

    def monitor(self):
        while True:
            try:
                self.ls_picam.wait_recording(2, splitter_port=self.ls_splitter_port)
            except PiCameraNotRecording:
                self.camhand._releaseSplitterPort(self, self.ls_splitter_port)
                self.splitter_port=None
                self.ls_condition=None
                break
            except:
                print('wait recording failed', file=sys.stderr)
                self.app._releaseSplitterPort(self, self.splitter_port)
                self.ls_splitter_port=None
                self.ls_condition=None
                raise
            if time.time() > self.ls_lastactive + self.ls_timeout or not self.monitor_active:
                with self.ls_protect:
                    self.ls_picam.stop_recording(splitter_port=self.ls_splitter_port)
                    self.camhand._releaseSplitterPort(self, self.ls_splitter_port)
                    self.ls_splitter_port=None
                    self.ls_condition = None
                break
        print('camera stream monitor thread exits', file=sys.stderr)
