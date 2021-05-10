import sys, time
sys.path.append('../..')
import flaskextras
from flask import redirect

run_time_string='{mins:d}:{secs:02d} (m:s)'

class web_tut1(flaskextras.webify):
    def __init__(self):
        """
        setup the app's local variables
        time_started    : - is just that
        time_running    : is a string for the time running field on the web page - updated on demand
        b1_click_count  : is the number of times button 1 has been clicked
        """
        self.time_started=time.time()
        self.b1_click_count = 0
        updateindex={'index': self.index_updates}
        super().__init__(__name__, updateindex)
        
    def index_updates(self):
        """
        called at regular intervals from the web server code for an active page with fields that need updating.
        
        There is only 1 page in this app ('index') and it provides updates for 3 fields (only fields which
        have actually changed value since the last update are sent to the web browser).
        """
        return [
            ('run_time',    {'value': self.time_running}),
            ('b1_counter',  {'value': self.b1_click_count}),
            ('count2',      {'value': str(self.b1_click_count*2)}),
        ]

    def clickbtn1(self, id):
        """
        method called from web browser when button clicked
        """
        self.b1_click_count += 1
        rdat = ((id, {  'value':'ooh! click me again!', 
                        'bgcolor': 'pink' if (self.b1_click_count % 2) == 1 else 'green',
                        'disabled': False}),)
        return rdat

    @property
    def time_running(self):
        mins, secs = divmod(time.time()-self.time_started, 60)
        return run_time_string.format(mins=int(mins), secs=int(secs))

app = web_tut1()

@app.route('/')
def redir():
    return redirect(url_for('index'))

@app.route('/index')
def index():
    with open('templates/index.html', 'r') as tfile:
        template=tfile.read()
    return template.format(app=app)    