#!/usr/bin/python3
"""
This module enables videos to be recorded in response to several triggers. It can save video from a few seconds before the trigger
to several seconds after the trigger.
"""
import threading, queue, time, pathlib, shutil
from subprocess import Popen, PIPE

class VideoRecorder():
    """
    Records H264 on demand.
    
    It uses triggers to start recording. Each trigger is a flag that can be set to start recording and cleared to stop recording.
    Even if multiple flags are set, only a single recording is made.
    
    Initially it starts with status off; the camera is not in use.
    
    Call ready to ready the recorder. The camera is turned on if it is not already on (via camhandler) and the status updates
    to ready. If vr_backtime > 0 it starts recording to a circular buffer and the status updates to watching.
    vr_watch returns a trigger that can then be set to start recording and unset to stop recording.
    
    When recording starts the status updates to recording.
    """
    def __init__(self, camhand):
        """
        initialisation just sets up the vars used.
        """
        self.camhand=camhand
        self.vr_status = 'off'        #off, ready, waiting or recording
        self.vr_width = 640
        self.vr_height = 480
        self.vr_folder = '~/camfiles/videos'
        self.vr_filename='%y/%m/%d/%H_%M_%S'
        self.vr_backtime = 0                # target time for video to start before trigger
        self.vr_forwtime = 3                # target time for video to carry on after trigger stops
        self.vr_record_limit = 20           # max length for raw video recording (h.264 file)
        self.vr_max_merge = 3               # max number of raw video files to merge into 1 mp4 file
        self.vr_saveh264 = False            # if true, h264 are not deleted after conversion to mp4
        self.vr_splitter_port = None
        self.vr_recordcount = 0
        self.vr_lastrecording = 0
        self.vr_protect=threading.Lock()
        self.vr_monthread = None
        self.procthread = None
        self.vr_trig_queue=queue.Queue()
        # and this to support web browser front end
        self.vr_web_trigger=None

    def ready(self, timeout=300):
        """
        prepare video recording, and return a trigger instance
        """
        self.camhand.start_camera()    # starts the camera if not already running
        with self.vr_protect:
            newtrig = trigger(self.vr_trig_queue, timeout=timeout)
            print('readying')
            if self.vr_splitter_port is None:
                print('starting monitor')
                self.vr_splitter_port = self.camhand._getSplitterPort(self)
                self.vr_status = 'ready'
                self.vr_monthread = threading.Thread(name='recorder', target=self.monitor, args=[newtrig])
                self.vr_monthread.start()
            else:
                print('already ready')
                self.vr_trig_queue.put((newtrig,'add'))   # add to q first so the new thread has one to pick up
            return newtrig

    def unready(self, trig):
        """
        release a trigger and stop recording if appropriate
        
        The trigger is removed from the active set and the monitor thread will take 
        appropriate action in due course
        """
        self.vr_trig_queue.put((trig,'done'))
            
    def makefilename(self):
        """
        picks up the folder and file info and returns filepath
        """
        fp= (pathlib.Path(self.vr_folder).expanduser()/(time.strftime(self.vr_filename))).with_suffix('')
        fp.parent.mkdir(parents=True, exist_ok=True)
        print('files setup', str(fp))
        return fp

    def monitor(self, newtrigger):
        picam = self.camhand.picam
        resize=self.camhand.get_resize((self.vr_width, self.vr_height))
        if self.vr_backtime > 0:
            circstream=picamera.PiCameraCircularIO(self.camhand.start_camera(), seconds=self.backtime+1, splitter_port=self.vr_splitter_port)
            picam.start_recording(circstream, format='h264', sps_timing=True, resize=resize, splitter_port=self.vr_splitter_port)
            self.vr_status='waiting'
        else:
            circstream=None     
        vformat='.h264'
        trigset=set([newtrigger])
        triggers_end=None
        while len(trigset) > 0:
            timenow=time.time()
            for trig in trigset:
                if trig.trig_on:
                    if trig.trig_timeout is None:
                        triggered=True
                        break
                    else:
                        if trig.clear_time is None:
                            trig.clear_time=timenow+trig.trig_timeout
                            triggered=True
                            break
                        else:
                            if timenow > trig.clear_time:
                                trig.trig_on=False
                                trig.clear_time=None
                            else:
                                triggered=True
                                break
            else:
                triggered=False
                
            if triggered:
                last_triggered = timenow
                triggers_end=None # reset trigger timeout
                if self.vr_status=='waiting':   # circ buffer running
                    #switch to file
                    recordingsequ=1
                    fpath=self.makefilename()
                    postpath=fpath.with_name(fpath.name+'%03d' % recordingsequ).with_suffix(vformat)
                    picam.split_recording(str(postpath), splitter_port=self.vr_splitter_port)
                    prepath=fpath.with_name(fpath.name+'%03d' % 0).with_suffix(vformat)
                    circstream.copy_to(str(prepath), seconds=self.vr_backtime)
                    self.processfiles((True, prepath))
                    circstream.clear()
                    self.vr_status='recording'
                    self.vr_recordcount += 1
                    self.vr_lastrecording=timenow
                    print('cr: triggered and waiting')
                elif self.vr_status=='ready':   # camera should be active, but no recording in progress
                    # start recording to file
                    prepath=None
                    fpath=self.makefilename()
                    postpath=fpath.with_name(fpath.name+'%03d' % 0).with_suffix(vformat)
                    picam.start_recording(str(postpath), resize=resize, sps_timing=True,splitter_port=self.vr_splitter_port)
                    recordingsequ=0
                    print('recording to ', str(postpath))
                    self.vr_status='recording'
                    self.vr_recordcount += 1
                    self.vr_lastrecording=timenow
                    print('cr: triggered and ready')
                else:
                    # already recording to file - carry on
                    picam.wait_recording(splitter_port=self.vr_splitter_port) # carry on recording - check for split recording file
                    if timenow > self.vr_record_limit + self.vr_lastrecording:
                        postpath=fpath.with_name(fpath.name+'%03d' % (recordingsequ+1)).with_suffix(vformat)
                        picam.split_recording(str(postpath), splitter_port=self.vr_splitter_port)
                        self.processfiles((True, fpath.with_name(fpath.name+'%03d' % recordingsequ).with_suffix(vformat)))
                        recordingsequ += 1
                        self.vr_lastrecording=timenow
                        print('cr: triggered split recording')
                    else:
                        print('cr: triggered recording continues')
            else: # no triggers present (now) - what were we doing?
                if self.vr_status=='waiting':     # circ buffer running 
                    if self.vr_backtime <= 0: # no re-trigger time now so close that down
                        picam.stop_recording(splitter_port=self.vr_splitter_port)
                        circstream = None
                        self.vr_status='ready'
                        print('cr: no trigger waiting - stopped')
                    else:
                        print('cr: no trigger waiting - backtime')
                        picam.wait_recording(splitter_port=self.vr_splitter_port) # carry on recording to circ buff
                elif self.vr_status=='ready':
                    if self.vr_backtime > 0: # turn on circ buffer record
                        circstream=picamera.PiCameraCircularIO(picam, seconds=self.vr_backtime+1, splitter_port=self.vr_splitter_port)
                        picam.start_recording(circstream, resize=resize, format=vformat, sps_timing=True, splitter_port=self.vr_splitter_port)
                        self.vr_status='waiting'
                        print('cr: circ buffer started')
                    else:
                        print('cr: nothing to do here')
                        pass # nothing to do here
                else: # we're recording to file
                    if self.vr_forwtime <= 0 or (not triggers_end is None and timenow > triggers_end): # time to stop recording
                        if self.vr_backtime > 0: # switch recording to circular buffer
                            if circstream is None:
                                circstream=picamera.PiCameraCircularIO(picam, seconds=self.vr_backtime+1, splitter_port=self.vr_splitter_port)
                            picam.split_recording(circstream, splitter_port=self.vr_splitter_port)
                            self.vr_status='waiting'
                            print('cr: file now to circ stream') 
                        else:
                            picam.stop_recording(splitter_port=self.vr_splitter_port)
                            self.vr_status='ready'
                            print('recording stopped')
                        self.processfiles((False, fpath.with_name(fpath.name+'%03d' % recordingsequ).with_suffix('.h264')))
                    elif self.vr_forwtime > 0 and triggers_end is None: # set a trigger end time
                        triggers_end = timenow+self.vr_forwtime
                        print('trigger end time set')
                    else:
                        print('waiting for trigger to expire')
                        pass # waiting to reach trigger_end time
            try:
                trig, act =self.vr_trig_queue.get(block=True, timeout=2)
            except queue.Empty:
                trig = None
            while not trig is None:
                if act=='add':
                    trigset.add(trig)
                elif act=='done':
                    trigset.remove(trig)
                else:
                    trig.trig_on=act
                    if act:
                        if not trig.clear_time is None:
                            trig.clear_time=time.time()+trig.trig_timeout
                try:
                    trig, act=self.vr_trig_queue.get_nowait()
                except queue.Empty:
                    trig=None

        if self.vr_status == 'recording':
            picam.stop_recording(splitter_port=self.vr_splitter_port)
            self.processfiles((False, fpath.with_name(fpath.name+'%03d' % recordingsequ).with_suffix('.h264')))
        if self.vr_status == 'waiting':
            picam.stop_recording(splitter_port=self.vr_splitter_port)
        if not self.procthread is None:
            self.procqueue.put('stop')
        self.camhand._releaseSplitterPort(self, self.vr_splitter_port)
        self.vr_splitter_port = None
        self.vr_status = 'off'
        self.monthread=None

    def processfiles(self, data):
        print('processfiles requests', data)
        if self.procthread is None:
            self.procqueue=queue.Queue()
            self.procthread=threading.Thread(name='video_record', target=self.fileprocessor, kwargs={'q': self.procqueue})
            self.procthread.start()
        self.procqueue.put(data)

    def fileprocessor(self, q):
        nextact=q.get()
        while nextact != 'stop':
            print('==================', nextact)
            flist=[]
            more, fpath=nextact
            while more:
                if fpath.exists:
                    if  fpath.stat().st_size > 0:
                        flist.append(fpath)
                        if self.vr_max_merge > 0 and len(flist) >= self.vr_max_merge:
                            self.processvid(flist)
                            flist=[]
                    else:
                        fpath.unlink()
                else:
                    print('file processor oops A', fpath)
                more, fpath = q.get()
            if fpath.exists():
                if  fpath.stat().st_size > 0:
                    flist.append(fpath)
                else:
                    fpath.unlink()
            else:
                print('file processor oops B', fpath)
            self.processvid(flist)
            nextact=q.get()
        print('===============fileprocessor exits')

    def processvid(self, flist):
        if len(flist) > 0:
            cmd=['MP4Box', '-quiet', '-add', str(flist[0] )]
            for fpath in flist[1:]:
                cmd.append('-cat')
                cmd.append(str(fpath))
            outfile=flist[0].with_suffix('.mp4')
            cmd.append(str(outfile))
            print(cmd)
            subp=Popen(cmd, universal_newlines=True, stdout=PIPE, stderr=PIPE)
            outs, errs = subp.communicate()
            rcode=subp.returncode
            if rcode==0:
                shutil.copystat(str(flist[0]), str(outfile))
                if not self.vr_saveh264:
                    for f in flist:
                        f.unlink()
            else:
                if errs is None:
                    print('MP4Box error - code %s' % rcode)
                else:
                    print('MP4Box stderr:'+str(errs))

    def record_now(self, id):
        """
        method called from web browser to start / stop recording
        """
        print('trigger is', self.vr_web_trigger.trig_on)
        if self.vr_web_trigger.trig_on:
            self.vr_web_trigger.clear_trigger()
            rdat = ((id, {'value':'record now', 'bgcolor': None, 'disabled': False}),)
        else:
            self.vr_web_trigger.set_trigger()
            rdat = ((id, {'value':'STOP', 'bgcolor': 'red', 'disabled': False}),)
        return rdat

    def ready_web(self, id):
        """
        method called from web browser front end - flips ready state
        """
        if self.vr_web_trigger is None:
            self.vr_web_trigger=self.ready()
            rdat=((id,{'value': 'disable recorder', 'disabled': False, 'bgcolor': 'pink'}),(id[:-1]+'2',{'disabled': False}))
        else:
            self.unready(self.vr_web_trigger)
            self.vr_web_trigger=None
            rdat=((id,{'value': 'enable recorder', 'disabled': False, 'bgcolor': None}),(id[:-1]+'2', {'disabled': True}))
        return rdat

class trigger():
    """
    A simple trigger class that allows another thread to set and clear whether the trigger is active.
    
    It also includes a timeout after which the trigger will clear if no other action is taken.
    
    timeout can be None, in which case it never times out (and has to be cleared).
    """
    def __init__(self, trigq, timeout = 100):
        self.trig_on = False
        self.trig_timeout = timeout
        self.trigq=trigq
        self.clear_time=None

    def set_trigger(self):
        self.trigq.put((self,True))

    def clear_trigger(self):
        self.trigq.put((self, False))