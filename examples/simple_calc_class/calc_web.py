#!/usr/bin/python3

import threading, time, sys
sys.path.append('../..')
import simpleweb, netinf, calc_class

class webbaby(calc_class.mymaths, simpleweb.webify):
    """
    This class extends the original app with some basic web helping methods (from wimpleweb.webify)
    and provides the method 'get_updates' which is called by the webserver whenever a page is requested
    which is an 'app_page' (see serverdef below)
    
    It also adds a property to help provide a clean web interface (op_select), and another property to 
    demo a simple progress bar.
    
    This approach means there is only 1 copy of the app running, so if multiple web browsers access
    the web server they all see the same values.
    """
    def __init__(self):
        """
        in addition to constructing the base classes, initialise a couple of variables used to run the 
        progress bar.
        """
        self.target_ops = 15
        self.started=time.time()
        super().__init__()
        self.operation_LIST = {'display': self.valid_ops()}

    def get_server_def(self):
        """
        This method is called by the web server as it starts. It returns the list of pages the app will
        respond to and details how to handle each of them
        """
        return {
            'GET': {
                ''              : ('redirect', '/index.html'),
                'index.html'    : ('app_page', {'template': 'index.html'}),
            },
            'REQUEST': {    # list the requests we are going to accept and how to handle them
                'do_sum'        : self.calc_now,
                'field_update'  : self.web_field_update,
            },

            'static': '../static',
        }

    def get_updates(self, pageid):
        """
        called at regular intervals from the web server code for an active page with fields that need updating.
        
        There is only 1 page in this app ('index') and it provides updates for 2 fields (only fields which
        have actually changed value since the last update are sent to the web browser).
        """
        if pageid == 'index':
            return [
                ('prog_bar', str(self.current_ops) ),
                ]
        else:
            return {}

    def calc_now(self, id):
        try:
            result=self.answer()
            if result.is_integer():
                resultstr=str(int(result))
            else:
                resultstr='%5.1f' % result
        except ZeroDivisionError:
            resultstr = 'Division by zero!'
        except:
            resultstr='calculator meltdown'
        return (('answer', {'value': resultstr}),
                ('do_sum', {'disabled': False}),)

    @property
    def op_select(self):
        """
        The builds the html for the operator selection so it shows the app's current value (for example if the page
        is reloaded or a fresh browser page is opened).
        """
        return simpleweb.make_subselect(
                choices=self.valid_ops(),
                selected=self.operation)

    @property
    def current_ops(self):
        """
        provide an attribute getter that simulates a progress bar
        """
        return round(time.time()-self.started) % (self.target_ops+1)

if __name__ == '__main__':
            # first create a web enabled instance of the app
    app=webbaby()
            # then set up the web server, passing the app 
    server = simpleweb.MultiServer(app=app, port=8000, )
            # fire up a new thread to run the web server and start it.
    serverthread = threading.Thread(target=server.serve_forever, name='webserver')
    serverthread.start()
    netinf.showserverIP(8000)
            # since the webserver is running in a another thread this code just 
            # waits for a keyboard interrupt which initiates a clean shutdown
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        server.tidyclose()
            # if the app needs to close down tidily, call that here
        print('close on keyboard interrupt')
    except:
        server.tidyclose()
        raise
    