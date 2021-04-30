
function do_updates(newinfo) {
    if (newinfo=='kwac') {
        console.log('update nothing')
    } else {
        newinfo.forEach(function(update, idx) {
            console.log(update[0] + ' is ' + update[1]);
            if (update[0] == '') {
                console.log('oops');
                console.log(newinfo);
            }
            var tempel=document.getElementById(update[0]);
            if (tempel) {
                if (tempel.nodeName=='INPUT' || tempel.nodeName=='PROGRESS' || tempel.nodeName=='SELECT') {
                    tempel.value=update[1];
                } else {
                    tempel.innerHTML=update[1];
                }
            }
        });
    }
}

function field_update(ele, ftype) {
    // called (mostly) when user changes a field's value (typically when the field looses focus)
    call_server(ele, "field_update", {"id": ele.id, "ftype": ftype, "val": ele.value})
}

function app_action(ele, path) {
    // called (mostly) from button's onclick
    call_server(ele, path, {"id": ele.id})
}

async function call_server(ele, url, params) {
    /*  
        The server is notified and can respond with a list of updates to apply to fields.
        
        The originating field is disabled, normally the updates in the response will enable it again 
    */
    ele.disabled=true;
    let response = await fetch(url, {
        headers: {"content-type":"application/json; charset=UTF-8"},
        body   : JSON.stringify(params),
        method : "REQUEST"
    });
    if (response.ok) { // if HTTP-status is 200-299
        let updates = await response.json();
        console.log(updates)
        updates.forEach(function(anupdate, idx) {
            updatefield(anupdate[0], anupdate[1])
        })
        
}   else {
        alert("HTTP-Error: " + response.status + ': ' + response.statusText);
        ele.disabled = false;
    }
}

function updatefield(fieldid, updates) {
    /*  smart field update to change / set various things about an element. Also logs messages and alerts user
        
        fieldid: id of the field to be changed (can also be 'log' or 'alert' - see below)
        updates: a dict of updates to apply, each entry is key and the new value for the key.
                 accepted keys are:
             value      : new text to be displayed in the field
             disabled   : new value for disabled
             bgcolor    : sets the background colour to value, if value is null, then the bgcolor
                          is removed (allowing the background color from a style or parent element)
                          
        if the fieldid is 'log', then updates is a string that is written to console.log.
        
        if the fieldid is 'alert', then updates is a string that is used as the parameter to alert.
        
    */
    if (fieldid=='log') {
        console.log(updates)
    } else if (fieldid=='alert') {
        alert(updates)
    } else {
        var tempel=document.getElementById(fieldid);
        if (tempel===null){
            console.log("updatefield failed to find field " + fieldid)
        } else {
            for (const [param, newvalue] of Object.entries(updates)) {
                if (param=='value') {
                    if (tempel.nodeName=='INPUT' || tempel.nodeName=='PROGRESS' || tempel.nodeName=='SELECT') {
                        tempel.value=newvalue;
                    } else {
                        tempel.innerHTML=newvalue;
                    }
                } else if (param=='disabled') {
                    tempel.disabled=newvalue;
                } else if (param=='bgcolor') {
                    tempel.style.backgroundColor=newvalue;    
                }
            }
        }
    }
}

function show_hide(etag, img) {
    var ele=document.getElementById(etag);
    var x=ele.style.display;
    if (x=="none") {
        ele.style.display="";
        img.src="static/openuparrow.svg"
    } else {
        img.src="static/opendnarrow.svg"
        ele.style.display="none";
    }
}

function liveupdates(pageid, livekey) {
    var esource = new EventSource("appupdates?pageid="+pageid);
    esource.addEventListener("message", function(e) {
            var newinfo=JSON.parse(e.data);
            do_updates(newinfo);
        }, false);
    esource.addEventListener("open", function(e) {
            console.log('update connection opened');
        }, false);
    esource.addEventListener("error", function(e) {
            if (e.readyState == EventSource.CLOSED) {
                console.log('update connection now closed');
            } else {
                console.log('update connection unhappy')
            }
        }, false);
}