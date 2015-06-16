$(document).ready(function() {

    var ws = new WebSocket('ws://lets.developonbox.ru/mycroft/ws');
    ws.onopen = function() {
        console.log('WebSocket open');
        $.each($('.run'), function(i, el){
            ws.send('info:' + $(el).attr('data-project'));
        })
    };
    ws.onmessage = function(event) {
        event = JSON.parse(event.data);
        var type = event.type;
        var data = event.data;
        var status = event.status;
        var li = $('<li></li>');
        $('.run').prop('disabled', true);
        var project = data.name;
        switch (type) {
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
                break;
            case 'git':
                project = data.repository.name
                li.html('New commit in repo: <strong>' + project +
                    '</strong> by ' + data.user_name + ' at ' + data.start_at +
                    '<br> comment: "' + data.commits[0].message + '"');
                break;
            case 'run':
                project = data.name
                li.html('Started project: <strong>' + project +
                    '</strong> at ' + data.start_at);
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
                li.html('<strong>Done at '+event.finish_at+'.</strong> <a href="' + event.logfile + '">Report</a>');
                if(event.artefact){
                    li.append(' &amp; <a href="' + event.artefact + '">Artefact</a>');
                }
                $('.run').prop('disabled', false);
                break;
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
        $('.clone').remove();

        $('#project-modal').modal();
    });

    $('.edit').on('click', function(e){
        e.preventDefault();
        $('.clone').remove();

        $('#project-modal').modal();
    });

    $('#add_step').on('click', function(e){
        e.preventDefault();

        $('.buildstep:first-child').clone().addClass('clone').appendTo('#steps');
    });
});
