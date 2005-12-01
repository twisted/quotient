var ALLTAGS = new Array();
var LAST_SELECTED_ROW = null;

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

function setTags(tags) { ALLTAGS = ALLTAGS.concat(eval("(" + tags + ")")); }

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

function findPosX(obj) {
    var curleft = 0;
    if (obj.offsetParent)
    {
        while (obj.offsetParent)
        {
            curleft += obj.offsetLeft
            obj = obj.offsetParent;
        }
    }
    else if (obj.x)
        curleft += obj.x;
    return curleft;
}

function fitMessageDetailToPage() {
    var element = document.getElementById("split-message-detail");
    /* this is a hack */
    if(0 < element.childNodes.length)
        element.style.height = innerWindowHeight() - findPosY(element) - 20 + 'px';
}

function normalizeTag(tag) {
    return tag.replace(/^\s+/, "").replace(/\s+$/, "").replace(/\s{2,}/, " ");
}

function startswith(needle, haystack) {
    return haystack.slice(0, needle.length) == needle;
}

function completeCurrentTag(tags) {
    var tags = tags.split(/,/);
    var last = normalizeTag(tags[tags.length - 1]);

    var complContainer = document.getElementById("tag-completions");
    purgeChildren(complContainer);

    if(last.length == 0)
        return;

    var completions = new Array();
    for(var i = 0; i < ALLTAGS.length; i++)
        if(startswith(last, ALLTAGS[i]))
            completions.push(ALLTAGS[i]);

    for(i = 0; i < completions.length; i++) {
        var link = document.createElement("a");
        link.setAttribute("href", "#");
        link.setAttribute("onclick",
                          "appendCompletion(this.firstChild.nodeValue); return false");
        if(i == 0)
            link.setAttribute("style", "font-weight: bold");
        link.appendChild(document.createTextNode(completions[i]));
        complContainer.appendChild(link);

        if(i < completions.length-1)
            complContainer.appendChild(document.createTextNode(", "))
    }
}

function appendCompletion(word) {
    var input = document.getElementById("add-tags-dialog-text-input");
    var tags = input.value.split(/,/);
    var last = normalizeTag(tags[tags.length-1]);
    input.value += word.slice(last.length, word.length) + ", ";
    purgeChildren(document.getElementById("tag-completions"));
    input.focus();
}

function onCompletionKeyDown(event) {
    if(event.keyCode == 9) { // tab was pressed
        /* if we have at least one completion being displayed,
           select the first one, and purge all completions */
        var completions = document.getElementById("tag-completions");
        if(0 < completions.childNodes.length) {
            appendCompletion(completions.firstChild.firstChild.nodeValue);
            purgeChildren(completions);
        }
        event.cancel = true;
        event.returnValue = false;
        event.preventDefault();
        return false;
    } else if(event.keyCode == 8) { // delete was pressed
        // recalculate completions of current tag
        var tags = event.originalTarget.value;
        if(0 < tags.length)
            tags = tags.slice(0, tags.length-1);
        completeCurrentTag(tags);
    }
    return true;
}

function centerAndDisplayDialog(dialog) {
    var middleX = innerWindowWidth() / 2;
    var middleY = innerWindowHeight() / 2;

    dialog.style.display = "";
    dialog.style.visibility = "hidden";
    dialog.style.left = middleX - (dialog.clientWidth / 2);
    dialog.style.top  = middleY - (dialog.clientHeight / 2);
    dialog.style.visibility = "visible";
}

function purgeChildren(e) {
    while(0 < e.childNodes.length)
        e.removeChild(e.firstChild);
}

function addTags() {
    document.getElementById("tags-plus").style.display = "none";
    document.getElementById("tags-minus").style.display = "";

    var tagdialog = document.getElementById("add-tags-dialog");
    tagdialog.style.display = "";
    document.getElementById("add-tags-dialog-text-input").focus();
}

function hideTags() {
    document.getElementById("tags-plus").style.display = "";
    document.getElementById("tags-minus").style.display = "none";
    document.getElementById("add-tags-dialog").style.display = "none";
}

function innerWindowHeight() {
    return document.getElementsByTagName("body")[0].clientHeight;
}

function innerWindowWidth() {
    return document.getElementsByTagName("body")[0].clientWidth;
}

function addTag(form) {
    var mtags = document.getElementById("message-tags");
    purgeChildren(mtags);
    mtags.appendChild(document.createTextNode("Loading..."));

    var tag = form.tag.value;
    var tags = null;
    if(tag.match(/,/))
        tags = tag.split(/,/);
    else
        tags = [tag];

    for(var i = 0; i < tags.length; i++) {
        tag = normalizeTag(tags[i]);
        ALLTAGS.push(tag);
        if(0 < tag.length) // FIXME: add them all at once
            server.handle("addTag", tag);
    }
    form.tag.value = ""; form.tag.focus();
    hideTags();
}

function closeAddTagsDialog() {
    var dlg = document.getElementById("add-tags-dialog");
    with(dlg.style) {
        display = "none";
        left = top = 0;
    }
}

function setChildBGColors(e, color) {
    for(var i = 0; i < e.childNodes.length; i++)
        if(e.childNodes[i].tagName)
            e.childNodes[i].style.backgroundColor = color;
}

function highlightMessageAtOffset(offset) {
    var row = document.getElementById("tdb-item-" + offset);
    if(LAST_SELECTED_ROW)
        setChildBGColors(LAST_SELECTED_ROW, "");
    LAST_SELECTED_ROW = row;
    setChildBGColors(row, "#FFFF00");
}

function loadMessage(messageLink, messageID) {
    /*
    if(LAST_SELECTED_ROW)
        setChildBGColors(LAST_SELECTED_ROW, "");

    var parentRow = messageLink.parentNode.parentNode;
    setChildBGColors(parentRow, "#FFFF00");
    LAST_SELECTED_ROW = parentRow;
    */
    fitMessageDetailToPage();
    server.handle('loadMessage', messageID);
}

function nextMessage() { server.handle('nextMessage') }
function nextUnreadMessage() { server.handle('nextUnreadMessage') }
function prevMessage() { server.handle('prevMessage') }
