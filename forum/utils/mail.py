import email
import socket
import os

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.header import Header
import email.Charset

from django.core.mail import DNS_NAME
from smtplib import SMTP
from forum import settings
from django.template import loader, Context, Template
from forum.utils.html import sanitize_html
from forum.context import application_settings
from forum.utils.html2text import HTML2Text
from threading import Thread

def send_msg_list(msgs, sender=None):
    if len(msgs):
        connection = SMTP(str(settings.EMAIL_HOST), str(settings.EMAIL_PORT),
                          local_hostname=DNS_NAME.get_fqdn())

        try:
            if (bool(settings.EMAIL_USE_TLS)):
                connection.ehlo()
                connection.starttls()
                connection.ehlo()

            if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
                connection.login(str(settings.EMAIL_HOST_USER), str(settings.EMAIL_HOST_PASSWORD))

            if sender is None:
                sender = str(settings.DEFAULT_FROM_EMAIL)

            for email, msg in msgs:
                try:
                    connection.sendmail(sender, [email], msg)
                except Exception, e:
                    pass
            try:
                connection.quit()
            except socket.sslerror:
                connection.close()
        except Exception, e:
            pass

def html2text(s, ignore_tags=(), indent_width=4, page_width=80):
    ignore_tags = [t.lower() for t in ignore_tags]
    parser = HTML2Text(ignore_tags, indent_width, page_width)
    parser.feed(s)
    parser.close()
    parser.generate()
    return parser.result

def named(data):
    if isinstance(data, (tuple, list)) and len(data) == 2:
        return '%s <%s>' % data

    return str(data)

def create_msg(subject, sender, recipient, html, text, images):
    msgRoot = MIMEMultipart('related')
    msgRoot['Subject'] = subject
    msgRoot['From'] = named(sender)
    msgRoot['To'] =  named(recipient)
    msgRoot.preamble = 'This is a multi-part message from %s.' % unicode(settings.APP_SHORT_NAME).encode('utf8')

    msgAlternative = MIMEMultipart('alternative')
    msgRoot.attach(msgAlternative)

    msgAlternative.attach(MIMEText(text, _charset='utf-8'))
    msgAlternative.attach(MIMEText(html, 'html', _charset='utf-8'))

    for img in images:
        try:
            fp = open(img[0], 'rb')
            msgImage = MIMEImage(fp.read())
            fp.close()
            msgImage.add_header('Content-ID', '<'+img[1]+'>')
            msgRoot.attach(msgImage)
        except:
            pass

    return msgRoot.as_string()

def send_email(subject, recipients, template, context={}, sender=None, images=[], threaded=True):
    if sender is None:
        sender = (unicode(settings.APP_SHORT_NAME), unicode(settings.DEFAULT_FROM_EMAIL))

    if not len(images):
        images = [(os.path.join(str(settings.UPFILES_FOLDER), os.path.basename(str(settings.APP_LOGO))), 'logo')]

    context.update(application_settings(None))
    html_body = loader.get_template(template).render(Context(context))
    txt_body = html2text(html_body)

    if isinstance(recipients, str):
        recipients = [recipients]

    msgs = []

    for recipient in recipients:
        if isinstance(recipient, str):
            recipient_data = ('recipient', recipient)
            recipient_context = None
        elif isinstance(recipient, (list, tuple)) and len(recipient) == 2:
            name, email = recipient
            recipient_data = (name, email)
            recipient_context = None
        elif isinstance(recipient, (list, tuple)) and len(recipient) == 3:
            name, email, recipient_context = recipient
            recipient_data = (name, email)
        else:
            raise Exception('bad argument for recipients')

        if recipient_context is not None:
            recipient_context = Context(recipient_context)
            msg_html = Template(html_body).render(recipient_context)
            msg_txt = Template(txt_body).render(recipient_context)
        else:
            msg_html = html_body
            msg_txt = txt_body

        msg = create_msg(subject, sender, recipient_data, msg_html, msg_txt, images)
        msgs.append((email, msg))

    if threaded:
        thread = Thread(target=send_msg_list, args=[msgs])
        thread.setDaemon(True)
        thread.start()
    else:
        send_msg_list(msgs)


def send_template_email(recipients, template, context):
    t = loader.get_template(template)
    context.update(dict(recipients=recipients, settings=settings))
    t.render(Context(context))

def create_and_send_mail_messages(messages):
    if not settings.EMAIL_HOST:
        return

    sender = Header(unicode(settings.APP_SHORT_NAME), 'utf-8')
    sender.append('<%s>' % unicode(settings.DEFAULT_FROM_EMAIL))
    sender = u'%s <%s>' % (unicode(settings.APP_SHORT_NAME), unicode(settings.DEFAULT_FROM_EMAIL))

    try:
        connection = SMTP(str(settings.EMAIL_HOST), str(settings.EMAIL_PORT),
                          local_hostname=DNS_NAME.get_fqdn())

        if (bool(settings.EMAIL_USE_TLS)):
            connection.ehlo()
            connection.starttls()
            connection.ehlo()

        if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
            connection.login(str(settings.EMAIL_HOST_USER), str(settings.EMAIL_HOST_PASSWORD))

        if sender is None:
            sender = str(settings.DEFAULT_FROM_EMAIL)

        for recipient, subject, html, text, media in messages:
            msgRoot = MIMEMultipart('related')

            msgRoot['Subject'] = Header(subject, 'utf-8')
            msgRoot['From'] = sender

            to = Header(recipient.username, 'utf-8')
            to.append('<%s>' % recipient.email)
            msgRoot['To'] = to

            msgRoot.preamble = 'This is a multi-part message from %s.' % unicode(settings.APP_SHORT_NAME).encode('utf8')

            msgAlternative = MIMEMultipart('alternative')
            msgRoot.attach(msgAlternative)

            msgAlternative.attach(MIMEText(text.encode('utf-8'), _charset='utf-8'))
            msgAlternative.attach(MIMEText(html.encode('utf-8'), 'html', _charset='utf-8'))

            for alias, location in media.items():
                fp = open(location, 'rb')
                msgImage = MIMEImage(fp.read())
                fp.close()
                msgImage.add_header('Content-ID', '<'+alias+'>')
                msgRoot.attach(msgImage)

            try:
                connection.sendmail(sender, [recipient.email], msgRoot.as_string())
            except Exception, e:
                pass

        try:
            connection.quit()
        except socket.sslerror:
            connection.close()
    except Exception, e:
        pass
