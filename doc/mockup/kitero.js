/* Ugly mockup */

var kitero = function() {

    var kitero = {}

    var updateGraph = function() {
	var updata = [], downdata = [];

	var getRandom = function(data, nb, mult) {
	    data.push(Math.random() * 300000 * mult);
	    if (data.length > nb) {
		data = data.slice(data.length - nb);
	    }
	    var res = [];
	    for (var i = 0, max = data.length; i < max; ++i) {
		res.push([i, data[i]]);
	    }
            return res;
	};

	var tickBytes = function(val, axis) {
	    if (Math.abs(val) > 1000000)
		return (val / 1000000).toFixed(axis.tickDecimals) + " MB";
	    else if (Math.abs(val) > 1000)
		return (val / 1000).toFixed(axis.tickDecimals) + " kB";
	    else
		return val.toFixed(axis.tickDecimals) + " B";	    
	}

	var build = function() {
	    $.plot($(".ui-accordion-content-active .kitero-graph"), [
		{ data: getRandom(updata, 40, 1),
		  color: "red",
		  label: "up" },
		{ data: getRandom(downdata, 40, -1),
		  color: "blue",
		  label: "down" },
	    ], { series: { shadowSize: 0 },
		 legend: { position: "nw" },
		 xaxis: { show: false, min: 0, max: 40 },
		 yaxis: { tickFormatter: tickBytes}});
	    setTimeout(build, 3000);
	};

	return build;
    }();

    kitero.start = function () {
	$('#cancel').button({icons: {primary: 'ui-icon-circle-close'},
			     disabled: true})
	    .click(function(event) {
		// Not implemented
		event.preventDefault();
	    });
	$('#apply').button({icons: {primary: 'ui-icon-circle-check'},
			    disabled: true})
	    .click(function(event) {
		var qos = $('.kitero-qos-selected .kitero-qos-name').text();
		var connection = $('.kitero-qos-selected').closest('.kitero-conn-details').prev()
		    .find('.kitero-conn-title').first().text();
		
		$('#kitero-progressbar').show();
		$("#kitero-progressbar").progressbar({value: 10});
		$('#cancel').button("disable");
		$('#apply').button("disable");
		setTimeout(function() {
		    $("#kitero-progressbar").progressbar({value: 60});
		    setTimeout(function() {
			$("#kitero-progressbar").progressbar({value: 100});
			setTimeout(function() {
			    $('#kitero-progressbar').hide();
			    $('#kitero-current-connection').fadeOut().text(connection).fadeIn();
			    $('#kitero-current-qos').fadeOut().text(qos).fadeIn();
			}, 300);
		    }, 1000);
		}, 1000);
		event.preventDefault();
	    });

	$('.kitero-conns').accordion( { icons: {
	    header: 'ui-icon-circle-triangle-e',
	    headerSelected: 'ui-icon-circle-triangle-s'},
					header: 'div.kitero-conn',
					active: 1 });

	/* When selecting a QoS, apply selected to it */
	$('.kitero-qos').delegate('li', 'click', function() {
	    $('.kitero-qos li').each(function() {
		$(this).removeClass('kitero-qos-selected');
	    });
	    $(this).addClass('kitero-qos-selected');

	    /* Unhide cancel/apply buttons */
	    $('#apply').button("enable");
	    $('#cancel').button("enable");
	    $('#kitero-progressbar').hide();
	});

	setTimeout(updateGraph, 1000);
    };

    return kitero;
}();

$(document).ready(kitero.start);
