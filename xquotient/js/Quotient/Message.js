
// import MochiKit.DOM

// import Nevow.Athena

Quotient.Message.MessageDetail = Nevow.Athena.Widget.subclass("Quotient.Message.MessageDetail");
Quotient.Message.MessageDetail.methods(
    function __init__(self, node, tags, showMoreDetail) {
        Quotient.Message.MessageDetail.upcall(self, "__init__", node);

        var tagsContainer = self.firstNodeByAttribute(
            "class", "tags-container");
        self.tagsDisplayContainer = Nevow.Athena.FirstNodeByAttribute(
            tagsContainer, "class", "tags-display-container");
        self.tagsDisplay = self.tagsDisplayContainer.firstChild;
        self.editTagsContainer = Nevow.Athena.FirstNodeByAttribute(
            tagsContainer, "class", "edit-tags-container");


        if(showMoreDetail) {
            self.toggleMoreDetail();
        }
        self.tags = tags;
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
        var mbody = self.firstNodeByAttribute("class", "message-body");
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
     * Make the necessary DOM changes to allow editing of the tags of this
     * message.  This involves showing, populating and focusing the tag text
     * entry widget
     */
    function editTags(self) {
        var input = self.editTagsContainer.tags;
        if(self.tagsDisplay.firstChild.nodeValue != "No Tags") {
            input.value = self.tags.join(', ');
        }
        self.tagsDisplayContainer.style.display = "none";
        self.editTagsContainer.style.display = "";

        /* IE throws an exception if an invisible element receives focus */
        input.focus();
    },

    function hideTagEditor(self) {
        self.editTagsContainer.style.display = "none";
        self.tagsDisplayContainer.style.display = "";
    },

    /**
     * Event-handler for tag saving.
     *
     * @return: C{false}
     */
    function dom_saveTags(self) {
        var tags = self.editTagsContainer.tags.value.split(/,\s*/),
            nonEmptyTags = [];
        for(var i = 0; i < tags.length; i++) {
            if(0 < tags[i].length) {
                nonEmptyTags.push(tags[i]);
            }
        }
        self.saveTags(nonEmptyTags).addCallback(
            function(ignored) {
                self._updateTagList();
                self.hideTagEditor();
            });
        return false;
    },

    /**
     * Tell our parent widget to select the tag C{tag}
     *
     * @param tag: the name of the tag to select
     * @type tag: C{String}
     */
    function chooseTag(self, tag) {
        if(self.widgetParent != undefined
            && self.widgetParent.chooseTag != undefined) {
            return self.widgetParent.chooseTag(tag);
        }
    },

    /**
     * Event-handler for tag choosing
     *
     * @param node: the tag link node
     * @type node: node
     *
     * @return: C{false}
     */
    function dom_chooseTag(self, node) {
        self.chooseTag(node.firstChild.nodeValue);
        return false;
    },

    /**
     * Update the tag list of our message
     */
    function _updateTagList(self) {
        while(self.tagsDisplay.firstChild) {
            self.tagsDisplay.removeChild(
                self.tagsDisplay.firstChild);
        }
        function makeOnclick(node) {
            return function() {
                return self.dom_chooseTag(node);
            }
        }
        for(var i = 0; i < self.tags.length; i++) {
            /* XXX template */
            var node = document.createElement("a");
            node.href = "#";
            node.className = "tag";
            node.onclick = makeOnclick(node);
            node.appendChild(document.createTextNode(self.tags[i]));
            self.tagsDisplay.appendChild(node);
        }
        if(i == 0) {
            self.tagsDisplay.appendChild(
                document.createTextNode("No Tags"));
        }
    },

    /**
     * Modify the tags for this message.
     *
     * @param tags: all of the tags for this message
     * @type tags: C{Array} of C{String}
     *
     * @rtype: L{Divmod.Defer.Deferred}
     */
    function saveTags(self, tags) {
        tags = Quotient.Common.Util.uniq(tags);
        var tagsToDelete = Quotient.Common.Util.difference(self.tags, tags),
            tagsToAdd = Quotient.Common.Util.difference(tags, self.tags),
            D;

        if(0 < tagsToAdd.length || 0 < tagsToDelete.length) {
            D = self.callRemote("modifyTags", tagsToAdd, tagsToDelete);
            D.addCallback(
                function(tags) {
                    self.tags = tags;
                });
        } else {
            D = Divmod.Defer.succeed(null);
        }
        D.addCallback(
            function(ignored) {
                if(0 < tagsToAdd.length
                    && self.widgetParent != undefined
                    && self.widgetParent.addTagsToViewSelector != undefined) {
                    self.widgetParent.addTagsToViewSelector(tagsToAdd);
                }
            });
        return D;
    });

/**
 * Message body control code which interacts with the DOM
 */
Quotient.Message.BodyView = Divmod.Class.subclass('Quotient.Message.BodyView');
Quotient.Message.BodyView.methods(
    function __init__(self, node) {
        self.node = node;
    },

    /**
     * Figure out the alternate MIME type linked to by node C{node}
     *
     * @param node: the alternate MIME type link
     * @type node: <a> node
     *
     * @return: the MIME type
     * @rtype: C{String}
     */
    function getMIMETypeFromNode(self, node) {
        return node.firstChild.nodeValue;
    },

    /**
     * Replace our node with another node
     *
     * @type node: node
     *
     * @rtype: C{undefined}
     */
    function replaceNode(self, node) {
        self.node.parentNode.insertBefore(node, self.node);
        self.node.parentNode.removeChild(self.node);
    });

/**
 * Message body control code which responds to events
 */
Quotient.Message.BodyController = Nevow.Athena.Widget.subclass('Quotient.Message.BodyController');
Quotient.Message.BodyController.methods(
    function __init__(self, node) {
        self.view = Quotient.Message.BodyView(node);
        Quotient.Message.BodyController.upcall(self, '__init__', node);
    },

    /**
     * Retrieve and display the component of this message with MIME type
     * C{type}
     *
     * @param type: MIME type
     * @type type: C{String}
     *
     * @rtype: L{Divmod.Defer.Deferred}
     */
    function chooseDisplayMIMEType(self, type) {
        var D = self.callRemote('getAlternatePartBody', type);

        D.addCallback(
            function(widget_info) {
                return self.addChildWidgetFromWidgetInfo(widget_info);
            });
        D.addCallback(
            function(widget) {
                self.view.replaceNode(widget.node);
                return widget;
            });
        return D;
    },

    /**
     * DOM event handler which wraps L{chooseDisplayMIMEType}
     */
    function dom_chooseDisplayMIMEType(self, node) {
        var type = self.view.getMIMETypeFromNode(node);
        self.chooseDisplayMIMEType(type);
        return false;
    });

Quotient.Message.Source = Nevow.Athena.Widget.subclass('Quotient.Message.Source');
/**
 * Responds to events originating from message source DOM.  Assumes a widget
 * parent with a L{showMessageBody} method
 */
Quotient.Message.Source.methods(
    /**
     * Called when the user decides they don't want to look at the message
     * source anymore.  Removes our node from the DOM, and calls
     * L{showMessageBody} on our widget parent
     */
    function cancel(self) {
        self.node.parentNode.removeChild(self.node);
        self.widgetParent.showMessageBody();
        return false;
    });
