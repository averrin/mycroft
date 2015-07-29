
$(document).ready(function() {
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
            release_action: $('#release_action').val(),
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
        ws.onmessage = function(event){
          event = JSON.parse(event.data);
          var type = event.type;
          if(type === 'action' && event.status === 'success'){
              window.location = '/mycroft';
          }

        }
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
        bsHandlers();
});
