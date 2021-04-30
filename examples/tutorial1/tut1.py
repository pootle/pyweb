import sys, threading, time, webbrowser
sys.path.append('../..')
import simpleweb, netinf

run_time_string='I have run for {mins:d}:{secs:02d}'

class web_tut1(simpleweb.webify):
    def __init__(self):
        """
        setup the app's local variables
        time_started    : - is just that
        time_running    : is a string for the time running field on the web page - updated on demand
        b1_click_count  : is the number of times button 1 has been clicked
        """
        self.time_started=time.time()
        self.time_running=run_time_string.format(mins=0, secs=0)
        self.b1_click_count = 0
        super().__init__()
        
    def get_server_def(self):
        """
        This method is called by the web server as it starts. It returns
        * the list of pages the app will respond to and details how to handle each of them
        * the list of requests the app will respond to and the function / method that should be called.
        """
        return {
            'GET': {       # list the special pages for this app
                ''              : ('redirect', '/index.html'),
                'index.html'    : ('app_page', {'template': 'index.html'}),
            },
            'REQUEST': {    # list the requests we are going to accept and how to handle them
                'clickbtn1'     : self.btn1_clicked,
                'field_update'  : self.web_field_update,
            },
            'static': 'static',
        }
        
    def get_updates(self, pageid):
        """
        called at regular intervals from the web server code for an active page with fields that need updating.
        
        There is only 1 page in this app ('index') and it provides updates for 2 fields (only fields which
        have actually changed value since the last update are sent to the web browser).
        """
        mins, secs = divmod(round(time.time()-self.time_started),60)
        self.time_running=run_time_string.format(mins=mins, secs=round(secs))
        if pageid == 'index':
            return [
                ('run_time', self.time_running),
                ('b1_counter', self.b1_click_count),
                ('count2',   str(self.b1_click_count*2)),
                ]
        else:
            return []

    def btn1_clicked(self, id):
        """
        method called from web browser when button clicked
        """
        self.b1_click_count += 1
        rdat = ((id, {  'value':'ooh! click me again!', 
                        'bgcolor': 'pink' if (self.b1_click_count % 2) == 1 else 'green',
                        'disabled': False}),)
        return rdat

if __name__ == '__main__':
    app = web_tut1()
    server = simpleweb.MultiServer(app=app, port=8000)
    serverthread = threading.Thread(target=server.serve_forever, name='webserver')
    serverthread.start()
    netinf.showserverIP(8000)
    ips=netinf.allIP4()
    sip = 'http://'+ips[0]+':8000' if len(ips) > 0 else 'http://127.0.0.1:8000'
    webbrowser.open(sip)
    try:
        while True:
            time.sleep(3)
    except KeyboardInterrupt:
        server.tidyclose()
        time.sleep(0.5)
        print('close on keyboard interrupt')
    except:
        server.tidyclose()
        raise
    