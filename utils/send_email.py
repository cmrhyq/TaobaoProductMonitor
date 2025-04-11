#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File send_email.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/15 0:35
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import smtplib
from loguru import logger
# 负责构造文本
from email.mime.text import MIMEText
# 负责构造图片
from email.mime.image import MIMEImage
# 负责将多个对象集合起来
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime

from domain.entity.email import EmailSender


class EmailService(object):
    def __init__(self, email_info: EmailSender):
        self.email_info = email_info

    def __format_email(self, send_email):
        """
        格式化邮件
        :param send_email: 要发送的邮件
        :return: 格式化后的
        """
        new_email = ""
        if "," in send_email:
            for rows in send_email.split(","):
                new_email = new_email + (rows.split("@")[0] + "<%s>" % rows + ",")
            send_email = new_email[0:-1]
        else:
            send_email = send_email.split("@")[0] + "<%s>" % send_email
        return send_email


    def __set_image(self, mm, image_path):
        """
        添加图片文件到邮件信息当中去
        :param mm:
        :param image_path: 图片路径
        :return:
        """
        image_name = image_path.split("/")[len(image_path.split("/")) - 1]
        logger.info("Start adding image named %s" % image_name)
        # 二进制读取图片
        image_data = open('image_path', 'rb')
        # 设置读取获取的二进制数据
        message_image = MIMEImage(image_data.read())
        # 关闭刚才打开的文件
        image_data.close()
        # 添加图片文件到邮件信息当中去
        mm.attach(message_image)


    def __set_file(self, mm, file_path):
        """
        加入附件
        :param mm:
        :param file_path: 文件路径
        :return:
        """
        for rows in file_path.split(","):
            file_name = rows.split("/")[len(rows.split("/")) - 1]
            logger.info("Start adding attachments named %s" % file_name)
            # 构造附件
            attach = MIMEText(open(rows, 'rb').read(), 'base64', 'utf-8')
            # 设置附件信息
            attach["Content-Disposition"] = 'attachment; filename="%s"' % file_name
            # 添加附件到邮件信息当中去
            mm.attach(attach)


    def send(self):
        """
        发送邮件
        :param email_info: email发送相关信息
        :return:
        """
        # 创建SMTP对象
        stp = smtplib.SMTP()
        mm = MIMEMultipart('related')
        try:
            # 主题
            theme = """%s""" % self.email_info.email_theme
            # 设置发送者，格式：sender_name<******@163.com>
            mm["From"] = self.__format_email(self.email_info.email_sender)
            mm["To"] = self.__format_email(self.email_info.email_receivers)
            mm["Subject"] = Header(theme, "utf-8")
            logger.info(f"Email receivers have {self.__format_email(self.email_info.email_receivers)}")

            # 正文
            content = f"{self.email_info.email_content}"
            send_text = MIMEText(content, "html", "utf-8")
            mm.attach(send_text)

            # 附件
            if self.email_info.attachments is not None:
                self.__set_file(mm, self.email_info.attachments)
                
            # 设置发件人邮箱的域名和端口，端口地址为25
            stp.connect(self.email_info.email_host, 25)
            # 打印出和SMTP服务器交互的所有信息
            # stp.set_debuglevel(1)
            # 登录邮箱，传递参数1：邮箱地址，参数2：邮箱授权码
            stp.login(self.email_info.email_sender, self.email_info.email_license)
            # 发送邮件，传递参数1：发件人邮箱地址，参数2：收件人邮箱地址，参数3：把邮件内容格式改为str
            stp.sendmail(self.email_info.email_sender, self.email_info.email_receivers, mm.as_string())
        except Exception as e:
            logger.error(e)
        finally:
            stp.quit()
