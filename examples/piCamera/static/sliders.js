function slidersetup() {
    var hslider = document.getElementById("hslider");
    if (hslider) {
        var zl=document.getElementById("cam_zoom_left");
        var zr=document.getElementById("cam_zoom_right");
        if (zl && zr) {
            noUiSlider.create(hslider, {
                start: [zl.value, zr.value],
                connect: true,
                range: {
                    "min": 0,
                    "max": 1
                }
            });
            hslider.noUiSlider.on('end', zoomupdate);
        }
    }
    var vslider = document.getElementById("vslider");
    if (vslider) {
        var zt=document.getElementById("cam_zoom_top");
        var zb=document.getElementById("cam_zoom_bottom");
        if (zt && zb) {
            noUiSlider.create(vslider, {
                start: [parseFloat(zt.value)+10, parseFloat(zb.value)+10],
                orientation: 'vertical',
                connect: true,
                range: {
                    "min": 10,
                    "max": 11
                }
            });
            vslider.noUiSlider.on('end', zoomupdate);
        }
    }
}

function zoomupdate(values, handle, unencoded, tap, positions, noUiSlider) {
    console.log(values);
    var firstv=parseFloat(values[0]);
    if (firstv < 2) {
        var zl=document.getElementById("cam_zoom_left");
        zl.value=values[0];
        field_update(zl, 'float');
        var zr=document.getElementById("cam_zoom_right");
        zr.value=values[1];
        field_update(zr, 'float');
    } else if (firstv < 12) {
        var zt=document.getElementById("cam_zoom_top");
        zt.value=parseFloat(values[0])-10;
        field_update(zt, 'float');
        var zb=document.getElementById("cam_zoom_bottom");
        zb.value=parseFloat(values[1])-10;
        field_update(zb, 'float');
    }
}

function zoomreset() {
    zl=document.getElementById("cam_zoom_left");
    zl.value=0
    field_update(zl, 'float');
    zr=document.getElementById("cam_zoom_right");
    zr.value=1;
    field_update(zr, 'float');
    var hslider = document.getElementById("hslider");
    hslider.noUiSlider.set([0,1]);
    zt=document.getElementById("cam_zoom_top");
    zt.value=0;
    field_update(zt, 'float');
    zb=document.getElementById("cam_zoom_bottom");
    zb.value=1;
    field_update(zb, 'float');
    var vslider = document.getElementById("vslider");
    vslider.noUiSlider.set([10,11]);
}
