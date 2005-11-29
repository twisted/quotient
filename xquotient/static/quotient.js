function resizeIFrame(frame) {
  // Code is from http://www.ozoneasylum.com/9671&latestPost=true
  try {
    // Get the document within the frame. This is where you will fail with 'permission denied'
    // if the document within the frame is not from the same domain as this document.
    // Note: IE uses 'contentWindow', Opera uses 'contentDocument', Netscape uses either.
    innerDoc = (frame.contentDocument) ? frame.contentDocument : frame.contentWindow.document;


    // Resize the style object, if it exists. Otherwise, resize the frame itself.
    objToResize = (frame.style) ? frame.style : frame;


    // Resize the object to the scroll height of the inner document body. You may still have 
    // to add a 'fudge' factor to get rid of the scroll bar entirely. With a plain-vanilla 
    // iframe, I found Netscape needs no fudge, IE needs 4 and Opera needs 5... 
    // Of course, your mileage may vary.
    objToResize.height = innerDoc.body.scrollHeight + 20 + 'px';
    objToResize.width = innerDoc.body.scrollWidth + 5 + 'px';
  }
  catch (e) {
    window.status = e.message;
  }
}


function resizeIFrameHeight(frame) {
  try {
    innerDoc = (frame.contentDocument) ? frame.contentDocument : frame.contentWindow.document;
    objToResize = (frame.style) ? frame.style : frame;
    objToResize.height = innerDoc.body.scrollHeight + 20 + 'px';
  }
  catch (e) {
    window.status = e.message;
  }
}

function findPosY(obj) {
    var curtop = 0;
    if (obj.offsetParent)
    {
        while (obj.offsetParent)
        {
            curtop += obj.offsetTop
            obj = obj.offsetParent;
        }
    }
    else if (obj.y)
        curtop += obj.y;
    return curtop;
}

function fitMessageDetailToPage() {
    var element = document.getElementById("message-detail");
    element.style.height = document.documentElement.clientHeight - findPosY(element) - 20 + 'px';
}

function loadMessage(messageID) {
    var cpanel = document.getElementById("message-control-panel");
    if(cpanel.style.display == "none")
        cpanel.style.display = "block";
    fitMessageDetailToPage();
    server.handle('loadMessage', messageID);
}
