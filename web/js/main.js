$(document).ready(function() {

    var ws = new WebSocket('ws://lets.developonbox.ru/mycroft/ws');
    ws.onopen = function() {
        console.log('WebSocket open');
        ws.onmessage = onmessage;
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
    var onmessage = function(event) {
        event = JSON.parse(event.data);
        var type = event.type;
        var data = event.data;
        var status = event.status;
        var li = $('<li></li>');
        $('.run').prop('disabled', true);
        var project = data.name;
        switch (type) {
            case 'full_info':
                $('.run').prop('disabled', false);
                $('#name').val(data.full_name);
                $('#repo').val(data.url);
                $('#url').val(data.web_url);
                $('#branch').val(data.branch);
                $('#watchers').val(data.watchers.join(', '));
                $('#fail_watchers').val(data.fail_watchers.join(', '));
                $('#deps').val(data.deps.join(', '));

                data.build_steps.forEach(function(step, i){
                    var step_form = $('#steps .buildstep:nth-child(' + (i + 1) + ')');
                    if(step_form.length === 0){
                        step_form = $('.buildstep:first-child').clone();
                        step_form.prepend('<hr>').addClass('clone').appendTo('#steps');
                        step_form.find('#bs_stop').prop('checked', false);
                        step_form.find('#bs_disable').prop('checked', false);
                    }
                    step_form.find('#bs_name').val(step.name);
                    step_form.find('#bs_desc').val(step.description);
                    step_form.find('#bs_cmd').val(step.cmd);
                    if(step.stop_on_fail){
                        step_form.find('#bs_stop').prop('checked', step.stop_on_fail);
                    }
                    if(step.disabled){
                        step_form.find('#bs_disable').prop('checked', step.disabled);
                    }
                });
                bsHandlers();
                return;
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
        $('#project-modal input[type="text"]').val('');
        $('#project-modal input[type="checkbox"]').prop('checked', false);

        $('#branch').val('master');
        $('#watchers').val('js-builds@maillist.dev.zodiac.tv');

        bsHandlers();

        $('#project-modal').modal();
    });

    $('.edit').on('click', function(e){
        e.preventDefault();
        $('.clone').remove();
        $('#project-modal input[type="text"]').val('');
        $('#project-modal input[type="checkbox"]').prop('checked', false);
        ws.send('fullinfo:' + $(e.currentTarget).attr('data-project'));

        $('#project-modal').modal();
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

    $('#save').on('click', function(e){
        e.preventDefault();

        var repo = $('#repo').val();
        var project = {
            full_name: $('#name').val(),
            name: repo.split('/')[repo.split('/').length-1].slice(0,-4),
            url: repo,
            web_url: $('#url').val(),
            branch: $('#branch').val(),
            watchers: $('#watchers').val().replace(' ', '').split(','),
            fail_watchers: $('#fail_watchers').val().replace(' ', '').split(','),
            deps: $('#deps').val().replace(' ', '').split(','),
            build_steps: []
        };

        $('.buildstep').each(function(i, step_form){
            step_form = $(step_form);
            var step = {
                name: step_form.find('#bs_name').val(),
                description: step_form.find('#bs_desc').val(),
                cmd: step_form.find('#bs_cmd').val(),
                stop_on_fail: step_form.find('#bs_stop').prop('checked'),
                disabled: step_form.find('#bs_disable').prop('checked'),
            };
            project.build_steps.push(step);
        });

        ws.send('save:' + JSON.stringify(project));
    });

    $('#add_step').on('click', function(e){
        e.preventDefault();

        $('.buildstep:first-child').clone().prepend('<hr>').addClass('clone').appendTo('#steps');
        bsHandlers();
    });

    function bsHandlers(){
        $('.bs_delete').on('click', function(e){
            e.preventDefault();
            if($('.buildstep').length < 2){
                return;
            }

            $(e.currentTarget).parent().parent().parent().remove();
            if($('.buildstep').length === 1){
                $('.buildstep').removeClass('clone');
            }
        });
        $('.bs_down').on('click', function(e){
            e.preventDefault();

            var step = $(e.currentTarget).parent().parent().parent();
            step.next().after(step);
        });
        $('.bs_up').on('click', function(e){
            e.preventDefault();

            var step = $(e.currentTarget).parent().parent().parent();
            step.prev().before(step);
        });
    }
});
