from http import server
from urllib.parse import urlparse, parse_qs
import pathlib, threading, time, sys, json, traceback, subprocess, errno, inspect

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
                print('notify rejected - missing / bad params', queryparams, file=sys.stderr)
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
                print('Exception handling notify: %s' % queryparams, file=sys.stderr)
                traceback.print_exc()
                self.send_error(500,'query crashed!')
        elif parsedpath.path == '/appupdates':  # web page requesting ongoing update stream
            queryparams = parse_qs(parsedpath.query)
            if 'pageid' in queryparams:
                self.serveupdates(queryparams['pageid'][0])
            else:
                print('bad request - appupdates request with no pageid' , file=sys.stderr)
                self.send_error(501)

        elif parsedpath.path=='/camstream':
            print('start camera stream', file=sys.stderr)
            camstream = self.server.app.get_cam_stream()
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            running=True
            try:
                while running and not camstream is None and self.server.serverrunning:
                    try:
                        frame, conttype, datalen=camstream.nextframe()
                    except StopIteration:
                        running=False
                    if running:
                        try:
                            self.wfile.write(b'--FRAME\r\n')
                            self.send_header('Content-Type', conttype)
                            self.send_header('Content-Length', datalen)
                            self.end_headers()
                            self.wfile.write(frame)
                            self.wfile.write(b'\r\n')
                        except BrokenPipeError:
                            running=False
                print('camstream client %sterminated' %   str(self.client_address), file=sys.stderr)
            except ConnectionError as ce:
                print('camstream client connection lost %s' %  str(self.client_address), file=sys.stderr)
            except Exception as e:
                print('camstream client %s crashed' %   (str(self.client_address)), file=sys.stderr)
            print('camstream handler thread exits', file=sys.stderr)

        else:                                   # some sort of general page request
            pathrequ=parsedpath.path[1:]        # ditch the leading slash
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

    def do_REQUEST(self):
        requests = self.server.serverdef['REQUEST']
        parsedpath=urlparse(self.path)
        rq = parsedpath.path[1:]
        if rq in requests:
            print('   ',self.headers)
            if 'Content-Length' in self.headers:
                request_params=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                print('>%s<' % request_params)
                try:
                    response=requests[rq](**request_params)
                    if response is True:
                        resp=200
                        resp_data=((request_params['id'], {'disabled':False}),)
                    else:
                        resp=200
                        resp_data=response
                except TypeError:
                    self.send_error(502,"There's a problem with that Dave.")
                    rqf=requests[rq]
                    if callable(rqf):
                        print('signature of %s (%s) does not match request params (%s) for request %s' % (rqf.__name__, inspect.signature(rqf), request_params, rq))
                        self.send_error(501,'action call mismatch')
                    else:
                        print('The action specified for request %s is not callable (%s of type %s)' % (rq, rqf, type(rqf).__name__))
                        self.send_error(501,'action call fail')
                except:
                    self.send_error(501,'no parameters received')
                    traceback.print_exc()
                else:
                    self.send_response(resp)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    print('sending ', resp_data)
                    self.wfile.write(json.dumps(resp_data).encode())
            else:
                print('xxxx')
                help(self.rfile)
                r_data = self.rfile.read()
                print('yyyy')
                print('>%s<' % r_data)
                request_params=json.load(self.rfile)
                print('ppp      ',request_params)
                self.send_error(401,'mmmmm')
        else:
            self.send_error(404,"I'm sorry Dave, I don't know how to do that (%s)" % rq)

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
                print(updates)
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
                    print('genstream client %s terminated' % str(self.client_address), file=sys.stderr)
                else:
                    traceback.print_exc()
                    self.send_error(500,' eeeek - see log')
            except:
                running = False
                traceback.print_exc()
                self.send_error(500,' eeeek - see log')

    def servestatic(self, statfile):
        staticfile=pathlib.Path(self.server.serverdef['static'])/statfile
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
        self.serverdef=app.get_server_def()
        self.check_config(self.serverdef)
        self.activeupdates = {}
        super().__init__(('', port), requhandler, **kwargs)

    def tidyclose(self):
        print('I am shutting down', file=sys.stderr)
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
                        print('GET entry for "%s" has unknown action %s. Not checked' % (gk, action), file=sys.stderr)
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
    
    This class provides the webupdate method that is called from the server code when the user changes the 
    value of a field that immediately updates a corresponding attribute in the app's class (or calls a function).

    Inheriting classes should also implement the methods get_server_def and get_updates (see below).
    """
    def __init__(self):
        self.logfile=sys.stderr

    def get_server_def(self):
        """
        when the webserver starts and is passed the "app", it calls this method to retrieve information about the service:
        
        return a dict as follows:
            'GET'    : <pagedefs>,
            'static' : <location for folder with static files>
        
        """
        raise NotImplementedError()

    def web_field_update(self, id, ftype, val):
        """
        normal method to update the value of a class' attribute. One of the standard 'REQUEST's 
        
        id:     field's id - is used as the attribute name. like in string format, '.' used as a separator to
                navigate class hierarchy
        
        type:   identifies how the string from the web browser should be parsed, can be:
            bool
            int
            float
            str
        
        val:    the string for the new value - will be converted as defined by type param
        """
        splitid=id.split('.')
        targetob = self
        while len(splitid) > 1:
            nextatt=splitid.pop(0)
            try:
                targetob=getattr(targetob,nextatt)
            except:
                print('web_field_update failed to find attribute >%s< in object %s for id %s' % (nextatt, targetob, id))
                return ((id, {'disabled':False}),
                        ('alert', "I'm sorry Dave, I can't find that attribute"),)
        targetatt=splitid[0]
        if not hasattr(targetob, targetatt):
            print('web_field_update failed - attribute %s not found in %s' % (targetatt, targetob))
            return ((id, {'disabled':False}),
                    ('alert', "I'm sorry Dave, I couldn't find the field"),)
        try:
            if ftype=='float':      # its a float
                newval = float(val)
            elif ftype=='int':      # its an int
                newval = int(val)
            elif ftype=='str':      # its a string
                newval=val
            elif ftype=='bool':     # boolean
                newval = val=='true'
            elif ftype=='sel':      # from a select field
                field_info = getattr(targetob, targetatt+'_LIST', None)
                if not field_info is None:
                    val_index = field_info['display'].index(val)
                    if 'values' in field_info:
                        newval = field_info['values'][val_index]
                    else:
                        newval = val
                else:
                    print('failed to find select list %s in %s' % (targetatt+'_LIST', targetob))
                    return ((id, {'disabled':False}),
                        ('alert', "I'm sorry Dave, there's a missing list"%ftype),)
            else:
                print('web_field_update failed - field type %s unknown for field %s' % (ftype, id))
                return ((id, {'disabled':False}),
                        ('alert', "I'm sorry Dave, I don't understand %s as a field type"%ftype),)
        except:                 # any exception here means we couldn't convert the string to the expected type
            print('web_field_update failed - failed to handle %s of type %s for field %s' % (val, ftype, id))
            return ((id, {'disabled':False}),
                        ('alert', "I'm sorry Dave, I couldn't make sense of the value %s" % val),)
        try:
            setattr(targetob, targetatt, newval)
            print(' I set %s in %s to %s' % (targetatt, targetob, newval))
        except:
            traceback.print_exc()
            return ((id, {'disabled':False}),
                        ('alert', "I'm sorry Dave, something went wrong with that update - see server log"),)
        return True


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
            ftype=split_id[-1]      # this defines how to handle the string
            fieldkey = split_id[0]  # and get the field name
            if ftype == 'x':        # call a function
                if hasattr(self, fieldkey):
                    try:
                        return 200, getattr(self, fieldkey)(value)
                    except Exception as e:
                        print('function call to %s from webupdate in class webify in module simpleweb failed' % fieldkey, e, file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)
                        return 500, 'it went all wrong'
            else:
                try:
                    if ftype=='f':      # its a float
                        val = float(value[0])
                    elif ftype=='i':    # its an int
                        val = int(value[0])
                    elif ftype=='s':    # its a string
                        val=value[0]
                    elif ftype=='b':    # boolean
                        print('check', value[0])
                        val = value[0]=='true'
                    elif ftype=='o':    # from a select field
                        field_info = getattr(self, fieldkey+'_LIST')
                        val_index = field_info['display'].index(value[0])
                        val=field_info['values'][val_index]
                    else:
                        return 301, "I don't understand this request's format (%s)" % ftype
                except:                 # any exception here means we couldn't convert the string to the expected type
                    return 400, "invalid value - I don't understand >%s< as a %s" % (value[0], {'f': 'float', 'i': 'integer'}[ftype])
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

    def web_request(self, call_params):
        """web page request from pymon.js call_server"""
        pass

def make_subselect(choices, selected, display=None):
    if display is None:
        return ''.join(['<option{sel}>{val}</option>'.format(sel=' selected ' if item == selected else '', val=item)  for item in choices])
    else:
        assert len(display)==len(choices)
        zzz= ''.join(['<option name="{}"{}>{}</option>'.format(name, ' selected ' if name == selected else '', disp)  for name, disp in zip(choices, display)])
        print(zzz)
        return zzz