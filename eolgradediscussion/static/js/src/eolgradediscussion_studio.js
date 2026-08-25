/*
        .-"-.
       /|6 6|\
      {/(_0_)\}
       _/ ^ \_
      (/ /^\ \)-'
       ""' '""
*/


function EolGradeDiscussionXBlock(runtime, element, settings) {

    $(element).find('.save-button-eolgradediscussion').bind('click', function(eventObject) {
        eventObject.preventDefault();
        var handlerUrl = runtime.handlerUrl(element, 'studio_submit');
        if($(element).find('select[name="id_forum"]').val() != ''){
            select_id_forum = document.getElementById($(element).find('select[name="id_forum"]')[0].id)
            const index = select_id_forum.selectedIndex;
            const option = select_id_forum.options[index];
            var data = {
                'display_name': $(element).find('input[name=display_name]').val(),
                'id_forum': $(element).find('select[name="id_forum"]').val(),
                'forum_display_name': option.text,
                'puntajemax': $(element).find('input[name=puntajemax]').val(),
            };
            if ($.isFunction(runtime.notify)) {
                runtime.notify('save', {state: 'start'});
            }
            $.post(handlerUrl, JSON.stringify(data)).done(function(response) {
                if (response.result == 'success' && $.isFunction(runtime.notify)) {
                    runtime.notify('save', {state: 'end'});
                }
                else {
                    runtime.notify('error',  {
                        title: 'Error: Falló en Guardar',
                        message: 'Revise los campos si estan correctos.'
                    });
                }
            });
        }
        else {
            alert("El campo 'Id Foro' no puede ser vacio.");
            e.preventDefault();
            return;
        }
    });

    $(element).find('.cancel-button-eolgradediscussion').bind('click', function(eventObject) {
        eventObject.preventDefault();
        runtime.notify('cancel', {});
    });
    $(function($) {
        // Show loading and hide elements
        $(element).find('#eolgradediscussion_loading').show();
        $(element).find('.eolgradediscussion_studio').hide();
        $(element).find('.eolgradediscussion_error').hide();
        $(element).find('.eolgradediscussion_studio li.field').hide();
        $(element).find('.save-button').hide();
        get_ids_discussion()
        function get_ids_discussion() {
            /*
            * Get all ids discussion
            */
            url_get_discussions = settings.url_get_discussions;
            $.ajax({
                url: url_get_discussions,
                dataType: 'json',
                cache: false,
                contentType: "application/json",
                processData: false,
                type: "GET",
                xhrFields: {
                    withCredentials: true
                },
                //headers: { "x-requested-with": "XMLHttpRequest" },
                crossDomain: true,
                success: function(response){
                    var aux_html = '';
                    var html_id_forum = $(element).find('select[name="id_forum"]')[0];
                    var lista_discussion = response['courseware_topics'].concat(response['non_courseware_topics']);
                    for (var i = 0; i<lista_discussion.length; i++){
                        if(lista_discussion[i]['id'] == null){
                            aux_html = aux_html + "<optgroup label='"+ lista_discussion[i]['name'] +"'>";
                            for (var j = 0; j<lista_discussion[i]['children'].length; j++){
                                if(settings.id_forum == lista_discussion[i]['children'][j]['id']){
                                    aux_html = aux_html + "<option selected value='" + lista_discussion[i]['children'][j]['id'] + "'> " + lista_discussion[i]['children'][j]['name'] + "</option>";
                                }
                                else{
                                    aux_html = aux_html + "<option value='" + lista_discussion[i]['children'][j]['id'] + "'> " + lista_discussion[i]['children'][j]['name'] + "</option>";
                                }
                            }
                            aux_html = aux_html + "</optgroup>";
                        }
                        else{
                            if(settings.id_forum == lista_discussion[i]['id']){
                                aux_html = aux_html + "<option selected value='" + lista_discussion[i]['id'] + "'> " + lista_discussion[i]['name'] + "</option>";
                            }
                            else{
                                aux_html = aux_html + "<option value='" + lista_discussion[i]['id'] + "'> " + lista_discussion[i]['name'] + "</option>";
                            }
                        }
                    }
                    html_id_forum.innerHTML = aux_html
                    $(element).find('#eolgradediscussion_loading').hide();
                    $(element).find('.eolgradediscussion_studio').show();
                    $(element).find('.eolgradediscussion_studio li.field').show();
                    $(element).find('.save-button').show();
                },
                error: function() {
                    $(element).find('#eolgradediscussion_loading').hide();
                    $(element).find('.eolgradediscussion_error').show();
                    runtime.notify('error',  {
                        title: 'Error: Falló en obtener los datos.',
                        message: 'No se pudo obterner los datos de los foros del curso, actualice la pagina e intente nuevamente, si el problema persiste contactese con mesa de ayuda.'
                    });
                }
            });
        }
    });
}