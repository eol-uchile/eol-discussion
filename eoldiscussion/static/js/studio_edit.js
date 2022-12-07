/* Javascript for StudioEditableXBlockMixin. */
function StudioEditableXBlockMixin(runtime, element, settings) {
    "use strict";
    $(function($) {
        if(settings.is_dated){
            $(element).find('#li_start_date').show();
            $(element).find('#li_end_date').show();
        }
        else{
            $(element).find('#li_start_date').hide();
            $(element).find('#li_end_date').hide();
        }
    });
    $(element).find('#is_dated').on('change', function() {
        //0: disabled
        //1: enabled
        if($(this).find(":selected").val()=="1"){
            $(element).find('#li_start_date').show();
            $(element).find('#li_end_date').show();
            $(element).find('#start_date')[0].focus();
        }
        if($(this).find(":selected").val()=="0"){
            $(element).find('#li_start_date').hide();
            $(element).find('#li_end_date').hide();
        }        
      });
    $(element).find('#limit_character').each(function() {
        this.value = this.value.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    });
    $(element).find('#limit_character').bind('keyup', function(e) {
        var val = $(this).val()
        val = val.replace(/[^0-9]/g , '');
        if(parseInt(val)<=0){
            val = '1';
        }
        if(parseInt(val)>2000){
            val = '2.000';
        }
        $(this).val(val);
        this.value = this.value.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    });
    $(element).find('#limit_character').bind('change', function(e) {
        var val = $(this).val();
        if(val == ''){
            val = '1';
        }
        $(this).val(val);
    });
    var studio_submit = function(data) {
        var handlerUrl = runtime.handlerUrl(element, 'submit_studio_edits');
        runtime.notify('save', {state: 'start', message: gettext("Saving")});
        $.ajax({
            type: "POST",
            url: handlerUrl,
            data: JSON.stringify(data),
            dataType: "json",
            global: false,  // Disable Studio's error handling that conflicts with studio's notify('save') and notify('cancel') :-/
            success: function(response) { runtime.notify('save', {state: 'end'}); }
        }).fail(function(jqXHR) {
            var message = gettext("This may be happening because of an error with our server or your internet connection. Try refreshing the page or making sure you are online.");
            if (jqXHR.responseText) { // Is there a more specific error message we can show?
                try {
                    message = JSON.parse(jqXHR.responseText).error;
                    if (typeof message === "object" && message.messages) {
                        // e.g. {"error": {"messages": [{"text": "Unknown user 'bob'!", "type": "error"}, ...]}} etc.
                        message = $.map(message.messages, function(msg) { return msg.text; }).join(", ");
                    }
                } catch (error) { message = jqXHR.responseText.substr(0, 300); }
            }
            runtime.notify('error', {title: gettext("Unable to update settings"), message: message});
        });
    };

    $('.save-button', element).bind('click', function(e) {
        e.preventDefault();
        var limit = $(element).find('#limit_character')[0].value.replace(/[^0-9]/g , '');
        var is_dated = $(element).find('#is_dated').val();
        is_dated = is_dated == '1';
        var check = true;
        if(parseInt(limit)<=0 || parseInt(limit)>2000) check = true;
        if(is_dated){
            var start_date = new Date($(element).find('#start_date').val())
            var end_date = new Date($(element).find('#end_date').val())
            if(end_date > start_date) check = true;
        }
        if(!check){
            runtime.notify('error', {title: gettext("Unable to update settings"), message: 'Revise quelos parámetros enten correctos.'});
        }
        else{
            $(element).find('#limit_character')[0].value = limit.toString();
            var offset = new Date().getTimezoneOffset();
            var timezone = -(offset/60)
            var form_data = {
                'display_name': $(element).find('input[name=display_name]').val(),
                'discussion_category': $(element).find('input[name=discussion_category]').val(),
                'discussion_target': $(element).find('input[name=discussion_target]').val(),
                'limit_character': $(element).find('input[name=limit_character]').val(),
                'is_dated': is_dated,
                'start_date': $(element).find('input[name=start_date]').val(),
                'end_date': $(element).find('input[name=end_date]').val()
            }
            studio_submit(form_data);
        }
    });

    $(element).find('.cancel-button').bind('click', function(e) {
        e.preventDefault();
        runtime.notify('cancel', {});
    });
}