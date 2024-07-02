var task_id, task_text, translation_text;
var save_task_url, task_version_url, access_edit_translate_url,
    home_page_url, finish_translation_url, list_version_url, release_task_url;
var csrf_token;
var last_time_get_edit_token;
var latest_translation_text;
var simplemde;
var left_plain_text_box_id;
var direction, language;
var last_saved_text;
var previewInterval;
var spellChecking = false;
var initialized = false;

// Settings
var markdown_render_interval = 100;
var autosave_interval = 30 * 1000;
var update_token_interval = 60 * 1000;

function transLog(msg){
    console.log("Translate: " + msg);
}


$(document).ready(function() {
    transLog("Initializing");
    if (direction=='rtl') {
        left_plain_text_box_id = 'left_rtl_plain_text_box';
        $('#' + left_plain_text_box_id).moratab('', {strings: {help: ''}});
    }
    else {
        left_plain_text_box_id = 'left_ltr_plain_text_box';
        $('#' + left_plain_text_box_id).html('');
        simplemde = new SimpleMDE({
            element: document.getElementById('left_ltr_plain_text_box'),
            status: false,
            toolbar: false,
            spellChecker: false,
            initialValue: ''
        });
    }
    getEditTranslateAccess(initial);

});


function loadTranslationText(text){

    if (direction=='rtl') {
        $('#' + left_plain_text_box_id).html('');
        $('#' + left_plain_text_box_id).moratab(text, {strings: {help: ''}});
    }
    else {
        $('#' + left_plain_text_box_id).html('');
        simplemde.value(text)
        simplemde.codemirror.refresh()
    }
}

function initial(){

    $('#left_rendered_text_box').css('direction', direction);
    task_text = $("#temp").html();
    translation_text = currentTranslationText();
    latest_translation_text = '';
    last_saved_text = currentTranslationText();
    setInterval(autoSave, autosave_interval)
    setInterval(onlinePreview, markdown_render_interval);
    onPreviewClick();
    initialized = true;
    transLog("Ready");
}

function currentTranslationText(){
    if (direction=='rtl')
        return $('#' + left_plain_text_box_id).text();
    return simplemde.value();
}

function renderMarkdown(id, text){
    $('#' + id).html(marked(text));
    renderMathInElement(document.getElementById(id));
}

function onlinePreview() {
    current_text = currentTranslationText();
    if (current_text != latest_translation_text){
        latest_translation_text = current_text;
        renderMarkdown('preview', current_text)
    }
}

function switchTab(id){
    var tabs = ['preview', 'isc-preview', 'isc-markdown'];
    for (var i = 0 ; i < 3 ; i++) {
        $('#' + tabs[i]).hide();
        $('#' + tabs[i] + '-btn').removeClass('btn-active');
    }
    $('#' + id).show();
    $('#' + id + '-btn').addClass('btn-active');
}

function onPreviewClick(){
    current_text = currentTranslationText();
    renderMarkdown('preview', current_text);
    switchTab('preview');
}

function onIscPreviewClick(){
    renderMarkdown('isc-preview', task_text);
    switchTab('isc-preview');
}

function onIscMarkdownClick(){
    $('#isc-markdown').html(task_text);
    switchTab('isc-markdown');
}

function autoSave() {
    transLog("Auto-save");
    saveVersion(true);
}

function saveAndGo(url, new_tab=false) {
    saveVersion(true, function() {
        if (new_tab) {
            window.open(url, '_blank').focus();
        } else {
            releaseToken(function() { window.location.href = url; });
        }
    });
}

function setEditToken(edit_token){
    last_time_get_edit_token = new Date();
    transLog("Edit token " + edit_token);
    sessionStorage.setItem('edit_translate_token_' + task_id, edit_token);
}

function saveVersion(autosave=false, callback=null) {
    current_trans_text = currentTranslationText();
    if (autosave && last_saved_text == current_trans_text) {
        if (callback)
            callback();
        return;
    }
    var edit_token = sessionStorage.getItem('edit_translate_token_' + task_id)
    $.ajax({
        url: save_task_url,
        data: {
            content: currentTranslationText(),
            id: task_id,
            saved: !autosave,
            edit_token: edit_token,
            csrfmiddlewaretoken: csrf_token
        },
        type: "POST",
        success: function (response) {
            if (response.can_edit == false)
                handleAccessDenied();
            else {
                last_saved_text = current_trans_text;
                setEditToken(response.edit_token)
                if (callback)
                    callback();
                else if (!autosave)
                    ToastrUtil.success('Successfully saved!');
            }
        }
    });
}

function getEditTranslateAccess(callback) {
    var edit_token = sessionStorage.getItem('edit_translate_token_' + task_id)
    var originalTranslationText = currentTranslationText();
    transLog("Obtaining edit token");
    $.ajax({
        url: access_edit_translate_url,
        data: {
            id: task_id,
            edit_token: edit_token,
            csrfmiddlewaretoken: csrf_token
        },
        type: "POST",
        success: function(response) {
            if (response.can_edit == false) {
                handleAccessDenied();
                return;
            }

            setEditToken(response.edit_token);

            // Translation might've changed since this ajax call is done asynchronously.
            var translationText = currentTranslationText();

            if (originalTranslationText.length === 0 && translationText.length === 0) {
                // Initial load or refresh (without further update), just load the content.
                loadTranslationText(response.content);
            } else if (edit_token !== response.edit_token) {
                // If token stays the same, no other session has tried to edit the translation since
                // older token can't be reused once another token has been issued. Hence, the more
                // expensive translation comparison doesn't need to be done as often.

                var canKeepCurrentTranslationState = originalTranslationText === response.content;
                if (!canKeepCurrentTranslationState) {
                    ToastrUtil.info('Translation has changed since last edit. Refreshing translation.');
                    loadTranslationText(response.content);
                }
            }

            if (callback) callback();
        },
        error: function () {
            handleAccessDenied('Connection error!');
        }
    });
}

function releaseToken(callback=null) {
    transLog("Releasing token");
    var edit_token = sessionStorage.getItem('edit_translate_token_' + task_id)
    $.ajax({
        url: finish_translation_url,
        data: {
            id: task_id,
            edit_token: edit_token,
            csrfmiddlewaretoken: csrf_token
        },
        type: "POST",
        success: function (response) {
          edit_token = null;
          if (callback) callback();
        },
        error: function () {
        }
    });
};

function handleAccessDenied(message='') {
    transLog("Edit access denied");
    msg = message || "The task is open somewhere else!"
    bootbox.alert({
        // title: 'Alert',
        message: '<b>' + msg + '</b>',
        buttons: {
            ok: {label: 'Back to Home'},
        },
        callback: function (result) {
            window.location.replace(home_page_url);
        }
    });
}

function checkIfCanChange(){
    current_date = new Date();
    if ((current_date - last_time_get_edit_token) >  update_token_interval)
        getEditTranslateAccess();
}

window.addEventListener("beforeunload", function(e){
    transLog('About to unload page');
    if (initialized) {
        const current_trans_text = currentTranslationText();
        if (last_saved_text != current_trans_text) {
            e.returnValue = true;
            e.preventDefault();
        }
    }
});

window.addEventListener("unload", function(e){
    transLog('Unloading page');
    var edit_token = sessionStorage.getItem('edit_translate_token_' + task_id);
    if (edit_token) {
        transLog('Sending token release beacon');
        data = new URLSearchParams();
        data.append('id', task_id);
        data.append("edit_token", edit_token);
        data.append('csrfmiddlewaretoken', csrf_token);
        navigator.sendBeacon(finish_translation_url, data);
    }
});

function onChangeSpellChecking(){
    spellChecking = !spellChecking;
    var value = simplemde.value();

    /* reset simpleMDE container */
    var element = document.getElementById("left_text_box_container");
    while (element.firstChild) {
       element.removeChild(element.firstChild);
    }
    var textarea = document.createElement('textarea');
    textarea.setAttribute('id', 'left_ltr_plain_text_box');
    element.appendChild(textarea);

    /* new simpleMDE */
    simplemde = new SimpleMDE({
        element: document.getElementById("left_ltr_plain_text_box"),
        status: false,
        toolbar: false,
        spellChecker: spellChecking,
        initialValue: value
    });
}

function release() {
    autoSave();
    bootbox.prompt({
        title: 'Release Note:',
        buttons: {
            confirm: {label: 'Release'},
        },
        callback: function (result) {
            if (result)
                sendRelease(result);
            else if (result == '') {
                ToastrUtil.error('Release note cannot be empty.');
            }
        }
    });
}

function sendRelease(note) {
    transLog("Releasing");
    $.ajax({
        url: release_task_url,
        data: {
            release_note: note,
            csrfmiddlewaretoken: csrf_token
        },
        type: "POST",
        success: function (response) {
            last_saved_content = simplemde.value();
            ToastrUtil.success('Task released!');
            transLog("Release: Success");
        },
        error: function (response) {
            ToastrUtil.error('Release failed.');
            transLog("Release: Failure");
        }
    });
}
