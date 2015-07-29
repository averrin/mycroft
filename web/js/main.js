var ws;
var onmessage;

function printLog(data){
  console.log('%c%s [%c%s%c]: %s', 'color: #111', data.name, 'color: orange; font-weight: bold', data.step, 'color: #111; font-weight: normal', data.line);
}

function setProjectHandlers(){
    $('#add').on('click', function(e){
        e.preventDefault();
        window.location = '/mycroft/new';
    });

    $('#delete').on('click', function(e){
        e.preventDefault();
        ws.send('delete:' + $(e.currentTarget).attr('data-project'));
    });
    $('.delete').on('click', function(e){
        e.preventDefault();
        $('#delete-modal').modal();
        var name = $(e.currentTarget).attr('data-project');
        $('#modal-name').html(name);
        $('#delete').attr('data-project', name);
    });

    $('.release').on('click', function(e){
        e.preventDefault();
        ws.send('release:' + $(e.currentTarget).attr('data-project'));
    });

}

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
