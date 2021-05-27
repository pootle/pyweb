
var maskxstep;
var maskystep;
var celldownx;
var celldowny;

var lastcellx;
var lastcelly;

var maskcontext;
var maskcanvas;

var mouseisdown=0;
var maskadd=true;

var detectmask=null;

var maskwidth=0;
var maskheight=0;

var maskname=null;

function maskeditflip(btnel) {
    if (btnel.innerHTML =='edit mask') {
        btnel.innerHTML="fetching mask";
        if (confirm('edit existing mask? (cancel to start new mask)')) {
            var mn = prompt("existing file name:", "default");
            if (mn == null) {
                btnel.innerHTML ='edit mask';
            } else {
                btnel.innerHTML=='fetching mask';
                fetchmask(btnel, mn);
            }
        } else {
            fetchmasksize(btnel)
        }
    } else if (btnel.innerHTML =='fetching mask') {
        // do nothing
    } else if (btnel.innerHTML=='finish edit') {
        var mn = maskname;
        if (mn==null) {
            mn='default';
        }
        var saveas=prompt("save changes as?", mn);
        if (saveas == null) {
            btnel.innerHTML ='edit mask'
            var mdiv=document.getElementById("livemaskdiv")
            mdiv.style.display="none";
        } else {
            btnel.innerHTML="saving mask";
            savemask(btnel, saveas)
        }
    } else if (btnel.innerHTML=='saving mask') {
        // do nothing
    } else {
         alert('ooops! ' +  btnel.innerHTML)
    }
}

async function fetchmasksize(btnel) {
    let response = await fetch("fetchmasksize");
    if (response.ok) { // if HTTP-status is 200-299
        let maskinf = await response.json();
        if ("width" in maskinf) {
            btnel.innerHTML="finish edit";
            maskwidth=maskinf['width'];
            maskheight=maskinf['height'];
            detectmask=[];
            for (var i=0;i<maskheight;i++) {
                detectmask[i] = Array(maskwidth).fill(0);
            }
            maskname=null;
            starteditmask();
        } else {
            alert('something wrong')
            btnel.innerHTML= "edit mask";
        }
    } else {
        alert("HTTP-Error: " + response.status);
        btnel.innerHTML="edit mask";
    }
}

async function fetchmask(btnel, mn) {
    let response = await fetch('fetchmask?name='+mn);
    if (response.ok) { // if HTTP-status is 200-299
        let maskinf = await response.json();
        if ("width" in maskinf) {
            btnel.innerHTML="finish edit";
            maskwidth=maskinf['width'];
            maskheight=maskinf['height'];
            if ('mask' in maskinf) {
                detectmask=maskinf['mask'];
            } else {
                detectmask=[];
                for (var i=0;i<maskheight;i++) {
                    detectmask[i] = Array(maskwidth).fill(0);
                }
            }
            if ('name' in maskinf) {
                maskname=maskinf['name']
            } else {
                maskname=null;
            }
            starteditmask();
        } else if ('msg' in maskinf) {
            alert(maskinf['msg'])
            btnel.innerHTML= "edit mask";
        } else {
            alert('something wrong')
            btnel.innerHTML= "edit mask";
        }
    } else {
        alert("HTTP-Error: " + response.status);
        btnel.innerHTML="edit mask";
    }
}

async function savemask(btnel, saveas) {
    let response = await fetch('savemask', {
        headers: {'Content-Type': 'application/json;charset=utf-8'},
        method: 'POST',
        body: JSON.stringify({
            'name': saveas,
            'mask': detectmask
            })
        });
    if (response.ok) {
        let result = await response.json();
        alert(result.message);
    } else {
        alert("HTTP-Error: " + response.status);
    }   
    var mdiv=document.getElementById("livemaskdiv")
    mdiv.style.display="none";
    btnel.innerHTML ='edit mask'
}

function starteditmask() {
    var mdiv=document.getElementById("livemaskdiv")
    mdiv.style.display="block";
    var cstyle=getComputedStyle(mdiv);
    maskcanvas=document.getElementById("livemaskcanv")
    maskcontext=maskcanvas.getContext('2d');
    var cwidth=parseInt(cstyle.getPropertyValue('width'));
    var cheight= parseInt(cstyle.getPropertyValue('height'));
    maskcanvas.width = cwidth;
    maskcanvas.height = cheight;
    maskcontext.lineWidth = 1;
    maskcontext.strokeStyle = '#00000080';
    var x;
    maskxstep=cwidth*1.0/maskwidth;
    for (x=0; x<maskwidth;x++) {
        maskcontext.beginPath();
        var xpos=maskxstep*x;
        maskcontext.moveTo(xpos, 0);
        maskcontext.lineTo(xpos, cheight-1);
        maskcontext.stroke();
    }
    maskystep=cheight*1.0/maskheight;
    for (x=0; x<maskheight;x++) {
        maskcontext.beginPath();
        var xpos=maskystep*x;
        maskcontext.moveTo(0, xpos);
        maskcontext.lineTo(cwidth-1, xpos);
        maskcontext.stroke();
    }
    for (x=0; x<maskwidth; x++) {
        for (var y=0; y<maskheight; y++) {
            if (detectmask[y][x]>0) {
                docell(x,y,true)
            }
        }
    }
    maskcanvas.onmousedown=maskmousedown;
    maskcanvas.onmousemove=maskmousemove;
    maskcanvas.onmouseup=maskmouseup;
}

function maskmousedown(e) {
    celldownx = Math.floor(e.offsetX/maskxstep);
    celldowny = Math.floor(e.offsetY/maskxstep);
    lastcellx=celldownx;
    lastcelly=celldowny;
    maskadd=!e.shiftKey;
    docell(celldownx, celldowny, maskadd);
    mouseisdown=1;
}

function maskmousemove(e) {
    if (mouseisdown) {
        var newdownx = Math.floor(e.offsetX/maskxstep);
        var newdowny = Math.floor(e.offsetY/maskxstep);
        if ((newdownx != lastcellx) || (newdowny != lastcelly)) {
            var xbase=celldownx;
            var xlim =lastcellx;
            if (xlim < xbase) {
                xbase=xlim;
                xlim =celldownx;
            }
            var ybase=celldowny;
            var ylim =lastcelly;
            if (ylim < ybase) {
                ybase=ylim;
                ylim=celldowny;
            }
            for (var x=xbase; x <= xlim; x++) {
                for (var y=ybase; y <= ylim; y++) {
                    docell(x,y,false);
                }
            }
            if (maskadd) {
                xbase=celldownx;
                xlim =newdownx;
                if (xlim < xbase) {
                    xbase=xlim;
                    xlim =celldownx;
                }
                var ybase=celldowny;
                var ylim =newdowny;
                if (ylim < ybase) {
                    ybase=ylim;
                    ylim=celldowny;
                }
                var x;
                var y;
                for (x=xbase; x <= xlim; x++) {
                    for (y=ybase; y <= ylim; y++) {
                        docell(x,y,true);
                    }
                }
            }
            lastcellx=newdownx;
            lastcelly=newdowny;
        }       
    }
}

function maskmouseup(e) {
    mouseisdown=0
}

function docell(cellx, celly, cellon) {
    maskcontext.clearRect(cellx*maskxstep+1, celly*maskystep+1, maskxstep-2, maskystep-2)
    if (cellon) {
        maskcontext.fillStyle = '#c000c0a0';
        maskcontext.fillRect(cellx*maskxstep+1, celly*maskystep+1, maskxstep-2, maskystep-2);
    }
    var cellval=0;
    if (cellon) {
        cellval=1;
    }
    detectmask[celly][cellx]=cellval;
}