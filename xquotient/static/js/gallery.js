// import Quotient
// import Quotient.Common
// import LightBox

if(typeof(Quotient.Gallery) == "undefined") {
    Quotient.Gallery = {};
}

Quotient.Gallery.Controller = Nevow.Athena.Widget.subclass("Quotient.Gallery.Controller");

Quotient.Gallery.Controller.methods(
    function setGalleryState(self, data) {
        document.getElementById("images").innerHTML = data[0];
        document.getElementById("pagination-links").innerHTML = data[1];
        initLightbox();
    },

    function prevPage(self) {
        self.callRemote('prevPage').addCallback(
            function(gs) { self.setGalleryState(gs) });
    },

    function nextPage(self) {
        self.callRemote('nextPage').addCallback(
            function(gs) { self.setGalleryState(gs) });
    });
