// Kitero namespace
var kitero = kitero || {};

$(function() {

    // Helper function. Stolen from:
    //  http://phpjs.org/functions/base64_encode:358
    function base64_encode (data) {
	var b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
	var o1, o2, o3, h1, h2, h3, h4, bits, i = 0,
        ac = 0,
        enc = "",
        tmp_arr = [];
	if (!data) {
            return data;
	}

	do {
            o1 = data.charCodeAt(i++);
            o2 = data.charCodeAt(i++);
            o3 = data.charCodeAt(i++);
            bits = o1 << 16 | o2 << 8 | o3;
            h1 = bits >> 18 & 0x3f;
	    h2 = bits >> 12 & 0x3f;
            h3 = bits >> 6 & 0x3f;
            h4 = bits & 0x3f;
	    tmp_arr[ac++] = b64.charAt(h1) + b64.charAt(h2) + b64.charAt(h3) + b64.charAt(h4);
	} while (i < data.length);

	enc = tmp_arr.join('');
        var r = data.length % 3;
	return (r ? enc.slice(0, r - 3) : enc) + '==='.slice(r || 3);
    }

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
	    kitero.console.log(options);
	    options || (options = {});
	    options.url || (options.url = this.url + "/../bind/" + 
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
    kitero.stats = null;	// Same for stats

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
    });

    // Stats about all interfaces
    kitero.model.Stats = Backbone.Model.extend({
	url: "api/1.0/stats",
	initialize: function() {
	    this.last = {
		time: null,
		value: null
	    };
	    this.keep = 60;	// Keep 60 values
	},
	parse: function(response) {
	    var now = {
		time: response.time,
		value: response.value
	    };
	    if (_(this.last.time).isNull()) {
		this.last = now;
		return {};	// No value available yet, next time
	    }
	    var append = function(now, prev, target, delta, keep) {
		// This function will append attributes from `now'
		// into attributes of `target', recursively, with
		// derivation if needed from `prev` assuming `delta`
		// seconds between `now` and `prev`.

		// 1. Expand existing values
		var result = _(target)
		    .map(function(value, key) {
			if (_(value).isArray()) {
			    // Leaf
			    var val;
			    var result = value;
			    if (key == "up" || key == "down") {
				// We need to derivate value
				if (_.isUndefined(now[key]) ||
				    _.isUndefined(prev[key]))
				    val = null;
				else
				    val = (now[key] - prev[key])/delta;
			    } else
				val = now[key];
			    // Append the new value
			    if (_.isUndefined(val)) val = null;
			    result.unshift(val);
			    if (result.length > keep) result.pop();
			    // Only return the result if it is not all null
			    if (_.all(result, _.isNull)) return null;
			    return { id: key,
				     value: result };
			} else {
			    var n = append(_.isUndefined(now[key])?{}:now[key],
					   _.isUndefined(prev[key])?{}:prev[key],
					   value,
					   delta, keep);
			    if (_.isEmpty(n)) return null;
			    return { id: key,
				     value: n };
			}
		    });

		// 2. Turn back result into a dictionary
		result = _.reduce(result, function(result, pack) {
		    if (!_.isNull(pack))
			result[pack.id] = pack.value;
		    return result;
		}, {});

		// 3. Add new values
		_(now).each(function(value, key) {
		    if (!_.isUndefined(result[key])) return;
		    if (_(value).isNumber()) {
			if (key == "up" || key == "down") {
			    if (_.isUndefined(prev[key]))
				return;
			    result[key] = [ (now[key] - prev[key])/delta ]
			    return;
			}
			result[key] = [ value ];
			return;
		    }
		    result[key] = append(now[key],
					 _.isUndefined(prev[key])?{}:prev[key],
					 {},
					 delta, keep);
		});

		// 4. Return
		return result;
	    };
	    var delta = now.time - this.last.time;
	    if (delta === 0)
		return this.toJSON();
	    var result =  append(now.value, this.last.value,
				 this.toJSON(), delta, this.keep);
	    this.last = now;
	    return result;
	}
    });

    // Views
    // -----

    // Stats window
    kitero.view.Stats = Backbone.View.extend({
	className: "kitero-stats-view",
	initialize: function() {
	    _.bindAll(this, "update", "render", "close");
	    kitero.stats.bind("poll", this.update);
	},
	close: function() {
	    
	},
	render: function() {
	    $("#kitero-stats-template")
		.tmpl({interface: this.model.get("name")})
		.appendTo(this.el);
	    $(this.el).dialog({ title: "Statistics for " + this.model.get("name"),
				close: this.close,
				resize: this.update,
				width: 700,
				height: $("body").height()*3/4 });
	    this.update();
	    return this;
	},
	close: function() {
	    kitero.stats.unbind("poll", this.update);
	    this.remove();
	},
	update: function() {
	    var data = function(iface, what) {
		var result = (kitero.stats.get(iface) || {})[what] || [];
		result = _.clone(result);
		result.reverse();
		result = _.zip(_.range(result.length), result);
		return _.reject(result, function(val) { _.isNull(val[1]) });
	    }
	    var tickBytes = function(val, axis) {
		if (Math.abs(val) > 1000000)
                    return (val / 1000000).toFixed(axis.tickDecimals) + "mB/s";
		else if (Math.abs(val) > 1000)
                    return (val / 1000).toFixed(axis.tickDecimals) + "kB/s";
		else
                    return val.toFixed(axis.tickDecimals) + "B/s";
            }
	    $.plot(this.el, [
		{ data: data(this.model.id, "up"),
		  color: "red",
		  label: "Upload" },
		{ data: data(this.model.id, "down"),
		  color: "blue",
		  label: "Download" }
	    ], { series: {shadowSize: 0 },
		 legent: {position: "nw" },
                 xaxis: { show: false, min: 0, max: kitero.stats.keep },
                 yaxis: { tickFormatter: tickBytes }});
	}
    });

    // Current settings header
    kitero.view.Settings = Backbone.View.extend({
	el: $("#kitero-header"),
	initialize: function() {
	    _.bindAll(this, 'render');
	    // Render should be triggered when settings are changed or
	    // when new interfaces are received.
	    kitero.settings.bind("change", this.render);
	},
	render: function() {
	    // Setup template variables
	    var display = {};
	    display['IP'] = kitero.settings.get("ip") || 'Unknown';
	    var interface = this.model.interface();
	    display['interface'] = interface && interface.get("name") || 'None';
	    var qos = this.model.qos();
	    display['qos'] = qos && qos.get("name") || 'None';
	    // Did we already set the banner?
	    var old = this.$("#kitero-settings");
	    if (!old.length) {
		// Apply the template
		kitero.console.debug("Render settings banner")
		this.el.children(":not(script)").remove();
		this.$("#kitero-header-template").tmpl(display).appendTo(this.el);
	    } else {
		// Reuse the current template
		_.each(display, function(value, key) {
		    var el = old.children("#kitero-settings-" + key);
		    if (value !== el.text()) {
			el.text(value).effect('pulsate', {times: 3}, 500);
		    }
		}, this);
	    }
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
	    _.bindAll(this, "update_selected");
	    this.model.bind("change:selected", this.update_selected);
	},
	// User selects this QoS
	select: function() {
	    var target = { s_interface: this.model.get("interface"),
			   s_qos: this.model.id };
	    kitero.console.debug("Select interface %s and QoS %s",
				 target.s_interface, target.s_qos);
	    kitero.settings.set(target);
	    kitero.settings.trigger("change:selected");
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
	    _.bindAll(this, "resize", "updatecounts");
	    kitero.stats.bind("change", this.updatecounts);
	},
	updatecounts: function() {
	    // Update counts for all interfaces
	    this.model.each(function (interface) {
		var iface = kitero.stats.get(interface.id) || {};
		var clients = (iface.clients || [0])[0];
		var id = interface.id.replace(".", "-"); // VLAN ID
		var span = this.$("#kitero-conn-id-" + id + " .kitero-conn-count");
		if (clients === 0) {
		    span.text("");;
		} else {
		    if (clients > 1) span.text(clients + " clients")
		    else span.text(clients + " client");
		}
	    }, this);
	},
	resize: function() {
	    // Resize the connections list such that the app is full screen.
	    var appheight = $("#kitero-header").outerHeight() +
		$("#kitero-footer").outerHeight() +
		$("#kitero-main").outerHeight() - this.el.height();
	    this.el.css("min-height", $("body").height() - appheight);
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
		var values = interface.toJSON();
		values.id = values.id.replace(".", "-");
		var html = $("#kitero-conn-template").tmpl(values);
		if (!interface.get("qos")) {
		    kitero.console.warning("No QoS for this interface:", interface);
		    return;
		}
		interface.get("qos").each(function(qq, q) {
		    var qos = new kitero.view.QoS({model: qq});
		    html.find(".kitero-qos").append(qos.render().el);
		});
		html.find(".kitero-conn-stats").bind("click", function(event) {
		    var n = new kitero.view.Stats({model: interface});
		    n.render();
		    event.stopPropagation();
		})
		html.appendTo(this.el);
	    }, this);
	    var that = this;
	    this.el.accordion( { autoHeight: false,
				 collapsible: true,
				 fillSpace: false,
				 clearStyle: true,
				 icons: {
				     header: 'ui-icon-circle-triangle-e',
				     headerSelected: 'ui-icon-circle-triangle-s'},
                                 header: 'div.kitero-conn',
                                 active: false});
	    // Handle element size
	    this.resize();
	    $(window).resize(this.resize);
	    return this;
	}
    });

    // Our main application
    kitero.view.Application = Backbone.View.extend({
	initialize: function() {
	    kitero.console.info("Starting Kitérő.")
	    _.bindAll(this, 'render', 'apply_changes');
	    // Initialize models
	    this.settings = kitero.settings = new kitero.model.Settings;
	    this.interfaces = new kitero.collection.Interfaces;
	    this.stats = kitero.stats = new kitero.model.Stats;
	    this.settings.bind("change", this.render);
	    this.interfaces.bind("reset", this.render);
	    // Fetch settings and interfaces from the web service
	    this.unavailable = _.once(this.unavailable);
	    this.settings.fetch({ error: this.unavailable, cache: false });
	    this.interfaces.fetch({ error: this.unavailable, cache: false });
	},
	// Display a dialog stating the unavailibility of the web service
	unavailable: function(what, error) {
	    var dialog = $("#kitero-unavailable")
		.tmpl({error: (error && (error.status + " " + error.statusText)) || "unknown error"})
		.dialog({ modal: true,
			  buttons: { "Reload": function() {window.location.reload();} },
			  close: function() {window.location.reload();},
			  title: "Kitérő web service unexpected situation",
			  dialogClass: "alert"
			});
	},
	// Apply changes
	apply_changes: function(event, password) {
	    var that = this;
	    var options = { error: function(what, error) {
		if (error && error.status === 401) {
		    var dialog = $("#kitero-password-dialog").tmpl({});
		    dialog.find("form").submit(function(event) {
			event.preventDefault();
			return false;
		    });
		    dialog.dialog({ modal: true,
				    title: "Password needed",
				    buttons: {
					Cancel: function() {
					    // Just close, no change
					    $(this).dialog("close");
					},
					OK: function() {
					    // Resubmit with the appropriate credentials
					    $(this).dialog("close");
					    that.apply_changes(event, $(this).find("input").val());
					}
				    }});
		} else that.unavailable(what, error);
	    }};
	    if (password !== undefined)
		options.beforeSend = function(req) {
		    req.setRequestHeader('Authorization',
					 "Basic " + base64_encode(password + ":" + password));
		};
	    kitero.settings.save(null, options);
	},
	// Reset changes, not used
	reset_changes: function(event) {
	    kitero.settings.reset();
	},
	render: function() {
	    // We render only if we have both appropriate settings and
	    // some interfaces to display. Otherwise, we stay in
	    // loading state.
	    if (this.settings.get("ip") && this.interfaces.length !== 0) {
		kitero.console.debug("Display interface.")
		// Initialize views. The associated model is a collection
		// of interfaces because we already have access to the
		// current settings through `kitero.settings`.
		this.settingsView = new kitero.view.Settings({model: this.interfaces});
		this.interfacesView = new kitero.view.Interfaces({model: this.interfaces});
		$("html").removeClass("loading");
		this.settingsView.render();
		this.interfacesView.render();
		// No need to redisplay the interface once it is displayed
		this.settings.unbind("change", this.render);
		this.interfaces.unbind("reset", this.render);
		this.settings.bind("change:selected", this.apply_changes);
		// Schedule periodic refresh
		this.scheduled = {};
		this.scheduled.settings = window.setInterval(function() {
		    kitero.settings.fetch({
			error: function(what, error) {
			    var that = kitero.app;
			    that.unavailable(what, error);
			    window.clearInterval(that.scheduled.settings);
			},
			cache: false
		    });
		}, 30100);
		this.scheduled.stats = window.setInterval(function() {
		    kitero.stats.fetch({
			success: function() {
			    // Trigger event from here since change
			    // does not seem to catch deep changes.
			    kitero.stats.trigger("poll");
			},
			error: function() {
			    // Do nothing
			    kitero.console.debug("unable to grab stats");
			},
			cache: false
		    });
		}, 5000);
	    }
	    return this;
	}
    });

    // Instantiate Kitérő.
    kitero.app = new kitero.view.Application({el: $("#kitero-interface")});
});
