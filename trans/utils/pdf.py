import os
from urllib.parse import urljoin
from uuid import uuid4
import logging
import requests

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string

import pdfkit
from shutil import copyfile
from xvfbwrapper import Xvfb

from trans.context_processors import ioi_settings

logger = logging.getLogger(__name__)

def render_pdf_template(translation, task_type,
                        static_path, images_path, pdf_output):
    requested_user = translation.user
    task = translation.task

    if task_type == 'released':
        content = translation.get_published_text()
    else:
        content = translation.get_latest_text()

    context = {
        'content': content,
        'contest': task.contest.title,
        'task_name': task.name,
        'country': requested_user.country.code,
        'language': requested_user.language.name,
        'language_code': requested_user.language.code,
        'direction': requested_user.language.direction(),
        'username': requested_user.username,
        'pdf_output': pdf_output,
        'static_path': static_path,
        'images_path': images_path,
        'text_font_base64': requested_user.text_font_base64
    }
    context.update(ioi_settings(None))
    return render_to_string('pdf-template.html', context=context)

# pdf file paths (excepting final pdf path)
def output_pdf_path(contest_slug, task_name, task_type, user):
    file_path = '{}/output/{}/{}/{}'.format('/tmp/ioi-translation', contest_slug, task_name, task_type)
    file_name = '{}-{}.pdf'.format(task_name, user.username)
    pdf_file_path = '{}/{}'.format(file_path, file_name)
    os.makedirs(file_path, exist_ok=True)
    return pdf_file_path

def released_pdf_path(contest_slug, task_name, user):
    return output_pdf_path(contest_slug, task_name, 'released', user)

def unreleased_pdf_path(contest_slug, task_name, user):
    return output_pdf_path(contest_slug, task_name, 'task', user)

# base pdf is a pdf of ISC
def base_pdf_path(contest_slug, task_name, task_type):
    user = User.objects.get(username='ISC')
    return output_pdf_path(contest_slug, task_name, task_type, user)

def build_pdf(translation, task_type):
    task = translation.task
    user = translation.user
    pdf_file_path = output_pdf_path(task.contest.slug, task.name, task_type, user)

    last_edit_time = translation.get_latest_change_time()
    rebuild_needed = not os.path.exists(pdf_file_path) or os.path.getmtime(pdf_file_path) < last_edit_time
    if not rebuild_needed:
        return pdf_file_path

    html = render_pdf_template(
        translation, task_type,
        static_path=settings.STATIC_ROOT,
        images_path=settings.MEDIA_ROOT + 'images/',
        pdf_output=True,
    )
    convert_html_to_pdf(html, pdf_file_path)
    add_page_numbers_to_pdf(pdf_file_path, task.name)
    return pdf_file_path


def build_final_pdf(translation):
    task_type = 'released' if translation.user.username == 'ISC' else 'task'
    return build_pdf(translation, task_type)


def get_file_name_from_path(file_path):
    return file_path.split('/')[-1]


def pdf_response(pdf_file_path, file_name):
    with open(pdf_file_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'inline;filename={}'.format(file_name)
        response['pdf_file_path'] = pdf_file_path
        return response


def convert_html_to_pdf(html, pdf_file_path):
    try:
        html_file_path = '/tmp/{}.html'.format(str(uuid4()))
        with open(html_file_path, 'wb') as f:
            f.write(html.encode('utf-8'))
        with Xvfb():
            pdfkit.from_file(html_file_path, pdf_file_path, options=settings.WKHTMLTOPDF_CMD_OPTIONS)
        os.remove(html_file_path)
    except Exception as e:
        logger.error(e)


def add_page_numbers_to_pdf(pdf_file_path, task_name):
    color =  '-color "0.4 0.4 0.4" '
    cmd = ('cpdf -add-text "{0} (%Page of %EndPage)   " -font "Arial" ' + color + \
          '-font-size 10 -bottomright .62in {1} -o {1}').format(task_name, pdf_file_path)
    os.system(cmd)


def add_info_line_to_pdf(pdf_file_path, info):
    color =  '-color "0.4 0.4 0.4" '
    output_pdf_path = '/tmp/{}.pdf'.format(str(uuid4()))
    cmd = 'cpdf -add-text "   {}" -font "Arial" -font-size 10 -bottomleft .62in {} -o {} {}'.format(
        info, pdf_file_path, output_pdf_path, color)
    os.system(cmd)
    return output_pdf_path

# This is Iranian version of printing, edited by Emil Abbasov (IOI2019):
def send_pdf_to_printer(pdf_file_path, country_code, country_name, printer_type, count=1):
    pdf_file = open(pdf_file_path, 'rb')
    upload_response = requests.post(
        '%s/upload' % settings.PRINT_SYSTEM_ADDRESS,
        files={'pdf': pdf_file},
        data={'type': 'translation'}
    )
    upload_response.raise_for_status()
    filename = upload_response.content
    response = requests.post(
        '%s/translation' % settings.PRINT_SYSTEM_ADDRESS,
        data={
            'filename': filename,
            'country_code': country_code,
            'country_name': country_name,
            'count': count,
            'printer_type': printer_type
        }
    )
    response.raise_for_status()
	
# This is Japan's version, not working with Iranian printing:
#def send_pdf_to_printer(pdf_file_path, country_code, country_name, cover_page=False, count=1):
#    with open(pdf_file_path, 'rb') as pdf_file:
#        response = requests.post(
#            urljoin(settings.PRINT_SYSTEM_ADDRESS, '/translation'),
#            files={'pdf': pdf_file},
#            data={
#                'country_code': country_code,
#                'country_name': country_name,
#                'cover_page': (1 if cover_page else 0),
#                'count': count,
#            },
#        )
#    response.raise_for_status()

# ADDED by Emil Abbasov, IOI2019

def merge_final_pdfs(task_names, username):
    os.system('mkdir -p media/merged') # create dir silently if doeesnt exist
    output_pdf_path = 'media/merged/{}-merged.pdf'.format(username)
    
    cmd = 'cpdf '
	
    for task_name in task_names:
        cmd = cmd + 'media/final_pdf/{}/{}.pdf '.format(task_name,username)
    cmd = cmd + '-o {}'.format(output_pdf_path)
	
    os.system(cmd)
    return output_pdf_path