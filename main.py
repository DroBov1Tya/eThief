import os
import re
import time
import imaplib
import email
from email.header import decode_header
from contextlib import contextmanager


# Ваши учетные данные
imap_server = os.getenv('IMAP_SERVER')
email_user = os.getenv('EMAIL_USER')
password = os.getenv('PASSWORD')  # Используйте приложение для токенов для большей безопасности

# Инициализация директорий
def initialize_directories(base_dir):
    dirs = {
        "attachments": os.path.join(base_dir, "attachments"),
        "inbox": os.path.join(base_dir, "inbox"),
        "sent": os.path.join(base_dir, "sent"),
    }
    for key, path in dirs.items():
        os.makedirs(path, exist_ok=True)
    return dirs

# Контекстный менеджер для работы с IMAP-соединением
@contextmanager
def imap_connection(server, user, password):
    mail = imaplib.IMAP4_SSL(server)
    try:
        mail.login(user, password)
        yield mail
    finally:
        mail.logout()

# Декодирование заголовка и очистка темы
def decode_subject(subject):
    subject, encoding = decode_header(subject)[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding if encoding else 'utf-8')
    return re.sub(r'[^\w\s]', '', subject)  # Удаление специальных символов

# Сохранение контента сообщения в файл
def save_email_content(target_dir, filename, content, is_html=False):
    extension = "html" if is_html else "txt"
    filepath = os.path.join(target_dir, f"{filename}.{extension}")
    with open(filepath, "w", encoding="utf-8") as file:
        file.write(content)
    print(f"Saved email content to {filepath}")

# Обработка одной части сообщения
def process_message_part(part, base_filename, target_dir, attachments_dir, subject, from_):
    content_type = part.get_content_type()
    content_disposition = str(part.get("Content-Disposition"))

    if content_type == "text/html" or content_type == "text/plain":
        content = part.get_payload(decode=True).decode()
        is_html = content_type == "text/html"
        save_email_content(
            target_dir, 
            base_filename, 
            f"<html><body>\n<h2>{subject}</h2>\n<p>From: {from_}</p>\n{content}\n</body></html>" if is_html else content,
            is_html
        )
    elif "attachment" in content_disposition:
        filename = part.get_filename()
        if filename:
            filepath = os.path.join(attachments_dir, filename)
            with open(filepath, "wb") as f:
                f.write(part.get_payload(decode=True))
            print(f"Attachment {filename} downloaded to {attachments_dir}")

# Загрузка сообщения и его частей
def download_message(mail, mail_id, box, dirs):
    try:
        target_dir = dirs["inbox"] if box == "inbox" else dirs["sent"]
        attachments_dir = dirs["attachments"]

        status, msg_data = mail.fetch(mail_id, '(RFC822)')
        if status != 'OK':
            return None

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_subject(msg["Subject"])
                from_ = decode_subject(msg.get("From"))
                base_filename = f"{subject[:50]}_{mail_id.decode()}"

                if msg.is_multipart():
                    for part in msg.walk():
                        process_message_part(part, base_filename, target_dir, attachments_dir, subject, from_)
                else:
                    process_message_part(msg, base_filename, target_dir, attachments_dir, subject, from_)
    except Exception as e:
        print(f"An error occurred while downloading message {mail_id}: {e}")

# Проверка почтового ящика
def check_mail(server, user, password, box, retries=3):
    for attempt in range(retries):
        try:
            with imap_connection(server, user, password) as mail:
                status, _ = mail.select(box)
                if status != 'OK':
                    raise Exception(f"Failed to select mailbox: {box}")

                status, messages = mail.search(None, 'ALL')
                if status != 'OK':
                    return set()

                return set(messages[0].split())
        except Exception as e:
            print(f"An error occurred while checking mail (attempt {attempt + 1}): {e}")
            time.sleep(5)
    return set()

# Обработка новых сообщений
def process_new_messages(server, user, password, old_messages, new_messages, box, dirs):
    new_emails = new_messages - old_messages
    if not new_emails:
        return

    try:
        with imap_connection(server, user, password) as mail:
            mail.select(box)
            for mail_id in new_emails:
                download_message(mail, mail_id, box, dirs)
                # Помечаем сообщение как непрочитанное
                mail.store(mail_id, '-FLAGS', '\\Seen')
    except Exception as e:
        print(f"An error occurred while processing messages: {e}")

# Основной цикл
if __name__ == "__main__":
    print("It's Work!")
    base_dir = "/app/saved_emails"  # Это путь, указанный в volume
    dirs = initialize_directories(base_dir)
    inbox = "inbox"
    sent = "Sent"
    old_messages_inbox = check_mail(imap_server, email_user, password, inbox)
    old_messages_sent = check_mail(imap_server, email_user, password, sent)
    
    while True:
        time.sleep(5)
        new_messages_inbox = check_mail(imap_server, email_user, password, inbox)
        new_messages_sent = check_mail(imap_server, email_user, password, sent)

        process_new_messages(imap_server, email_user, password, old_messages_inbox, new_messages_inbox, inbox, dirs)
        process_new_messages(imap_server, email_user, password, old_messages_sent, new_messages_sent, sent, dirs)

        old_messages_inbox = new_messages_inbox
        old_messages_sent = new_messages_sent