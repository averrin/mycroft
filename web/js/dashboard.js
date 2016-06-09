function showLog(data){
    if(data.name != $($('.project-panel')[0]).attr('data-name')) {
      return;
    }
    $('#logs').removeClass('hide');
    $('.run').prop('disabled', false);
    printLog(data);
    $('#log').prepend('[<span style="color:orange;font-weight: bold">' + data.step + '</span>]: ' + data.line + '<br>');
    // $('#log').append(data.name + '[' + data.step + ']: ' + data.line + '\n');
}

function showGitInfo(project, data){
    var ul = $('.events[data-project="'+project+'"] .git-info ul');
    ul.html('');
    var info = data.git_info;
    ul.append($('<li>Revision: <a href="'+data.repo_url+'/commit/'+info.revision+'">'+info.revision+'</a></li>'));
    ul.append($('<li>Branch: <strong>'+info.branch+'</strong></li>'));
    ul.append($('<li>Author: <strong>'+info.author+'</strong></li>'));
    ul.append($('<li>Date: '+info.date+'</li>'));
    ul.append($('<li>Comment: <em>'+info.comment+'</em></li>'));
    $('.run').prop('disabled', false);
}
function startedByHook(project, data, li){
    li.html('New commit in repo: <strong>' + project +
        '</strong> by ' + data.user_name + ' at ' + data.start_at +
        '<br> comment: "' + data.commits[0].message + '"');
    $('#log').html('');
}
function started(project, data, li){
    li.html('Started project: <strong>' + project +
        '</strong> at ' + data.start_at);
    $('#log').html('');
}
function markDone(project, data, li, event){
    li.addClass(status);
    li.html('<strong>Done at '+event.finish_at+'.</strong> <a href="' + event.logfile + '">Report</a>');
    if(event.artefact){
        li.append(' &amp; <a href="' + event.artefact + '">Artefact</a>');
        if(event.ftp_artefact){
          li.append(' &amp; <a href="' + event.ftp_artefact + '">FTP Artefactory</a>');
        }
    }
    $('.run').prop('disabled', false);
    $('#log').prepend('[<span style="color:lightblue;font-weight: bold">' + data.name + '</span>]: <span style="color: lightgreen;font-weight: bold">Done</span><br>');
}
function singleTest(project, data, event){
    var e = $('.events[data-project="'+event.id+'"] li:last-child');
    if(e.has('ul').length === 0){
        e.append('<ul></ul>');
    }
    var list = e.find('ul');
    if(data.status === 'ERROR'){
        list.append('<li class="ERROR">'+data.test+'</li>');
    }else{
        list.append('<li>'+data.test+': <span class="' + data.status +'">'+data.status+'</span></li>');
    }
}

$(document).ready(function() {
    onmessage = function(event) {
        event = JSON.parse(event.data);
        var type = event.type;
        var data = event.data;
        var status = event.status;
        var li = $('<li></li>');
        $('.run').prop('disabled', true);
        var project = data.id;
        switch (type) {
            case 'log':
                showLog(data);
                return;
            case 'git_info':
                showGitInfo(project, data);
                return;
            case 'git':
                project = data.repository.name;
                startedByHook(project, data, li);
                break;
            case 'run':
                project = data.name;
                started(project, data, li);
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
                markDone(project, data, li, event);
                break;
            case 'single_test':
                singleTest(project, data, event);
                return;
            default:
                if(type.indexOf('pre_') !== 0){
                    li.addClass(status);
                    if(status === 'success'){
                        $('.events[data-project="'+project+'"] .loader').replaceWith('<i class="glyphicon glyphicon-ok"></i>');
                    }else{
                        $('.events[data-project="'+project+'"] .loader').replaceWith('<i class="glyphicon glyphicon-remove"></i>');
                    }
                    li.html('Step done with status: <span class="status">' + status + '</span>');
                    if(event.logfile){
                        li.append($('<span> [<a href="' + event.logfile +'">log</a>]</span>'));
                    }
                }else{
                    li.html('<strong>' + event.description + '</strong>' + '<img class="loader" src="/mycroft/static/loader.gif">');
                }

        }
        $('.events[data-project="'+project+'"] .init').remove();
        $('.events[data-project="'+project+'"] .git-info').remove();
        $('.events[data-project="'+project+'"]').append(li);
    };

    ws.onmessage = onmessage;
    $('.run').on('click', function(e){
        e.preventDefault();
        $('.events[pata-project="'+$(this).attr('data-project')+'"]').html('');
        $.get('/mycroft/run/' + $(this).attr('data-project'), function(data){
            console.log(data);
            if(data !== 'success'){
                alert('Build already started');
            }
        });
        $(this).prop('disabled', true);
    });
    setProjectHandlers()
});
