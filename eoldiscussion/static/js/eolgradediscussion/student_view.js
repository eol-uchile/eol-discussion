/*
        .-"-.
       /|6 6|\
      {/(_0_)\}
       _/ ^ \_
      (/ /^\ \)-'
       ""' '""
*/

function EolGradeDiscussionXBlock(runtime, element, settings) {
    var $ = window.jQuery;
    var $element = $(element);
    var url_get_student_module = runtime.handlerUrl(element, 'get_data_forum');
    var handlerUrlSaveStudentAnswersAll = runtime.handlerUrl(element, 'savestudentanswersall');

    function showAnswers(result){
        /*
            check if response dont have error
        */
        $(element).find('#ui-loading-forum-grade-load-footer').hide()
        if (result.result == 'success'){
            $element.find('#eolgradediscussion_label')[0].textContent = "Guardado Correctamente";
            $element.find('#eolgradediscussion_label')[0].style.display = "block";
            $element.find('#eolgradediscussion_wrong_label')[0].textContent = "";
            $element.find('#eolgradediscussion_wrong_label')[0].style.display = "none";
            $element.find("#calificado")[0].textContent = parseInt($element.find("#calificado")[0].textContent) + result.calificado;
            $(element).find('#save-button-forum-grade')[0].disabled = false
        }
        if (result.result == 'error'){
            $element.find('#eolgradediscussion_label')[0].textContent = "";
            $element.find('#eolgradediscussion_label')[0].style.display = "none";
            $element.find('#eolgradediscussion_wrong_label')[0].textContent = "Error de datos o rol de usuario";
            $element.find('#eolgradediscussion_wrong_label')[0].style.display = "block";
        }
    }
    function errorMesagges(response){
        $element.find('#eolgradediscussion_label')[0].textContent = "";
        $element.find('#eolgradediscussion_label')[0].style.display = "none";
        $element.find('#eolgradediscussion_wrong_label')[0].textContent = "Error de datos o rol de usuario";
        $element.find('#eolgradediscussion_wrong_label')[0].style.display = "block";
        $(element).find('#ui-loading-forum-grade-load-footer').hide();
    }
    function create_modal_content(lista_alumnos, content_forum){
        /*  
            Create modal content
        
        lista_alumno = [{'id': a['id'],
        'username': a['username'],
        'correo': a['email'],
        'student_forum': student_forum}...]
        student_forum = { 
            user id { 
                hilo id {
                    comment id : [] 
                    }
                }
            }
        */ 
        modal_content = $(element).find('#forum-grade-container');
        var html_content = "";
        html_content = '<ol aria-labelledby="expand-collapse-outline-all-button">'
        for (var i = 0; i < lista_alumnos.length; i++) {
            var comment_data = lista_alumnos[i]
            html_content = html_content + create_accordion_user(comment_data, content_forum)
        }
        html_content = html_content + '</ol>'
        modal_content.html(html_content)
    }
    $(element).find('#save-button-forum-grade').live('click', function(e) {
        /*
            Save user's score and feedback
        */
        e.currentTarget.disabled = true;
        $(element).find('#ui-loading-forum-grade-load-footer').show();
        var tabla =  $(element).find('#forum-grade-container')[0];
        var puntajes = tabla.getElementsByTagName('input');
        var check = true;
        var data =  new Array();
        for(i=0;i<puntajes.length;i++){
            var punt = puntajes[i].value.trim();
            var user_id = puntajes[i].getAttribute('aria-controls');
            var pmax = settings.puntajemax;
            var feedback = puntajes[i].parentElement.parentElement.children[1].children[0].value
            if (punt != "" && (punt.includes(".") || parseInt(punt, 10) > parseInt(pmax, 10) || parseInt(punt, 10) < 0)){
                check = false;
                break;
            }
            else{
                var aux = {
                    'user_id':user_id,
                    'score': punt,
                    'feedback': feedback
                }
                data.push(aux)
            }
        }
        if (check){
            $.ajax({
                type: "POST",
                url: handlerUrlSaveStudentAnswersAll,
                data: JSON.stringify({"data": data}),
                success: showAnswers,
                error: errorMesagges
            });
        }
        else{
            $element.find('#eolgradediscussion_wrong_label')[0].textContent = "Revise los campos si estan correctos";
            $element.find('#eolgradediscussion_label')[0].textContent = "";
            $(element).find('#ui-loading-forum-grade-load-footer').hide();
            $element.find('#eolgradediscussion_wrong_label')[0].style.display = "block";
            e.currentTarget.disabled = false;
        }
    });
    $(element).find('#checkbox_users').live('change', function(e) {
        if (e.target.checked) {
            $(element).find('.class_empty_main_user').hide()
        }
        else {
            $(element).find('.class_empty_main_user').show()
        }
    });

    function findPos(obj) {
        /*
            find position of modal
        */
        var curtop = 0;
        if (obj.offsetParent) {
            do {
                curtop += obj.offsetTop;
            } while (obj = obj.offsetParent);
        return [curtop];
        }
    }

    $(element).find('input[name=forum-grade-button]').live('click', function(e) {
        /* 
            Get forum data
        */
        e.currentTarget.disabled = true;
        $element.find('#eolgradediscussion_label')[0].textContent = "";
        $element.find('#eolgradediscussion_label')[0].style.display = "none";
        $element.find('#eolgradediscussion_wrong_label')[0].textContent = "";
        $element.find('#eolgradediscussion_wrong_label')[0].style.display = "none";
        $(element).find('#ui-loading-forum-grade-load').show()
        var id_modal = $(this)[0].getAttribute('aria-controls')
        var forum_modal =  document.getElementById(id_modal)
        
        $.post(url_get_student_module, JSON.stringify({})).done(function(response) {
            //{'result': 'success', 'lista_alumnos': lista_alumnos, 'content_forum': content_forum}
            if (response.result == 'success' ){
                titulo = $(element).find('#forum-grade-body')
                titulo.html('Puntaje máximo: ' + settings.puntajemax);
                create_modal_content(response.lista_alumnos, response.content_forum);
                $(element).find('#save-button-forum-grade')[0].disabled = false
            }
            else {
                titulo = $(element).find('#forum-grade-body')
                if (response.result == 'user is not course staff' ){
                    titulo.html('Usuario no tiene permisos para obtener los datos.');
                }
                else {
                    if (response.result == 'no data' ){
                        titulo.html('Foro sin datos.');
                    }
                    else {
                        if (response.result == 'no id_forum' ){
                            titulo.html('Componente no configurado.');
                        }
                        else {
                            titulo.html('Se ha producido un error en obtener los datos.');
                        }
                    }
                }
            }
            $(element).find('#ui-loading-forum-grade-load').hide();
            forum_modal.style.display = "block";
            window.scroll(0,findPos(document.getElementById(id_modal)) - 450);
            e.currentTarget.disabled = false;
        }).fail(function() {
            titulo = $(element).find('#forum-grade-body')
            titulo.html('Se ha producido un error en obtener los datos');
            $(element).find('#ui-loading-forum-grade-load').hide();
            forum_modal.style.display = "block";
            window.scroll(0,findPos(document.getElementById(id_modal)) - 450);
            e.currentTarget.disabled = false;
        });
    });

    function create_accordion_user(data, content_forum){
        /*data = {'id': a['id'],
        'username': a['username'],
        'correo': a['email'],
        'score': puntaje,
        'student_forum': student_forum}*/
        /*
        content_forum= {
                'thread_id': comment['thread_id'],
                'username': comment['username'],
                'body': comment['body'],
                'id': comment['id'],
                'commentable_id': comment['commentable_id'],
                'type': comment['type'],
                'user_id': comment['user_id'],
                'children': comment['children'],
                'other_com': [],
                'endorsed': true/false
            }
        student_forum  = { 
            user id { 
                hilo id {
                    comment id : [] 
                    }
                }
            }
        */
        var score = data['score'] || '';
        
        var style_flecha = 'style="color: #c7bdbd;"';
        var class_empty = 'class_empty_main_user';
        if (!isEmpty(data['student_forum'])){
            style_flecha = 'style="color: #0075b4;"';
            class_empty = ''
        }
        var aux_id = data['id'] + '_forumgrade_' + settings.location;
        var flecha = '<span class="fa fa-chevron-right" aria-hidden="true" ' + style_flecha + '></span>';
        var aux_html = '<li class="outline-item main_user ' + class_empty +' "><div class="row row_gradeforum">'+
                    '<div class="col-md-3 eolgradediscussion_username"><span> '+data['username'] +'</span></div>'+
                    '<div class="col-md-5 eolgradediscussion_comment_main"><textarea class="eolgradediscussion_comment_input" type="text" spellcheck="false">'+data['feedback'] +'</textarea></div>'+
                    '<div class="col-md-2 eolgradediscussion_puntaje" ><input name="puntaje" class="decimalx" type="text" value="'+score+'" aria-controls="'+data['id'] +'"></div>'+
                    '<div class="col-md-2 eolgradediscussion_flecha"><button class="forumgrade-row-button" aria-expanded="false" aria-controls="'+aux_id+'">'+
                        flecha+
                    '</button></div></div>';
        var aux_thread = '';
        if (! isEmpty(data['student_forum'])){
            aux_html = aux_html + '<ol id="'+aux_id+'" class="ol_thread is-hidden" aria-labelledby="expand-collapse-outline-all-button">';
            for(var hilo in data['student_forum']){
                var aux_id = data['id'] + '_' + hilo + '_' + settings.location;
                aux_thread = aux_thread + create_accordion_thread(content_forum[hilo], data['id']);
                var aux_comments = '';
                if ( !isEmpty(data['student_forum'][hilo]) || content_forum[hilo]['children'].length > 0){
                    aux_comments = '<ol id="'+aux_id+'" class="is-hidden" aria-labelledby="expand-collapse-outline-all-button">' + headers_comment();
                    var comentarios = [];
                    if (!isEmpty(data['student_forum'][hilo])){
                        comentarios = Object.keys(data['student_forum'][hilo]);
                    }
                    else {
                        if (content_forum[hilo]['children'].length > 0){
                            comentarios = content_forum[hilo]['children'];
                        }
                    }
                    var aux_subcomments = '';
                    for(var j=0; j<comentarios.length;j++){
                        aux_comments = aux_comments + create_accordion_comments(content_forum[comentarios[j]], data['id']);
                        if ((data['student_forum'][hilo][comentarios[j]] != undefined && data['student_forum'][hilo][comentarios[j]].length > 0) || content_forum[comentarios[j]]['children'].length > 0){
                            var aux_id = data['id'] + '_' + comentarios[j] + '_' + settings.location;
                            var subcomments = []
                            if (data['student_forum'][hilo][comentarios[j]] != undefined && data['student_forum'][hilo][comentarios[j]].length > 0 ){
                                subcomments = data['student_forum'][hilo][comentarios[j]];
                            }
                            else{
                                subcomments =content_forum[comentarios[j]]['children'];
                            }
                            aux_subcomments = '<ol id="'+aux_id+'" class="ol_sub_comment is-hidden" aria-labelledby="expand-collapse-outline-all-button">';
                            for(var k=0; k<subcomments.length;k++){
                                aux_subcomments = aux_subcomments + create_accordion_subcomment(content_forum[subcomments[k]]);
                            }
                            aux_subcomments = aux_subcomments + '</ol>';
                        }
                        aux_comments = aux_comments + aux_subcomments + '</li>';
                    }
                    aux_comments = aux_comments  + '</ol>';
                }
                aux_thread = aux_thread + aux_comments + '</li>';
            }
            aux_html = aux_html + aux_thread + '</ol>';
        }
        aux_html = aux_html + '</li>';
        
        return aux_html
    }
    function isEmpty(ob){
        for(var p in ob){ return false;}
       return true;
     }
     
    function create_accordion_thread(data, user_id){
        var thread_id = user_id + '_' + data['id'] + '_' + settings.location;
        var style_flecha = 'style="color: #c7bdbd;"'
        if (data['children'].length > 0){
            style_flecha = 'style="color: #0075b4;"'
        }
        var flecha = '<span class="fa fa-chevron-right" aria-hidden="true" ' + style_flecha + '></span>';
        var thread_html = '<li class="outline-item main_thread"><div class="row row_gradeforum">'+
                    '<div class="col-md-3 eolgradediscussion_username"><span> '+data['username'] +'</span></div>'+
                    '<div class="col-md-7 eolgradediscussion_comment" aria-controls="'+ data['id']+'"><a href="'+ data['url_thread'] +'" target="_blank" style="color: #0075b4;">'+ data['title'] +'</a></div>'+
                    '<div class="col-md-2 eolgradediscussion_flecha"><button class="forumgrade-row-button" aria-expanded="false" aria-controls="'+thread_id+'">'+
                        flecha+
                    '</button></div></div><div class="row row_description"><div class="col-md-12 col_description"><span>'+ data['body'] +'</span></div></div>';
        return thread_html
    }
    function create_accordion_comments(data, user_id){
        var endorsed = data['endorsed'] || 'false'
        var comment_id = user_id + '_' + data['id'] + '_' + settings.location;
        var style_flecha = 'style="color: #c7bdbd;"'
        if (data['children'].length > 0){
            style_flecha = 'style="color: #0075b4;"'
        }
        var flecha = '<span class="fa fa-chevron-right" aria-hidden="true" ' + style_flecha + '></span>'
        var comment_html = '<li class="outline-item thread_comment"><div class="row row_thread_comment">'+
                    '<div class="col-md-3 eolgradediscussion_username"><span> '+data['username'] +'</span></div>'+
                    '<div class="col-md-7 eolgradediscussion_comment" aria-controls="'+ data['id']+'"><span aria-controls="'+ endorsed+'">'+ data['body'] +'</span></div>'+
                    '<div class="col-md-2 eolgradediscussion_flecha"><button class="forumgrade-row-button" aria-expanded="false" aria-controls="'+comment_id+'">'+
                        flecha+
                    '</button></div></div>';
        return comment_html
    }
    function headers_comment(){
        var headers = '<div class="row row_headers" style="text-align: center;font-weight: bold;">'+
                '<div class="col-md-3 eolgradediscussion_username"><span>Usuario</span></div>'+
                '<div class="col-md-7 eolgradediscussion_comment"><span>Comentarios</span></div>'+
                '<div class="col-md-2 eolgradediscussion_flecha"><span>Ver Mas</span></div></div>';
        return headers
    }

    function create_accordion_subcomment(data){
        /*
        data = {
                'thread_id': comment['thread_id'],
                'username': comment['username'],
                'body': comment['body'],
                #'parent_id': comment['parent_id'],
                'id': comment['id'],
                'commentable_id': comment['commentable_id'],
                'type': comment['type'],
                'user_id': comment['user_id'],
                'children': comment['children']
            }
        */
        var endorsed = data['endorsed'] || 'false'
        var comentario = data['body'] || '';
        var aux_html = '<li class="outline-item li_sub_comment"><div class="row row_gradeforum">'+
                    '<div class="col-md-3 eolgradediscussion_username"><span>'+data['username'] +'</span></div>'+
                    '<div class="col-md-9 eolgradediscussion_comment" aria-controls="'+ data['id']+'"><span aria-controls="'+ endorsed+'">'+comentario +'</span></div></li>';
        return aux_html
    }
    $(element).find('.forumgrade-row-button').live('click', function(e) {
        var boton = e.currentTarget
        var next_block = boton.getAttribute('aria-controls')
        var block = document.getElementById(next_block)
        var flecha = boton.children[0]
        if (block){
            if (block.style.display === "block") {
                if (flecha) flecha.className = 'fa fa-chevron-right'
                block.style.display = "none";
            } 
            else {
                if (flecha) flecha.className = 'fa fa-chevron-right fa-rotate-90'
                block.style.display = "block";
            }
        }
    });

    $(element).find('.decimalx').live('keyup', function(e) {
        var val = $(this).val().trim()
        if(isNaN(val) || val.includes(".")){
            val = val.replace(/[^0-9]/g , '')
        }
        $(this).val(val)
        if (val == ''){
            val = '0'
        }
        var pmax = settings.puntajemax
        if (parseInt(val, 10) <= parseInt(pmax, 10) && parseInt(val, 10) >= 0 ){
            e.currentTarget.className = 'decimalx';
        }   
        else{
            e.currentTarget.className = 'decimalx error_decimal';
        }
    });
}
