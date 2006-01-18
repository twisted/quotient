// import Quotient.Common

if(typeof(Quotient) == "undefined") {
    Quotient = {};
}

if(typeof(Quotient.Gallery) == "undefined") {
    Quotient.Gallery = {};
}

Quotient.Gallery.Controller = Nevow.Athena.Widget.subclass();

Quotient.Gallery.Controller.method("setGalleryState",
    function(self, data) {
        document.getElementById("images").innerHTML = data[0];
        document.getElementById("pagination-links").innerHTML = data[1];
    });

Quotient.Gallery.Controller.method("prevPage",
    function(self) {
        self.callRemote('prevPage').addCallback(
            function(gs) { self.setGalleryState(gs) });
    });

Quotient.Gallery.Controller.method("nextPage",
    function(self) {
        self.callRemote('nextPage').addCallback(
            function(gs) { self.setGalleryState(gs) });
    });

