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
            case 'git_info':
                console.log(type);
                $('#' + project + '-details .git-info ul').html('');
                var ul = $('#' + project + '-details .git-info ul');
                var info = data.git_info;
                ul.append($('<li>Revision: <a href="'+data.repo_url+'/commit/'+info.revision+'">'+info.revision+'</a></li>'));
                ul.append($('<li>Author: <strong>'+info.author+'</strong></li>'));
                ul.append($('<li>Date: '+info.date+'</li>'));
                ul.append($('<li>Comment: <em>'+info.comment+'</em></li>'));
                $('.run').prop('disabled', false);
                return;
        }
    }
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
