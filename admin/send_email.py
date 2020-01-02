# !/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import time
import datetime
import os
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import commands
import smtplib
import email.MIMEMultipart
import email.MIMEText
import email.MIMEBase
import os.path
import mimetypes
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email import Encoders
from email.header import Header
from email.MIMEMultipart import MIMEMultipart
from email.MIMEImage import MIMEImage
from email.utils import parseaddr, formataddr
import string
from logutil import logger


def send_rate_email(sender, receiver, cc_receiver, to, txt, title):
    #    to = _format_addr(to)
    subject = title
    table = """
     %s
    """ % (txt)
    msg = MIMEMultipart('related')
    msgAlternative = MIMEMultipart('alternative')
    msg.attach(msgAlternative)
    msgText = MIMEText(table, 'html', 'utf-8')
    msgAlternative.attach(msgText)

    msg["Accept-Language"] = "zh-CN"
    msg["Accept-Charset"] = "ISO-8859-1,utf-8"
    if not isinstance(subject, unicode):
        subject = unicode(subject)

    msg['Subject'] = subject
    msg['To'] = ','.join(to)
    if cc_receiver != None:
        msg['CC'] = ','.join(cc_receiver)

    #-----------------------------------------------------------
    s = smtplib.SMTP('corp.chinacache.com')
    answer = s.sendmail(sender, receiver, msg.as_string())
    s.close()
    logger.info('send_rate_email to: %s|| cc_receiver: %s|| receiver: %s|| answer: %s' % (to, cc_receiver, receiver, answer))
    if str(answer) == '{}':
        return 'success'
    else:
        return 'fail'


def get_email_data(need_alarm_rate, need_alarm_current, need_alarm_user):
    logger.info("get_email_data need_alarm_rate: %s|| need_alarm_current: %s|| need_alarm_user: %s" % (need_alarm_rate, need_alarm_current, need_alarm_user))
    txt_data = ""
    for line in range(len(need_alarm_rate)):
        txt_data += "<tr>"
        txt_data += "<td >" + str(need_alarm_user[line]) + "</td>"
        txt_data += "<td >" + str(need_alarm_rate[line]) + "</td>"
        txt_data += "<td >" + str(need_alarm_current[line]) + "</td>"
        txt_data += "</tr>"
    txt = "<html>"
    txt += "<body>"
    txt += "<table style=\"font-size: 14px;border-collapse:collapse;\" bordercolor=\"#C1DAD7\" border=\"1\";  cellspacing=\"0\">"
    txt += "<tr>"
    txt += "<th bgcolor=\"#CAE8EA\" colspan=\"3\" style=\"padding:5px 10px;\" align=\"left\">" + "限速组列表" + "</th>"
    txt += "</tr>"
    txt += "<tr>"
    txt += "<td bgcolor=\"#CAE8EA\" style=\"font-weight:bold;padding:5px 10px;\">" + "用户名" + "</td>"
    txt += "<td bgcolor=\"#CAE8EA\" style=\"font-weight:bold;padding:5px 10px;\">" + "限速值" + "</td>"
    txt += "<td bgcolor=\"#CAE8EA\" style=\"font-weight:bold;padding:5px 10px;\">" + "现在总带宽" + "</td>"
    txt += "</tr>"
    txt += txt_data
    txt += "</table>"
    txt += "</body>"
    txt += "</html>"
    logger.info("get_email_data txt: %s" % txt)
    send_rate_email("yanming.liang@chinacache.com", ["yanming.liang@chinacache.com"], [
                    "yanming.liang@chinacache.com"], ["yanming.liang@chinacache.com"], txt, "限速邮件告警")
