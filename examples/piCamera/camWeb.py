import sys, threading, time
sys.path.append('../..')
import camHandler
import simpleweb, netinf

class web_picam(camHandler.cameraManager, simpleweb.webify):
    def get_server_def(self):
        """
        This method is called by the web server as it starts. It returns the list of pages the app will
        respond to and details how to handle each of them
        """
        return {
            'GET': {       # list the special pages for this app
                ''              : ('redirect', '/index.html'),
                'index.html'    : ('app_page', {'template': 'index.html'}),
            },
            'REQUEST': {    # list the requests we are going to accept and how to handle them
                'record_enable': self.vidrecord.ready_web,
                'record_now'   : self.vidrecord.record_now,
                'field_update' : self.web_field_update,
            },
            'static': 'static',
        }
        
    def get_updates(self, pageid):
        """
        called at regular intervals from the web server code for an active page with fields that need updating.
        
        There is only 1 page in this app ('index') and it provides updates for 2 fields (only fields which
        have actually changed value since the last update are sent to the web browser).
        """
        if pageid == 'index':
            return [
                ('cam_summary', self.cam_summary),
                ('vr_status',   self.vidrecord.vr_status),
                ]
        else:
            return []

    @property
    def select_res(self):
        return simpleweb.make_subselect(
                choices=camHandler.cam_resolutions[self.camType],
                selected=self.cam_resolution)

    def __format__(self, fparam):
        s1 = fparam.split('#')
        if len(s1) == 1:
            return super().__format__(fparam)
        else:
            act, attr = s1[:2]
            if act == 'sel':
                return simpleweb.make_subselect(getattr(self, attr+'_LIST')['display'], selected=getattr(self,attr))
            else:
                print('xxxxx', s1)
                return ''

if __name__ == '__main__':
    camapp = web_picam()
    server = simpleweb.MultiServer(app=camapp, port=8000)
    serverthread = threading.Thread(target=server.serve_forever, name='webserver')
    serverthread.start()
    netinf.showserverIP(8000)
    try:
        while True:
            time.sleep(3)
    except KeyboardInterrupt:
        server.tidyclose()
        camapp.stop_camera()
        time.sleep(0.5)
        print('close on keyboard interrupt')
    except:
        server.tidyclose()
        camapp.stop_camera()
        raise
    