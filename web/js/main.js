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
        switch (type) {
            case 'git':
                $('#events').html('');
                li.html('New commit in repo: <strong>' + data.repository.name +
                    '</strong> by ' + data.user_name +
                    '<br> comment: "' + data.commits[0].message + '"');
                break;
            case 'before_pull':
                li.html('Start pulling...' + '<img class="loader" src="static/loader.gif">');
                break;
            case 'pulled':
                $('.loader').replaceWith($('<i class="glyphicon glyphicon-ok"></i>'));
                li.html('Repo was successfully updated.');
                break;
            case 'before_build':
                li.html('Start building...' + '<img class="loader" src="static/loader.gif">');
                break;
            case 'built':
                li.addClass(status);
                li.html('Build result: <span class="status">' + status + '</span>');
                if(status === 'success'){
                    $('.loader').replaceWith($('<i class="glyphicon glyphicon-ok"></i>'));
                }else{
                    $('.loader').replaceWith($('<i class="glyphicon glyphicon-remove"></i>'));
                }
                break;
            case 'before_test':
                li.html('Start testing...' + '<img class="loader" src="static/loader.gif">');
                break;
            case 'tested':
                li.addClass(status);
                li.html('Tests result: <span class="status">' + status + '</span>');
                if(status === 'success'){
                    $('.loader').replaceWith($('<i class="glyphicon glyphicon-ok"></i>'));
                }else{
                    $('.loader').replaceWith($('<i class="glyphicon glyphicon-remove"></i>'));
                }
                break;
            case 'info':
                li.html(data.message);
                break;
            case 'error':
                li.addClass(status);
                li.html(data.message);
                break;
            default:

        }
        $('#events').append(li);
    };

    $('.run').on('click', function(e){
        e.preventDefault();
        $('#events').html('');
        $.get('run/' + $(this).attr('data-project'));
    });
});
