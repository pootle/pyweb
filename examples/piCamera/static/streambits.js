function livestreamflip(btnel) {
    var imele=document.getElementById("livestreamimg");
    if (imele.src.endsWith("nocam.png")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 ) {
        imele.src="camstream"
        btnel.innerHTML="hide livestream"
        console.log('live stream stopped')
    } else {
        imele.src="static/nocam.png"
        btnel.innerHTML="show livestream"
        console.log('live stream started')
    }
}