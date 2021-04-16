function field_changed(ele) {
    notify(ele, "notify?t="+ele.id+"&v="+ele.value);
}

function appClickNotify(ele) {
    notify(ele, "notify?t="+ele.id+"&v=0");
}

async function notify(ele, fs) {
    ele.disabled=true;
    let response = await fetch(fs);
    if (response.ok) { // if HTTP-status is 200-299
        if (response.status != 204) {   //  if it is 204 then nothing more to do
            let resp = await response.text();
            console.log('response:' + resp);
            let msg = JSON.parse(resp);
            if (msg.OK) {
                if ('value' in msg) {
                    if (ele.nodeName=='SELECT') {
                        // skip update for now
                    } else if (ele.nodeName=='INPUT') {
                        ele.value=msg.value;
                    } else {
                        ele.innerText=msg.value;
                    }
                } else if ('updates' in msg) {
                     do_updates(msg.updates);
                }
            } else {
                alert(msg.fail);
            }
        }
        console.log('good status from request >' + fs + '<, msg: ' + response.statusText);
    } else {
        console.log('bad status from request >' + fs + '<, msg: ' + response.statusText);
        alert("HTTP-Error: " + response.statusText);
    }
    ele.disabled=false;
}

function do_updates(newinfo) {
    if (newinfo=='kwac') {
        console.log('update nothing')
    } else {
        newinfo.forEach(function(update, idx) {
            console.log(update[0] + ' is ' + update[1]);
            var tempel=document.getElementById(update[0]);
            if (tempel) {
                if (tempel.nodeName=='INPUT' || tempel.nodeName=='PROGRESS') {
                    tempel.value=update[1];
                } else {
                    tempel.innerHTML=update[1];
                }
            }
        });
    }
}

function flipme(etag, img) {
    var ele=document.getElementById(etag);
    var x=ele.style.display;
    if (x=="none") {
        ele.style.display="";
        img.src="static/openuparrow.png"
    } else {
        img.src="static/opendnarrow.png"
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