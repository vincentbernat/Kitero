// Kitero namespace
var kitero = kitero || {};

$(function() {

    // Proxy object for `console`.
    kitero.console = function() {
	var names = ["log", "debug", "info", "warn", "error", "trace"];
	var that = {};
	function callFirebugConsole(f) {
            return function () {
                if (typeof console !== "undefined" && console[f] && console[f].apply) {
                    return console[f].apply(console, arguments);
                }
            };
        }
	for (var i = 0; i < names.length; ++i) {
            that[names[i]] = callFirebugConsole(names[i]);
        }
	return that;
    }();

    // Subnamespaces for models, views and collections
    kitero.model = kitero.model || {};
    kitero.view = kitero.view || {};
    kitero.collection = kitero.collection || {};

    // Models
    // ------

    // Current client settings (IP, current interface, current QoS).
    // All other models should refer to this one to know the active
    // interface and QoS and register for change event if they want to
    // be kept updated. Most views should listen to events from this
    // model.
    kitero.model.Settings = Backbone.Model.extend({
	defaults: {
	    ip          : null,
	    interface   : null, // current interface name (server side)
	    qos         : null,	// current qos name (server side)
	    s_interface : null,	// selected interface (client side)
	    s_qos       : null	// selected qos (client side)
	},
	url: "api/1.0/current",
	parse: function(response) {
	    // First, check if the answer status code is appropriate
	    if (response.status !== 0) {
		var error = "/api/1.0/current request returned non-0 status";
		kitero.console.error(error, response);
		throw error;
	    }
	    // Complete the answer with currently selected values
	    _.defaults(response.value,
		       { s_interface: this.get("s_interface") || response.value.interface,
			 s_qos: this.get("s_qos") || response.value.qos });
	    return response.value;
	},
	// Do we need to save the new settings
	needs_apply: function() {
	    return ((this.get("s_interface") !== this.get("interface")) ||
		    (this.get("s_qos") !== this.get("qos")));
	},
	save: function(attr, options) {
	    // Override save to use our URL scheme.
	    // PUT or POST is not important. Both works.
	    options || (options = {});
	    options.url || (options.url = this.url + "/../interface/" + 
			    encodeURIComponent(this.get("s_interface")) + "/" +
			    encodeURIComponent(this.get("s_qos")));
	    return Backbone.Model.prototype.save.call(this, attr, options);
	},
	// Reset to server-side state
	reset: function() {
	    this.set({ s_interface: this.get("interface"),
		       s_qos: this.get("qos") });
	}
    });

    // Instead of keeping a reference to client settings in all other
    // models, we use a variable in our namespace. It should be
    // initialized later.
    kitero.settings = null;

    // Model for a QoS setting. Some views may listen to
    // `change:selected` event to update visual status of the QoS. For
    // other purposes, it is better to listen to `change` event from
    // `kitero.model.Settings` instance.
    kitero.model.QoS = Backbone.Model.extend({
	defaults: {
	    name: null,
	    description: "",
	    selected: false,	// selected (client-side)
	    interface: null	// ID of the interface (not a reference)
	}
    });

    // A collection of QoS settings.
    kitero.collection.QoS = Backbone.Collection.extend({
	model: kitero.model.QoS
    });

    // Model for one interface (with its list of associated QoS
    // settings)
    kitero.model.Interface = Backbone.Model.extend({
	defaults: {
	    name: null,
	    description: "",
	    qos: null
	},
	initialize: function() {
	    _.bindAll(this, 'update_selected');
	    this.update_selected();
	    if (kitero.settings)
		kitero.settings.bind("change", this.update_selected);
	},
	// Update the `selected` attribute to match the selected client
	// settings (from `kitero.settings`).
	update_selected: function() {
	    if (!kitero.settings) return;
	    var selected_interface = kitero.settings.get("s_interface");
	    var selected_qos = kitero.settings.get("s_qos");
	    var cqos = this.get("qos");
	    if (cqos) {
		// For each QoS in the collection, the QoS is marked
		// as selected if the interface match and if the QoS
		// match.
		cqos.each(function(q) {
		    q.set({selected:
			   ((selected_interface === this.id) &&
			    (selected_qos === q.id))})
		}, this);
	    }
	}
    });

    // A collection of interfaces. This collection can be fetched from
    // the web service.
    kitero.collection.Interfaces = Backbone.Collection.extend({
	model: kitero.model.Interface,
	url: "api/1.0/interfaces",
	parse: function(response) {
	    // Check the answer status
	    if (response.status !== 0) {
		var error = "/api/1.0/interfaces request returned non-0 status";
		kitero.console.error(error, response);
		throw error;
	    }
	    // Transform the answer into an array.
	    var answer = _.map(response.value, function(interface, eth) {
		// QoS should be instantiated properly
		var qos = new kitero.collection.QoS(
		    _.map(interface.qos, function(value, key) {
			return new kitero.model.QoS({ id: key,
						      name: value.name,
						      description: value.description,
						      interface: eth
						    });
		    }));
		return { id: eth,
			 name: interface.name,
			 description: interface.description,
			 qos: qos
		       }
	    });
	    return answer;
	},
	// Current interface
	interface: function() {
	    return this.get(kitero.settings.get("interface"));
	},
	// Current QoS
	qos: function() {
	    var qos = this.interface() && this.interface().get("qos");
	    return (qos && qos.get(kitero.settings.get("qos")));
	}
    })

    // Views
    // -----

    // Current settings header
    kitero.view.Settings = Backbone.View.extend({
	el: $("#kitero-header"),
	initialize: function() {
	    _.bindAll(this, 'render');
	    // Render should be triggered when settings are changed or
	    // when new interfaces are received.
	    kitero.settings.bind("change", this.render);
	    this.model.bind("reset", this.render);
	},
	render: function() {
	    // Setup template variables
	    var display = {};
	    display['IP'] = kitero.settings.get("ip") || 'Unknown';
	    var interface = this.model.interface();
	    display['interface'] = interface && interface.get("name") || 'None';
	    var qos = this.model.qos();
	    display['qos'] = qos && qos.get("name") || 'None';
	    // Remove old information and render the new one
	    this.el.children(":not(script)").remove();
	    $("#kitero-header-template").tmpl(display).appendTo(this.el);
	    return this;
	}
    });
    // QoS
    kitero.view.QoS = Backbone.View.extend({
	tagName: "li",
	events: {
	    "click": "select"
	},
	initialize: function() {
	    _.bindAll(this, "render", "update_selected");
	    this.model.bind("change:selected", this.update_selected);
	},
	// User selects this QoS
	select: function() {
	    var target = { s_interface: this.model.get("interface"),
			   s_qos: this.model.id };
	    kitero.console.debug("Select interface %s and QoS %s",
				 target.s_interface, target.s_qos);
	    kitero.settings.set(target);
	},
	update_selected: function() {
	    $(this.el).toggleClass("kitero-qos-selected", this.model.get("selected"));
	},
	render: function() {
	    kitero.console.debug("Render QoS %s", this.model.get("name"), this);
	    $("#kitero-qos-template").tmpl(this.model.toJSON()).appendTo($(this.el));
	    this.update_selected();
	    return this;
	}
    });
    // Interfaces
    kitero.view.Interfaces = Backbone.View.extend({
	el: $("#kitero-conns"),
	initialize: function() {
	    _.bindAll(this, 'render');
	    this.model.bind("reset", this.render);
	},
	render: function() {
	    this.el.children(":not(script)").remove();
	    this.model.each(function(interface) {
		// We should delegate this to another view,
		// unfortunately, we need two elements to build such a
		// view and backbone.js does not easily allows
		// this. Therefore, the view for interfaces also
		// happens to be the view for invidual interfaces.
		kitero.console.debug("Render interface %s", interface.get("name"), interface);
		var html = $("#kitero-conn-template").tmpl(interface.toJSON());
		if (!interface.get("qos")) {
		    kitero.console.warning("No QoS for this interface:", interface);
		    return;
		}
		interface.get("qos").each(function(qq, q) {
		    var qos = new kitero.view.QoS({model: qq});
		    html.find(".kitero-qos").append(qos.render().el);
		});
		html.appendTo(this.el);
	    }, this);
	    this.el.accordion( { icons: {
		header: 'ui-icon-circle-triangle-e',
		headerSelected: 'ui-icon-circle-triangle-s'},
                                 header: 'div.kitero-conn',
                                 active: 1 });
	    return this;
	}
    });

    // Our main application
    kitero.view.Application = Backbone.View.extend({
	events: {
	    'click #apply'  : "apply_changes",
	    'click #cancel' : "reset_changes"
	},
	initialize: function() {
	    kitero.console.info("Starting Kitérő.")
	    _.bindAll(this, 'render', 'toggle_buttons');
	    // Initialize models
	    this.settings = kitero.settings = new kitero.model.Settings;
	    this.interfaces = new kitero.collection.Interfaces;
	    this.settings.bind("change", this.render);
	    this.settings.bind("change", this.toggle_buttons);
	    this.interfaces.bind("reset", this.render);
	    // Initialize views. The associated model is a collection
	    // of interfaces because we already have access to the
	    // current settings through `kitero.settings`.
	    this.settingsView = new kitero.view.Settings({model: this.interfaces});
	    this.interfacesView = new kitero.view.Interfaces({model: this.interfaces});
	    // Fetch settings and interfaces from the web service
	    this.settings.fetch();
	    this.interfaces.fetch();
	},
	// Enable or disable OK/Cancel buttons
	toggle_buttons: function() {
	    this.$('#cancel,#apply').button(
		(!this.saving && this.settings.needs_apply())?"enable":"disable");
	},
	// Apply changes
	apply_changes: function(event) {
	    event.preventDefault();
	    // Toggle "saving" flag
	    this.saving = true;
	    this.toggle_buttons();
	    var view = this;
	    // To be done: handle error case
	    kitero.settings.save(null,
				 { success: function() {
				     view.saving = false;
				     view.toggle_buttons(); // Useless, but we don't know
				     }
				 });
	},
	// Reset changes
	reset_changes: function(event) {
	    event.preventDefault();
	    kitero.settings.reset();
	},
	render: function() {
	    // We render only if we have both appropriate settings and
	    // some interfaces to display. Otherwise, we stay in
	    // loading state.
	    if (this.settings.get("ip") && this.interfaces.length !== 0) {
		kitero.console.debug("Display interface.")
		// Initialize OK and cancel buttons
		this.$('#cancel').button({icons: {primary: 'ui-icon-circle-close'},
					  disabled: true});
		this.$('#apply').button({icons: {primary: 'ui-icon-circle-check'},
					 disabled: true});
		$("html").removeClass("loading");
		// No need to redisplay the interface once it is displayed
		this.settings.unbind("change", this.render);
		this.interfaces.unbind("reset", this.render);
	    }
	    return this;
	}
    });

    // Instantiate Kitérő.
    kitero.app = new kitero.view.Application({el: $("#kitero-interface")});
});
