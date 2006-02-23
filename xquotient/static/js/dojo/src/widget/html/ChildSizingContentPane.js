dojo.provide("dojo.widget.html.ChildSizingContentPane");

dojo.require("dojo.widget.html");
dojo.require("dojo.widget.Container");
dojo.require("dojo.widget.html.ContentPane");

dojo.widget.html.ChildSizingContentPane = function(){
	dojo.widget.html.Container.call(this);
}
dojo.inherits(dojo.widget.html.ChildSizingContentPane, dojo.widget.html.ContentPane);

dojo.lang.extend(dojo.widget.html.ChildSizingContentPane, {
    widgetType: "ChildSizingContentPane",

    onResized: function() {
        this.domNode.firstChild.style.height = (this.sizeActual - 40) + 'px';
    
    }});

dojo.widget.tags.addParseTreeHandler("dojo:ChildSizingContentPane");
