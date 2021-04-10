from http import server
from urllib.parse import urlparse, parse_qs
import pathlib, threading, time, sys, json, traceback, subprocess, errno

class simplehandler(server.BaseHTTPRequestHandler):
    """
    A class to handle each request 
    """
    def do_GET(self):
        parsedpath=urlparse(self.path)      # and do 1st level parse on the request
        if parsedpath.path.startswith('/static/'):                           #if the path starts with static - serve a fixed file
            self.servestatic(statfile=parsedpath.path[len('/static/'):])
        elif parsedpath.path == '/notify':    # field value update or button click
            try:
                queryparams = parse_qs(parsedpath.query)
                id=queryparams['t'][0]
            except:
                self.send_error(500, 'missing parameter in query request')
                print('notify rejected - missing / bad params', queryparams)
                return
            try:
                resp, msg = self.server.app.webupdate(id, queryparams.get('v', []))
                if 200 <= resp <= 299:
                    self.send_response(resp)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    if resp != 204:
                        self.wfile.write(json.dumps(msg).encode())
                else:
                    self.send_error(resp, msg)
            except ValueError as ve:
                self.send_error(403, str(ve))
            except:
                print('Exception handling notify: %s' % queryparams)
                traceback.print_exc()
                self.send_error(500,'query crashed!')
        elif parsedpath.path == '/appupdates':  # web page requesting ongoing update stream
            queryparams = parse_qs(parsedpath.query)
            if 'pageid' in queryparams:
                self.serveupdates(queryparams['pageid'][0])
            else:
                print('bad request - appupdates request with no pageid')
                self.send_error(501)
        else:                                   # some sort of general page request
            pathrequ=parsedpath.path[1:]      # ditch the leading slash
            get_defs = self.server.serverdef['GET'] # fetch the dict of known requests
            if pathrequ in get_defs:
                action, params = get_defs[pathrequ]
                if action=='redirect':          # it's a simple redirect
                    self.send_response(301)
                    self.send_header('Location', params)
                    self.end_headers()
                elif action=='app_page':        # it's a request for an html page from a template
                    try:
                        tpath = pathlib.Path('templates')/params['template']
                        with tpath.open('r') as tfile:
                            template=tfile.read()
                        app=self.server.app
                        content=template.format(app=app)
                        self.send_response(200)
                        self.send_header(*mimetypeforfile('.html'))
                        self.end_headers()
                        self.wfile.write(content.encode())
                    except:
                        traceback.print_exc()
                        self.send_error(500,' eeeek - see log')
                else:
                    print('unknown action %s for GET %s' % (action, pathrequ), file=sys.stderr)
                    self.send_error(500)
            else:
                print('no action defined for path %s' % pathrequ, file=sys.stderr)
                self.send_error(404)

    def serveupdates(self, pageid):
        """
        produces an ongoing stream of updates for a web page. Runs until the connection fails or
        something else breaks.
        
        Initialise an empty dict, used to hold the last known values of the fields of interest.
        
        Ask the app for a list of current values for all the fields of interest on the given page
        (Each entry in the list is a field key, and a field value)
        
        Check each entry against the dict and drop any entries where the value hasn't changed
        
        JSON encode the resuling list and send to the web browser.
        
        wait a bit
        
        repeat from ask the app
        
        """
        running=True
        currently={}
        while running:
            try:
                newdata = self.server.app.get_updates(pageid)
                updates=[]
                for anupdate in newdata:
                    if not anupdate[0] in currently or currently[anupdate[0]] != anupdate[1]:
                        currently[anupdate[0]] = anupdate[1]
                        updates.append(anupdate)
                datats=json.dumps(updates)
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                self.end_headers()
                self.wfile.write(('data: %s\n\n' % datats).encode())
#                print('----------------> %s sent' % newdata)
                time.sleep(2)
                if not self.server.serverrunning:
                    running = False
            except BrokenPipeError as e:
                running = False
                if e.errno==errno.EPIPE:
                    print('genstream client %s terminated' % str(self.client_address))
                else:
                    traceback.print_exc()
                    self.send_error(500,' eeeek - see log')
            except:
                running = False
                traceback.print_exc()
                self.send_error(500,' eeeek - see log')

    def servestatic(self, statfile):
        staticfile=pathlib.Path('static')/statfile
        if staticfile.is_file():
            try:
                sfx=mimetypeforfile(staticfile.suffix)
            except:
                self.send_error(501, "no mime type found in server config['mimetypes'] for %s" % staticfile.suffix)
                return
            self.send_response(200)
            self.send_header(*sfx)
            with staticfile.open('rb') as sfile:
                cont=sfile.read()
                self.send_header('Content-Length', len(cont))
                self.end_headers()
                self.wfile.write(cont)
        else:
            self.send_error(404, 'file %s not present or not a file' % str(staticfile))

class MultiServer(server.ThreadingHTTPServer):
    """
    extend threadinghttpserver to look after the app
    """
    allow_reuse_address = True
    daemon_threads = True
    def __init__(self,  app, port, requhandler = simplehandler, **kwargs):
        self.app = app
        self.serverrunning = True
        self.serverdef=app.get_pages()
        self.check_config(self.serverdef)
        self.activeupdates = {}
        super().__init__(('', port), requhandler, **kwargs)

    def tidyclose(self):
        print('I am shutting down')
        #self.app.Save()
        self.serverrunning = False
        self.shutdown()

    def check_config(self, sdef):
        checkOK=True
        if 'GET' in sdef:
            for gk, kv in sdef['GET'].items():
                badmsg=None
                if not isinstance(gk,str):
                    badmsg = 'bad entry in serverdef["GET"]: key is not a string (%s)' % gk
                if not len(kv) == 2:
                    badmsg = 'bad entry in serverdef["GET"]: value for key %s is not 2-tuple' % gk
                if not badmsg:
                    action, params = kv
                    if action == 'redirect':
                        if not params[1:] in sdef['GET']:
                            badmsg = 'GET entry for "%s" redirects to %s, but %s has no entry in GET' % (gk, params, params)
                    elif action == 'app_page':
                        if 'template' in params:
                            tpath=pathlib.Path('templates')/params['template']
                            if not tpath.is_file():
                                badmsg = 'unable to locate template file "%s" for entry "%s"' % (str(tpath), gk)
                        else:
                            badmsg = '"template" not defined for entry "%s"' % gk
                    else:
                        print('GET entry for "%s" has unknown action %s. Not checked' % (gk, action))
                if badmsg:
                    print(badmsg, file=sys.stderr)
                    checkOK=False
        if not checkOK:
            sys.exit(1)

def mimetypeforfile(fileext):
        return {
        '.css' :('Content-Type', 'text/css; charset=utf-8'),
        '.html':('Content-Type', 'text/html; charset=utf-8'),
        '.js'  :('Content-Type', 'text/javascript; charset=utf-8'),
        '.ico' :('Content-Type', 'image/x-icon'),
        '.jpg' :('Content-Type', 'image/jpeg'),
        '.png' :('Content-Type', 'image/png'),
        '.mp4' :('Content-Type', 'video/mp4'),
        '.svg' :('Content-Type', 'image/svg+xml'),
        }[fileext]

class webify():
    """
    class that adds web update method to use with existing class or as base for a simple app.
    """
    def webupdate(self, fieldid, value):
        """
        Called when the user updates a field value on a web page.
        
        fieldid: the html id for the field
        
        values:  array of strings for the updated value (typically only 1 in the array)
        
        returns:
            resp: an hhtp response code which can be:
                204     : update handled nothing more to do
                200-299 : (but not 204) msg (a dict) will be sent with
                    'OK'    : boolean  - True if successful
                    'value' : (only used if OK is True) updated field value.
                    'fail'  : (only used if OK is False) message to alert user
            
                any other value: Something broke, attached string sent to use as user prompt
        """
        split_id = fieldid.split('-')
                        # split off the type of the string, and check we got 1
        if len(split_id) > 1:
            try:
                ftype=split_id[-1]
                        # this defines how to handle the string
                if ftype=='f':      # its a float
                    val = float(value[0])
                elif ftype=='i':    # its an int
                    val = int(value[0])
                elif ftype=='s':    # its a string
                    val=value[0]
                else:
                    return 301, "I don't understand this request's format (%s)" % ftype
            except:                 # any exception here means we couldn't convert the string to the expected type
                return 400, 'invalid value'
            fieldkey = split_id[0]  # now get the field name
            if hasattr(self, fieldkey):
                try:                # wrap setting the attribute so if ot blows up we can report the error
                    setattr(self, fieldkey, val)
                    return 204, None
                except Exception as e:
                    return 500, str(e)
            else:
                        # the field name had no matching attribute so send back an error
                return 400, 'unknown field (%s) in update request' % fieldkey
        return 400, 'passed fieldid not understood (%s)' % fieldid


def make_subselect(choices, selected, display=None):
    if not display is None:
        assert len(display)==len(choices)
        return ''.join(['<option name="{}"{}>{}</option>'.format(name, ' selected ' if name == selected else '', disp)  for name, disp in zip(choices, display)])
    else:
        return ''.join(['<option{sel}>{val}</option>'.format(sel=' selected ' if item == selected else '', val=item)  for item in choices])
