import sys, time, json
from flask import redirect, request, Response, jsonify, Flask

class webify(Flask):
    """
    Inherit from this class to provide the added functionality to allow dynamic updates of a web page by the app and 
    to provide an easy mechanism to call methods in the app,
    """
    def __init__(self, appname, page_updators):
        super().__init__(appname)
        self.webify_page_update_index = page_updators
        self.add_url_rule('/appupdates', view_func=self.webify_doappupdates)
        self.add_url_rule('/field_update', view_func=self.webify_fieldupdator)
        self.add_url_rule('/app_action', view_func=self.webify_app_action_call, methods=('REQUEST',))

    def webify_app_action_call(self):
        """
        called from flask to handle a REQUEST with app_action. This will have been triggered by field on the web page with
        onclick="app_action ....."
        """
        print(request.json, file=sys.stderr)
        app_func=getattr(self,request.json.pop('action'))
        print('calling', app_func, 'with', request.json, 'of type', type(request.json).__name__, file=sys.stderr)
        return jsonify(app_func(**request.json))

    def webify_fieldupdator(self):
        """
        called from flask when the user has changed a field that has (for example) onchange="field_update(this, 'int')"
        if converts the value to the appropriate type and updates finds the relevant instance's attribute then sets the value.
        Note that the js code in the web page disables the field
        as soon as it is called (to prevent impatient users from triggering multiple calls), so this finishes be ebaling the field again
        any problems identfied will cause an alert to the user on the web page.
        """
        request_data = request.args
        fid=request_data['id']
        splitid=fid.split('.')
        targetob = self
        while len(splitid) > 1:
            nextatt=splitid.pop(0)
            try:
                targetob=getattr(targetob,nextatt)
            except:
                print('web_field_update failed to find attribute >%s< in object %s for id %s' % (nextatt, targetob, id), file=sys.stderr)
                return jsonify(((fid, {'disabled':False}),
                        ('alert', "I'm sorry Dave, I can't find that attribute"),))
        targetatt=splitid[0]
        if not hasattr(targetob, targetatt):
            print('web_field_update failed - attribute %s not found in %s' % (targetatt, targetob), file=sys.stderr)
            return jsonify(((fid, {'disabled':False}),
                    ('alert', "I'm sorry Dave, I couldn't find the field"),))
        ftype=request_data['t']
        valstring=request_data['v']
        try:
            if ftype=='float':      # its a float
                newval = float(valstring)
            elif ftype=='int':      # its an int
                newval = int(valstring)
            elif ftype=='str':      # its a string
                newval=valstring
            elif ftype=='bool':     # boolean
                newval = valstring=='true'
            elif ftype=='sel':      # from a select field
                field_info = getattr(targetob, targetatt+'_LIST', None)
                if not field_info is None:
                    val_index = field_info['display'].index(valstring)
                    if 'values' in field_info:
                        newval = field_info['values'][val_index]
                    else:
                        newval = valstring
                else:
                    print('failed to find select list %s in %s' % (targetatt+'_LIST', targetob), file=sys.stderr)
                    return jsonify(((fid, {'disabled':False}),
                        ('alert', "I'm sorry Dave, there's a missing list"%ftype),))
            else:
                print('web_field_update failed - field type %s unknown for field %s' % (ftype, id), file=sys.stderr)
                return jsonify(((fid, {'disabled':False}),
                        ('alert', "I'm sorry Dave, I don't understand %s as a field type"%ftype),))
        except:                 # any exception here means we couldn't convert the string to the expected type
                print('web_field_update failed - failed to handle %s of type %s for field %s' % (valstring, ftype, id), file=sys.stderr)
                return jsonify(((fid, {'disabled':False}),
                            ('alert', "I'm sorry Dave, I couldn't make sense of the value %s" % valstring),))
        try:
            setattr(targetob, targetatt, newval)
            print(' I set %s in %s to %s' % (targetatt, targetob, newval), file=sys.stderr)
        except:
            traceback.print_exc()
            return jsonify(((fid, {'disabled':False}),
                        ('alert', "I'm sorry Dave, something went wrong with that update - see server log"),))
        return jsonify(((fid, {'disabled':False}),))

    def webify_doappupdates(self):
        """
        responds to GET requests with a generator (updatestreamgen - above) that uses the function defined in updateindex to fetch the values
        appropriate to each page. 
        """
        return Response(updatestreamgen(self.webify_page_update_index[request.args['page']]), mimetype='text/event-stream; charset=utf-8')

    def __format__(self, fparam):
        """
        special version of format that handles fields that use a drop down list on the web page. If the format param ends with 'sel' then the 
        string preceding 'sel' is the attribute name with the current drop down value, and this code expects to find an attibute <name>_LIST
        which is a dict with info to create the dropdown.
        """
        if fparam.endswith('sel'):
            attr = fparam[:-3]
            print('trying with', attr, file=sys.stderr)
            return make_subselect(getattr(self, attr+'_LIST')['display'], selected=getattr(self,attr))
        else:
            return super().__format__(fparam)

def make_subselect(choices, selected, display=None):
    """
    Function to create the (inner)) html for a drop down list (<select>)
    
    choices: the list of options as seen by the app - displayed to the user if display is None
    
    selected: the current value - if display is present, one of display, otherwise one of choices
    
    display:  if present, this is the list the user will see 
    """
    if display is None:
        return ''.join(['<option{sel}>{val}</option>'.format(sel=' selected ' if item == selected else '', val=item)  for item in choices])
    else:
        assert len(display)==len(choices)
        return ''.join(['<option name="{}"{}>{}</option>'.format(name, ' selected ' if name == selected else '', disp)  for name, disp in zip(choices, display)])

def updatestreamgen(updatefunc):
    """
    standard generator to yield an ongoing stream of updates to fields on the page.
    
    This function remembers all the field values that have been sent and only sends those that have changed
    
    updatefunc: a function to call that will return a dict of the updateable fields and the current values of the field
    
    yields an ongoing stream of updates which Flask forwards to the web browser. The standard js function 'liveupdates' in pymon.js 
    processes the data and updates the web page.
    """
    currently={}
    while True:
        newdata = updatefunc()
        updates=[]
        for anupdate in newdata:
            if anupdate[0] in currently:
                fieldupdates={}
                currentitem=currently[anupdate[0]]
                for updatekey, updateval in anupdate[1].items():
                    if not updatekey in currentitem or currentitem[updatekey]!=updateval:
                        currentitem[updatekey]=updateval
                        fieldupdates[updatekey]=updateval
                if fieldupdates:
                    updates.append((anupdate[0], fieldupdates))
            else:
                currently[anupdate[0]] = anupdate[1]
                updates.append(anupdate)
        datats=json.dumps(updates)
        yield ('data: %s\n\n' % datats).encode()
        time.sleep(2)