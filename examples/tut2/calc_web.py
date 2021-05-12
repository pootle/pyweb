#!/usr/bin/python3

import time, sys
sys.path.append('../..')
import flaskextras, netinf, calc_class

class webbaby(flaskextras.webify, calc_class.mymaths):
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
        calc_class.mymaths.__init__(self)
        self.operation_LIST = {'display': self.valid_ops()}
        updateindex={'index': self.index_updates}
        flaskextras.webify.__init__(self, __name__, updateindex)


    def index_updates(self):
        """
        called at regular intervals from the web server code for an active page with fields that need updating.
        
        There is only 1 page in this app ('index') and it provides updates for 3 fields (only fields which
        have actually changed value since the last update are sent to the web browser).
        """
        return [
            ('prog_bar', {'value': str(self.current_ops)}),
        ]

    def do_sum(self, id):
        try:
            result=self.answer()
            if result.is_integer():
                resultstr=str(int(result))
            else:
                resultstr='%5.2f' % result
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
        return flaskextras.make_subselect(
                values=self.valid_ops(),
                selected=self.operation)

    @property
    def current_ops(self):
        """
        provide an attribute getter that simulates a progress bar
        """
        return round(time.time()-self.started) % (self.target_ops+1)

app = webbaby()

@app.route('/')
def redir():
    return redirect(url_for('index'))

@app.route('/index')
def index():
    with open('templates/index.html', 'r') as tfile:
        template=tfile.read()
    return template.format(app=app)    
    