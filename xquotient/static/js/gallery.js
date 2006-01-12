// import Quotient.Common

if(typeof(Quotient) == "undefined") {
    Quotient = {};
}

if(typeof(Quotient.Gallery) == "undefined") {
    Quotient.Gallery = {};
}

function quotient_addPerson(targetID) {
    Quotient.Gallery.Controller.get(
        Nevow.Athena.NodeByAttribute(
            document.documentElement, "athena:class", "Quotient.Gallery.Controller"
        )).callRemote("addPerson", targetID);
}

Quotient.Gallery.Controller = Nevow.Athena.Widget.subclass();

Quotient.Gallery.Controller.prototype.setGalleryState = function(data) {
    MochiKit.DOM.getElement("images").innerHTML = data[0];
    MochiKit.DOM.getElement("pagination-links").innerHTML = data[1];
}

Quotient.Gallery.Controller.prototype.prevPage = function() {
    this.callRemote('prevPage').addCallback(this.setGalleryState);
}

Quotient.Gallery.Controller.prototype.nextPage = function() {
    this.callRemote('nextPage').addCallback(this.setGalleryState);
}

