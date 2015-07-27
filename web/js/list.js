$(document).ready(function() {
    onmessage = function(event) {
        event = JSON.parse(event.data);
        var type = event.type;
        var data = event.data;
        var status = event.status;
        var li = $('<li></li>');
        $('.run').prop('disabled', true);
        var project = data.name;
        switch (type) {
            case 'log':
                $('#logs').removeClass('hide');
                $('.run').prop('disabled', false);
                console.log('%c%s [%c%s%c]: %s', 'color: #111', data.name, 'color: orange; font-weight: bold', data.step, 'color: #111; font-weight: normal', data.line);
                $('#log').prepend('[<span style="color:orange;font-weight: bold">' + data.step + '</span>]: ' + data.line + '<br>');
                // $('#log').append(data.name + '[' + data.step + ']: ' + data.line + '\n');
                return;
            case 'git_info':
                $('#' + project + '-events .git-info ul').html('');
                var ul = $('#' + project + '-events .git-info ul');
                var info = data.git_info;
                ul.append($('<li>Revision: <a href="'+data.repo_url+'/commit/'+info.revision+'">'+info.revision+'</a></li>'));
                ul.append($('<li>Author: <strong>'+info.author+'</strong></li>'));
                ul.append($('<li>Date: '+info.date+'</li>'));
                ul.append($('<li>Comment: <em>'+info.comment+'</em></li>'));
                $('.run').prop('disabled', false);
                return;
            case 'git':
                project = data.repository.name;
                li.html('New commit in repo: <strong>' + project +
                    '</strong> by ' + data.user_name + ' at ' + data.start_at +
                    '<br> comment: "' + data.commits[0].message + '"');
                $('#log').html('');
                break;
            case 'run':
                project = data.name;
                li.html('Started project: <strong>' + project +
                    '</strong> at ' + data.start_at);
                $('#log').html('');
                break;
            case 'info':
                li.html(data.message);
                break;
            case 'action':
                console.log(event.status);
                if(event.status == 'success'){
                    location.reload();
                }
                return;
            case 'error':
                li.addClass(status);
                li.html('<strong>' + data.message + '</strong>');
                break;
            case 'done':
                li.addClass(status);
                li.html('<strong>Done at '+event.finish_at+'.</strong> <a href="' + event.logfile + '">Report</a>');
                if(event.artefact){
                    li.append(' &amp; <a href="' + event.artefact + '">Artefact</a>');
                    }
                $('.run').prop('disabled', false);
                $('#log').prepend('[<span style="color:lightblue;font-weight: bold">' + data.name + '</span>]: <span style="color: lightgreen;font-weight: bold">Done</span><br>');
                break;
            case 'single_test':
                var e = $('#' + event.name + '-events li:last-child');
                if(e.has('ul').length === 0){
                    e.append('<ul></ul>');
                }
                var list = e.find('ul');
                if(data.status === 'ERRROR'){
                    list.append('<li class="ERROR">'+data.test+'</li>');
                }else{
                    list.append('<li>'+data.test+': <span class="' + data.status +'">'+data.status+'</span></li>');
                }
                return;
            default:
                if(type.indexOf('pre_') !== 0){
                    li.addClass(status);
                    if(status === 'success'){
                        $('#' + project + '-events .loader').replaceWith('<i class="glyphicon glyphicon-ok"></i>');
                    }else{
                        $('#' + project + '-events .loader').replaceWith('<i class="glyphicon glyphicon-remove"></i>');
                    }
                    li.html('Step done with status: <span class="status">' + status + '</span>');
                    if(event.logfile){
                        li.append($('<span> [<a href="' + event.logfile +'">log</a>]</span>'));
                    }
                }else{
                    li.html('<strong>' + event.description + '</strong>' + '<img class="loader" src="static/loader.gif">');
                }

        }
        $('#' + project + '-events .init').remove();
        $('#' + project + '-events .git-info').remove();
        $('#' + project + '-events').append(li);
    };

    ws.onmessage = onmessage;
    $('.run').on('click', function(e){
        e.preventDefault();
        $('#' + $(this).attr('data-project') + '-events').html('');
        $.get('run/' + $(this).attr('data-project'), function(data){
            console.log(data);
            if(data !== 'success'){
                alert('Build already started');
            }
        });
        $(this).prop('disabled', true);
    });

    $('#add').on('click', function(e){
        e.preventDefault();
        window.location = 'new';
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
});
