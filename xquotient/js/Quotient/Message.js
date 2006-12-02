
// import MochiKit.DOM

// import Nevow.Athena

Quotient.Message.MessageDetail = Nevow.Athena.Widget.subclass("Quotient.Message.MessageDetail");
Quotient.Message.MessageDetail.methods(
    function __init__(self, node, showMoreDetail) {
        Quotient.Message.MessageDetail.upcall(self, "__init__", node);
        if(showMoreDetail) {
            self.toggleMoreDetail();
        }
    },

    function _getMoreDetailNode(self) {
        if(!self.moreDetailNode) {
            self.moreDetailNode = self.firstNodeByAttribute("class", "detail-toggle");
        }
        return self.moreDetailNode;
    },

    /**
     * Show the source of our message
     *
     * @return: deferred firing with L{Quotient.Message.Source}
     * @rtype: L{Divmod.Defer.Deferred}
     */
    function messageSource(self) {
        var d = self.callRemote("getMessageSource");
        d.addCallback(
            function(widget_info) {
                return self.addChildWidgetFromWidgetInfo(widget_info);
            });
        d.addCallback(
            function(widget) {
                var mbody = self.firstNodeByAttribute("class", "message-body");
                mbody.parentNode.insertBefore(widget.node, mbody);
                mbody.style.display = "none";
                return widget;
            });
        return d;
    },

    /**
     * Show the body of our message
     */
    function showMessageBody(self) {
        var mbody = self.firstNodeByAttribute("class", "message-body")
        mbody.style.display = "";
    },

    /**
     * Toggle the visibility of the "more detail" panel, which contains
     * some extra headers, or more precise values for headers that are
     * summarized or approximated elsewhere.
     *
     * @param node: the toggle link node (if undefined, will locate in DOM)
     * @return: undefined
     */
    function toggleMoreDetail(self, node) {
        if(node == undefined) {
            node = self._getMoreDetailNode();
        }

        node.blur();

        if(node.firstChild.nodeValue == "More Detail") {
            node.firstChild.nodeValue = "Less Detail";
        } else {
            node.firstChild.nodeValue = "More Detail";
        }

        if(!self.headerTable) {
            self.headerTable = self.firstNodeByAttribute("class", "msg-header-table");
        }

        var visible;
        var rows = self.headerTable.getElementsByTagName("tr");
        for(var i = 0; i < rows.length; i++) {
            if(rows[i].className == "detailed-row") {
                if(rows[i].style.display == "none") {
                    rows[i].style.display = "";
                } else {
                    rows[i].style.display = "none";
                }
                if(visible == undefined) {
                    visible = rows[i].style.display != "none";
                }
            }
        }
        return self.callRemote("persistMoreDetailSetting", visible);
    },

    /**
     * Show the original, unscrubbed HTML for this message
     */
    function showOriginalHTML(self) {
        var mbody = self.firstNodeByAttribute("class", "message-body"),
            iframe = mbody.getElementsByTagName("iframe")[0];

        if(iframe.src.match(/\?/)) {
            iframe.src += "&noscrub=1";
        } else {
            iframe.src += "?noscrub=1";
        }

        var sdialog = self.firstNodeByAttribute("class", "scrubbed-dialog");
        sdialog.parentNode.removeChild(sdialog);
    },

    /**
     * Open a window that contains a printable version of
     * the current message
     *
     * @param node: an <a>
     */
    function printable(self) {
        window.open(self.firstNodeByAttribute("class", "printable-link").href);
    },

    /**
     * Present an element that contains an editable list of tags for my message
     */
    function editTags(self) {
        if(!self.tagsDisplayContainer) {
            var tagsContainer = self.firstNodeByAttribute("class", "tags-container");
            self.tagsDisplayContainer = Nevow.Athena.FirstNodeByAttribute(
                                            tagsContainer, "class", "tags-display-container");
            self.tagsDisplay = self.tagsDisplayContainer.firstChild;
            self.editTagsContainer = Nevow.Athena.FirstNodeByAttribute(
                                        tagsContainer, "class", "edit-tags-container");
        }
        var tdc = self.tagsDisplayContainer;
        var input = self.editTagsContainer.getElementsByTagName("input")[0];
        if(self.tagsDisplay.firstChild.nodeValue != "No Tags") {
            input.value = self.tagsDisplay.firstChild.nodeValue;
        }
        tdc.style.display = "none";
        self.editTagsContainer.style.display = "";

        /* IE throws an exception if an invisible element receives focus */
        input.focus();
    },

    function hideTagEditor(self) {
        self.editTagsContainer.style.display = "none";
        self.tagsDisplayContainer.style.display = "";
    },

    /**
     * Inspect the contents of the tag editor element and persist any
     * changes that have occured (deleted tags, added tags)
     */
    function saveTags(self) {
        var _gotTags = self.editTagsContainer.tags.value.split(/,\s*/);
        var  gotTags = [];
        var seen = {};
        for(var i = 0; i < _gotTags.length; i++) {
            if(0 < _gotTags[i].length && !(_gotTags[i] in seen)) {
                seen[_gotTags[i]] = 1;
                gotTags.push(_gotTags[i]);
            }
        }

        var existingTags;
        if(self.tagsDisplay.firstChild.nodeValue == "No Tags") {
            existingTags = [];
        } else {
            existingTags = self.tagsDisplay.firstChild.nodeValue.split(/,\s*/);
        }

        var tagsToDelete = Quotient.Common.Util.difference(existingTags, gotTags);
        var tagsToAdd = Quotient.Common.Util.difference(gotTags, existingTags);

        if(tagsToAdd || tagsToDelete) {
            self.callRemote("modifyTags", tagsToAdd, tagsToDelete);
        }

        if(0 < gotTags.length) {
            self.tagsDisplay.firstChild.nodeValue = gotTags.join(", ");
            if(self.widgetParent) {
                self.widgetParent.addTagsToViewSelector(tagsToAdd);
            }
        } else {
            self.tagsDisplay.firstChild.nodeValue = "No Tags";
        }

        self.hideTagEditor();
    });

Quotient.Message.Source = Nevow.Athena.Widget.subclass('Quotient.Message.Source');
/**
 * Responds to events originating from message source DOM
 */
Quotient.Message.Source.methods(
    /**
     * Called when the user decides they don't want to look at the message
     * source anymore.  Removes our node from the DOM, and calls
     * L{showMessageBody} on our widget parent, which we hope is a
     * L{Quotient.Message.MessageDetail}
     */
    function cancel(self) {
        self.node.parentNode.removeChild(self.node);
        self.widgetParent.showMessageBody();
        return false;
    });
