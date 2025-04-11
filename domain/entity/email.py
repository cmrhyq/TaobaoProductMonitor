from dataclasses import dataclass


@dataclass
class EmailSender(object):
    """
    邮件发送器
    """
    email_host: str = None
    email_sender: str = None
    email_receivers: str = None
    email_license: str = None
    email_theme: str = None
    email_content: str = None
    attachments: str = None