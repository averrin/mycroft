$(document).ready(function() {

    var ws = new WebSocket('ws://lets.developonbox.ru/mycroft/ws');
    ws.onopen = function() {
        console.log('WebSocket open');
    };
    ws.onmessage = function(event) {
        event = JSON.parse(event.data);
        var type = event.type;
        var data = event.data;
        var status = event.status;
        var li = $('<li></li>');
        $('.run').prop('disabled', true );
        switch (type) {
            case 'git':
                $('#events').html('');
                li.html('New commit in repo: <strong>' + data.repository.name +
                    '</strong> by ' + data.user_name +
                    '<br> comment: "' + data.commits[0].message + '"');
                break;
            case 'info':
                li.html(data.message);
                break;
            case 'error':
                li.addClass(status);
                li.html('<strong>' + data.message + '</strong>');
                break;
            case 'done':
                li.addClass(status);
                li.html('<strong>Done.</strong> Report: <a href="' + event.logfile + '">HTML</a>');
                $('.run').prop('disabled', false );
                break;
            default:
                if(type.indexOf('pre_') !== 0){
                    li.addClass(status);
                    if(status === 'success'){
                        $('.loader').replaceWith('<i class="glyphicon glyphicon-ok"></i>');
                    }else{
                        $('.loader').replaceWith('<i class="glyphicon glyphicon-remove"></i>');
                    }
                    li.html('Step done with status: <span class="status">' + status + '</span>');
                    if(event.logfile){
                        li.append($('<span> [<a href="' + event.logfile +'">log</a>]</span>'));
                    }
                }else{
                    li.html('<strong>' + event.description + '</strong>' + '<img class="loader" src="static/loader.gif">');
                }

        }
        $('#events').append(li);
    };

    $('.run').on('click', function(e){
        e.preventDefault();
        $('#events').html('');
        $.get('run/' + $(this).attr('data-project'), function(data){
            console.log(data);
            if(data !== 'success'){
                alert('Build already started');
            }
        });
        $('.run').prop('disabled', true );
    });
});
