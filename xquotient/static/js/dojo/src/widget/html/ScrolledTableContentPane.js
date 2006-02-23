/*
	Copyright (c) 2004-2005, The Dojo Foundation
	All Rights Reserved.

	Licensed under the Academic Free License version 2.1 or above OR the
	modified BSD license. For more information on Dojo licensing, see:

		http://dojotoolkit.org/community/licensing.shtml
*/

dojo.provide("dojo.widget.html.ScrolledTableContentPane");

dojo.require("dojo.widget.html");
dojo.require("dojo.widget.Container");
dojo.require("dojo.widget.html.ContentPane");
dojo.require("dojo.widget.ScrolledTableContentPane");

dojo.widget.html.ScrolledTableContentPane = function(){
	dojo.widget.html.Container.call(this);
}
dojo.inherits(dojo.widget.html.ScrolledTableContentPane, dojo.widget.html.ContentPane);

dojo.lang.extend(dojo.widget.html.ScrolledTableContentPane, {
    widgetType: "ScrolledTableContentPane",

    onResized: function() {
        if(!this._scrollElement) {
            this._scrollElement = Nevow.Athena.NodeByAttribute(
                                        this.domNode, 'class', 'scroll-viewport');
            this._scrollWidget = Mantissa.ScrollTable.ScrollingWidget.get(
                                    this._scrollElement);
        }
        this._scrollElement.style.height = (this.sizeActual - 40) + 'px';
        this._scrollWidget.scrolled();
    
    }});

dojo.widget.tags.addParseTreeHandler("dojo:ScrolledTableContentPane");
