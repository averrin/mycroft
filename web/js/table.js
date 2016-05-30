function markRunning(project){
    $('.run').prop('disabled', true);
    var tr = $('.project[data-project="'+project+'"]');
    tr.addClass('running');
    tr.find('td:nth-child(2)').html('<b>Running...</b><img class="loader" src="/mycroft/static/loader.gif">');
}
function showGitInfo(project, data){
    var ul = $('.details[data-project="'+project+'"] .git-info ul');
    ul.html('');
    var info = data.git_info;
    ul.append($('<li>Revision: <a href="'+data.repo_url+'/commit/'+info.revision+'">'+info.revision+'</a></li>'));
    ul.append($('<li>Branch: <strong>'+info.branch+'</strong></li>'));
    ul.append($('<li>Author: <strong>'+info.author+'</strong></li>'));
    ul.append($('<li>Date: '+info.date+'</li>'));
    ul.append($('<li>Comment: <em>'+info.comment+'</em></li>'));
    $('.run').prop('disabled', false);
}
function markDone(project, event){
    var tr = $('.project[data-project="'+project+'"]');
    tr.removeClass('running');
    var report = '<b><a href="' + event.logfile + '">' + event.run_id + '<b> [<small>' + event.finish_at + '</small>]: <span class="' + event.status + '">' + event.status + '</span></a>';
    if(event.artefact){
      report += '<br>';
      report += '<a href="' + event.artefact + '">Artefact</a>';
        if(event.ftp_artefact){
          report += '&nbsp;&amp;&nbsp;<a href="' + event.ftp_artefact + '">FTP Artefactory</a>';
        }
    }
    tr.find('td:nth-child(2)').html(report);
    $('.run').prop('disabled', false);
    ws.send('info:' + project);
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
        var tr;

        switch (type) {
            case 'git_info':
                showGitInfo(project, data);
                return;
            case 'done':
                markDone(project, event);
                break;
            case 'log':
                printLog(data);
                markRunning(project)
                break;
            case 'action':
                console.log(event.status);
                if(event.status == 'success'){
                    location.reload();
                }
                return
            default:
                markRunning(project)
                break;
        }
    }
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
    $('.parametric_run').on('click', function(e){
        e.preventDefault();
        $('#parametric_run').attr('data-project', $(this).attr('data-project'));
        $('#params-modal').modal();
    });
    $('#parametric_run').on('click', function(e){
        e.preventDefault();
        $('.events[pata-project="'+$(this).attr('data-project')+'"]').html('');
        $.get('/mycroft/run/' + $(this).attr('data-project') +'?' + $('#params-modal form').serialize(), function(data){
            console.log(data);
            if(data !== 'success'){
                alert('Build already started');
            }
        });
        $('#params-modal').modal('hide');
    });
    setProjectHandlers();
});
