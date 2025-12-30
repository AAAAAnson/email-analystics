import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.config import settings
from app.models.email import Email
from app.models.sync_status import SyncStatus

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.imap_server = settings.email_imap_server
        self.imap_port = settings.email_imap_port
        self.email_address = settings.email_address
        self.email_password = settings.email_password
        self.connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> bool:
        """连接到IMAP服务器"""
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.email_address, self.email_password)
            logger.info(f"成功连接到邮箱: {self.email_address}")
            return True
        except Exception as e:
            logger.error(f"连接邮箱失败: {e}")
            return False

    def disconnect(self):
        """断开IMAP连接"""
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    def _decode_str(self, s: str) -> str:
        """解码邮件头部字符串"""
        if not s:
            return ""
        decoded_parts = []
        for part, encoding in decode_header(s):
            if isinstance(part, bytes):
                try:
                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                except Exception:
                    decoded_parts.append(part.decode('utf-8', errors='ignore'))
            else:
                decoded_parts.append(part)
        return ''.join(decoded_parts)

    def _get_email_body(self, msg: email.message.Message) -> tuple:
        """提取邮件正文"""
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        text = payload.decode(charset, errors='ignore')
                        if content_type == "text/plain":
                            body_text = text
                        elif content_type == "text/html":
                            body_html = text
                except Exception as e:
                    logger.warning(f"解析邮件正文失败: {e}")
        else:
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    text = payload.decode(charset, errors='ignore')
                    if content_type == "text/plain":
                        body_text = text
                    elif content_type == "text/html":
                        body_html = text
            except Exception as e:
                logger.warning(f"解析邮件正文失败: {e}")

        # 如果只有HTML，提取纯文本
        if not body_text and body_html:
            soup = BeautifulSoup(body_html, 'lxml')
            body_text = soup.get_text(separator='\n', strip=True)

        return body_text, body_html

    def _get_attachments(self, msg: email.message.Message) -> List[Dict]:
        """提取附件信息"""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_str(filename)
                        attachments.append({
                            "filename": filename,
                            "content_type": part.get_content_type(),
                            "size": len(part.get_payload(decode=True) or b"")
                        })
        return attachments

    def fetch_emails(self, folder: str = "INBOX", limit: int = 100, since_uid: int = 0) -> List[Dict[str, Any]]:
        """获取邮件列表"""
        if not self.connection:
            if not self.connect():
                return []

        emails = []
        try:
            self.connection.select(folder)

            # 搜索邮件
            if since_uid > 0:
                # 获取UID大于指定值的邮件
                status, data = self.connection.uid('search', None, f'UID {since_uid}:*')
            else:
                status, data = self.connection.search(None, 'ALL')

            if status != 'OK':
                return []

            email_ids = data[0].split()
            # 取最新的limit封邮件
            email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids

            for email_id in email_ids:
                try:
                    if since_uid > 0:
                        status, msg_data = self.connection.uid('fetch', email_id, '(RFC822)')
                    else:
                        status, msg_data = self.connection.fetch(email_id, '(RFC822)')

                    if status != 'OK':
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # 获取UID
                    if since_uid > 0:
                        uid = int(email_id.decode())
                    else:
                        status, uid_data = self.connection.fetch(email_id, '(UID)')
                        uid = int(uid_data[0].decode().split('UID ')[1].split(')')[0])

                    # 解析邮件
                    message_id = msg.get('Message-ID', f'<{uid}@local>')
                    subject = self._decode_str(msg.get('Subject', ''))
                    sender = self._decode_str(msg.get('From', ''))
                    recipients = self._decode_str(msg.get('To', ''))
                    cc = self._decode_str(msg.get('Cc', ''))

                    # 解析日期
                    date_str = msg.get('Date', '')
                    try:
                        date = parsedate_to_datetime(date_str) if date_str else datetime.utcnow()
                    except Exception:
                        date = datetime.utcnow()

                    # 获取正文和附件
                    body_text, body_html = self._get_email_body(msg)
                    attachments = self._get_attachments(msg)

                    emails.append({
                        "uid": uid,
                        "message_id": message_id,
                        "subject": subject,
                        "sender": sender,
                        "recipients": recipients,
                        "cc": cc,
                        "date": date,
                        "body_text": body_text,
                        "body_html": body_html,
                        "folder": folder,
                        "has_attachments": len(attachments) > 0,
                        "attachments": attachments
                    })

                except Exception as e:
                    logger.error(f"解析邮件失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"获取邮件列表失败: {e}")

        return emails

    async def sync_emails_to_db(self, db: AsyncSession, folder: str = "INBOX", limit: int = 500) -> Dict[str, Any]:
        """同步邮件到数据库"""
        # 获取同步状态
        result = await db.execute(select(SyncStatus).where(SyncStatus.folder == folder))
        sync_status = result.scalar_one_or_none()

        if not sync_status:
            sync_status = SyncStatus(folder=folder, status="syncing")
            db.add(sync_status)
            await db.commit()
            await db.refresh(sync_status)

        sync_status.status = "syncing"
        await db.commit()

        try:
            # 获取邮件
            emails = self.fetch_emails(folder=folder, limit=limit, since_uid=sync_status.last_uid)

            new_count = 0
            max_uid = sync_status.last_uid

            for email_data in emails:
                # 检查是否已存在
                result = await db.execute(
                    select(Email).where(Email.message_id == email_data["message_id"])
                )
                existing = result.scalar_one_or_none()

                if not existing:
                    new_email = Email(
                        message_id=email_data["message_id"],
                        subject=email_data["subject"],
                        sender=email_data["sender"],
                        recipients=email_data["recipients"],
                        cc=email_data["cc"],
                        date=email_data["date"],
                        body_text=email_data["body_text"],
                        body_html=email_data["body_html"],
                        folder=email_data["folder"],
                        has_attachments=email_data["has_attachments"],
                        attachments=email_data["attachments"]
                    )
                    db.add(new_email)
                    new_count += 1

                if email_data["uid"] > max_uid:
                    max_uid = email_data["uid"]

            await db.commit()

            # 更新同步状态
            total = await db.execute(select(func.count(Email.id)).where(Email.folder == folder))
            sync_status.last_uid = max_uid
            sync_status.last_sync_at = datetime.utcnow()
            sync_status.total_emails = total.scalar()
            sync_status.status = "completed"
            await db.commit()

            return {
                "success": True,
                "new_emails": new_count,
                "total_emails": sync_status.total_emails
            }

        except Exception as e:
            logger.error(f"同步邮件失败: {e}")
            sync_status.status = "error"
            await db.commit()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            self.disconnect()


# 全局实例
email_service = EmailService()
