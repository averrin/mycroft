var ws;
var onmessage;
$(document).ready(function() {
    ws = new WebSocket('ws://lets.developonbox.ru/mycroft/ws');
    ws.onopen = function() {
        console.log('WebSocket open');
        ws.onclose = onclose;
        $.each($('.run'), function(i, el){
            ws.send('info:' + $(el).attr('data-project'));
        });
    };
    var onclose = function(){
        console.log('ws closed');
        ws = new WebSocket('ws://lets.developonbox.ru/mycroft/ws');
        ws.onmessage = onmessage;
        ws.onclose = onclose;
        console.log('ws reopened');
    };

});
