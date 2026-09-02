from __future__ import annotations

import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from core_system.constants.status_constants import Status
from core_system.models import AccessSession, OfficerUser


class AuditorDashboardConsumer(AsyncWebsocketConsumer):
    GROUP_NAME = "auditor_dashboard"

    async def connect(self):
        self.user = None
        self._disconnecting = False

        access_token = self.scope.get("session", {}).get("access_token")

        if not access_token:
            query_string = self.scope.get("query_string", b"").decode()
            if query_string:
                params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
                access_token = params.get("token")

        if access_token:
            self.user = await self._authenticate(access_token)

        if self.user is None:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connected to auditor dashboard",
            "officer_name": self.user.full_name,
        }))

        pending_count = await self._get_pending_count()
        if pending_count > 0:
            await self.send(text_data=json.dumps({
                "type": "notification_summary",
                "pending_count": pending_count,
                "message": f"You have {pending_count} pending item(s) awaiting review.",
            }))

    @database_sync_to_async
    def _get_pending_count(self):
        from core_system.models import TransactionVerification
        return TransactionVerification.objects.filter(
            verification_status=Status.PENDING,
            auditor_id_FK__isnull=True,
        ).count()

    async def disconnect(self, close_code):
        self._disconnecting = True
        try:
            if self.user:
                try:
                    await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)
                except Exception:
                    pass
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or self._disconnecting:
            return
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except json.JSONDecodeError:
            pass

    @database_sync_to_async
    def _authenticate(self, token: str):
        try:
            session = AccessSession.objects.select_related("user_id_FK").get(
                token_id=token,
                session_status="Active",
                expires_at__isnull=False,
            )
            if session.expires_at and session.expires_at.tzinfo is not None:
                from django.utils import timezone
                if session.expires_at < timezone.now():
                    return None
            return session.user_id_FK
        except AccessSession.DoesNotExist:
            return None

    async def aid_post_created(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_created",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
            "aid_type": event.get("aid_type"),
            "total_expected": event.get("total_expected"),
            "target_month": event.get("target_month"),
        }))

    async def contribution_updated(self, event):
        await self.send(text_data=json.dumps({
            "type": "contribution_updated",
            "post_id": event.get("post_id"),
            "contribution_id": event.get("contribution_id"),
            "member_name": event.get("member_name"),
            "status": event.get("status"),
            "paid_amount": event.get("paid_amount"),
        }))

    async def aid_post_finished(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_finished",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
        }))

    async def aid_post_finish_requested(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_finish_requested",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
            "stage": event.get("stage"),
        }))

    async def aid_post_release_pending(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_release_pending",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
        }))

    async def pending_queue_updated(self, event):
        await self.send(text_data=json.dumps({
            "type": "pending_queue_updated",
            "queue_type": event.get("queue_type"),
            "count": event.get("count"),
        }))

    async def dashboard_refresh(self, event):
        await self.send(text_data=json.dumps({
            "type": "dashboard_refresh",
            "section": event.get("section", "all"),
        }))

    async def notification_summary(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification_summary",
            "pending_count": event.get("pending_count", 0),
            "message": event.get("message", ""),
        }))

    async def data_changed(self, event):
        await self.send(text_data=json.dumps({
            "type": "data_changed",
            "section": event.get("section", "all"),
        }))

    async def data_changed(self, event):
        await self.send(text_data=json.dumps({
            "type": "data_changed",
            "section": event.get("section", "all"),
        }))


class TreasurerDashboardConsumer(AsyncWebsocketConsumer):
    GROUP_NAME = "treasurer_dashboard"

    async def connect(self):
        self.user = None
        self._disconnecting = False

        access_token = self.scope.get("session", {}).get("access_token")

        if not access_token:
            query_string = self.scope.get("query_string", b"").decode()
            if query_string:
                params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
                access_token = params.get("token")

        if access_token:
            self.user = await self._authenticate(access_token)

        if self.user is None:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connected to treasurer dashboard",
            "officer_name": self.user.full_name,
        }))

        pending_count = await self._get_pending_count()
        if pending_count > 0:
            await self.send(text_data=json.dumps({
                "type": "notification_summary",
                "pending_count": pending_count,
                "message": f"You have {pending_count} returned item(s) pending resubmission.",
            }))

    @database_sync_to_async
    def _get_pending_count(self):
        from core_system.models import TransactionVerification
        return TransactionVerification.objects.filter(
            verification_status=Status.RETURNED_REVISION,
        ).count()

    async def disconnect(self, close_code):
        self._disconnecting = True
        try:
            if self.user:
                try:
                    await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)
                except Exception:
                    pass
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or self._disconnecting:
            return
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except json.JSONDecodeError:
            pass

    @database_sync_to_async
    def _authenticate(self, token: str):
        try:
            session = AccessSession.objects.select_related("user_id_FK").get(
                token_id=token,
                session_status="Active",
                expires_at__isnull=False,
            )
            if session.expires_at and session.expires_at.tzinfo is not None:
                from django.utils import timezone
                if session.expires_at < timezone.now():
                    return None
            return session.user_id_FK
        except AccessSession.DoesNotExist:
            return None

    async def aid_post_created(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_created",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
            "aid_type": event.get("aid_type"),
            "total_expected": event.get("total_expected"),
            "target_month": event.get("target_month"),
        }))

    async def contribution_updated(self, event):
        await self.send(text_data=json.dumps({
            "type": "contribution_updated",
            "post_id": event.get("post_id"),
            "contribution_id": event.get("contribution_id"),
            "member_name": event.get("member_name"),
            "status": event.get("status"),
            "paid_amount": event.get("paid_amount"),
        }))

    async def aid_post_finished(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_finished",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
        }))

    async def aid_post_finish_requested(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_finish_requested",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
            "stage": event.get("stage"),
        }))

    async def aid_post_release_pending(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_release_pending",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
        }))

    async def aid_post_repayment_pending(self, event):
        await self.send(text_data=json.dumps({
            "type": "aid_post_repayment_pending",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
        }))

    async def dashboard_refresh(self, event):
        await self.send(text_data=json.dumps({
            "type": "dashboard_refresh",
            "section": event.get("section", "all"),
        }))

    async def data_changed(self, event):
        await self.send(text_data=json.dumps({
            "type": "data_changed",
            "section": event.get("section", "all"),
        }))

    async def notification_summary(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification_summary",
            "pending_count": event.get("pending_count", 0),
            "message": event.get("message", ""),
        }))


class PresidentDashboardConsumer(AsyncWebsocketConsumer):
    GROUP_NAME = "president_dashboard"

    async def connect(self):
        self.user = None
        self._disconnecting = False

        access_token = self.scope.get("session", {}).get("access_token")

        if not access_token:
            query_string = self.scope.get("query_string", b"").decode()
            if query_string:
                params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
                access_token = params.get("token")

        if access_token:
            self.user = await self._authenticate(access_token)

        if self.user is None:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connected to president dashboard",
            "officer_name": self.user.full_name,
        }))

        pending_count = await self._get_pending_count()
        if pending_count > 0:
            await self.send(text_data=json.dumps({
                "type": "notification_summary",
                "pending_count": pending_count,
                "message": f"You have {pending_count} item(s) awaiting your signature.",
            }))

    @database_sync_to_async
    def _get_pending_count(self):
        from core_system.models import TransactionVerification
        return TransactionVerification.objects.filter(
            verification_status=Status.AUDITOR_VERIFIED,
            president_id_FK__isnull=True,
        ).count()

    async def disconnect(self, close_code):
        self._disconnecting = True
        try:
            if self.user:
                try:
                    await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)
                except Exception:
                    # Log but don't fail on group discard errors during shutdown
                    pass
        except Exception:
            # Silently handle any exceptions during disconnect to prevent blocking shutdown
            pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or self._disconnecting:
            return
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except json.JSONDecodeError:
            pass

    @database_sync_to_async
    def _authenticate(self, token: str):
        try:
            session = AccessSession.objects.select_related("user_id_FK").get(
                token_id=token,
                session_status="Active",
                expires_at__isnull=False,
            )
            if session.expires_at and session.expires_at.tzinfo is not None:
                from django.utils import timezone
                if session.expires_at < timezone.now():
                    return None
            return session.user_id_FK
        except AccessSession.DoesNotExist:
            return None

    async def dashboard_refresh(self, event):
        if self._disconnecting:
            return
        await self.send(text_data=json.dumps({
            "type": "dashboard_refresh",
            "section": event.get("section", "all"),
        }))

    async def aid_post_finished(self, event):
        if self._disconnecting:
            return
        await self.send(text_data=json.dumps({
            "type": "aid_post_finished",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
        }))

    async def aid_post_finish_requested(self, event):
        if self._disconnecting:
            return
        await self.send(text_data=json.dumps({
            "type": "aid_post_finish_requested",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
            "stage": event.get("stage"),
        }))

    async def aid_post_release_pending(self, event):
        if self._disconnecting:
            return
        await self.send(text_data=json.dumps({
            "type": "aid_post_release_pending",
            "post_id": event.get("post_id"),
            "member_name": event.get("member_name"),
        }))

    async def pending_queue_updated(self, event):
        if self._disconnecting:
            return
        await self.send(text_data=json.dumps({
            "type": "pending_queue_updated",
            "queue_type": event.get("queue_type"),
            "count": event.get("count"),
        }))

    async def notification_summary(self, event):
        if self._disconnecting:
            return
        await self.send(text_data=json.dumps({
            "type": "notification_summary",
            "pending_count": event.get("pending_count", 0),
            "message": event.get("message", ""),
        }))


class MemberDashboardConsumer(AsyncWebsocketConsumer):
    """Live per-member group so the Member PWA bell updates instantly.

    Group name: member_{member_id_PK}
    """

    async def connect(self):
        self.user = None
        self.member = None
        self._disconnecting = False

        access_token = self.scope.get("session", {}).get("access_token")

        if not access_token:
            query_string = self.scope.get("query_string", b"").decode()
            if query_string:
                params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
                access_token = params.get("token")

        if access_token:
            self.user = await self._authenticate(access_token)
            self.member = await self._get_member()

        if self.member is None:
            await self.close(code=4001)
            return

        self.group_name = f"member_{self.member.member_id_PK}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connected to member dashboard",
            "member_name": self.member.full_name,
        }))

        unread = await self._get_unread_count()
        if unread > 0:
            await self.send(text_data=json.dumps({
                "type": "notification_summary",
                "pending_count": unread,
                "message": f"You have {unread} unread notification(s).",
            }))

    @database_sync_to_async
    def _authenticate(self, token: str):
        try:
            session = AccessSession.objects.select_related("user_id_FK").get(
                token_id=token,
                session_status="Active",
                expires_at__isnull=False,
            )
            if session.expires_at and session.expires_at.tzinfo is not None:
                from django.utils import timezone
                if session.expires_at < timezone.now():
                    return None
            return session.user_id_FK
        except AccessSession.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_member(self):
        from core_system.models import Member
        if self.user is None:
            return None
        return Member.objects.filter(officer_user_id_FK=self.user).first()

    @database_sync_to_async
    def _get_unread_count(self):
        from core_system.models import Notification
        return Notification.objects.filter(
            recipient_type="member",
            recipient_id=self.member.member_id_PK,
            is_read=False,
        ).count()

    async def disconnect(self, close_code):
        self._disconnecting = True
        if self.member:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except json.JSONDecodeError:
            pass

    async def notification_created(self, event):
        if self._disconnecting:
            return
        await self.send(text_data=json.dumps({
            "type": "notification_created",
            "notification": event.get("notification", {}),
        }))

    async def data_changed(self, event):
        if self._disconnecting:
            return
        await self.send(text_data=json.dumps({
            "type": "data_changed",
            "section": event.get("section", "all"),
        }))
