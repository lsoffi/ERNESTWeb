import uuid
from django.db import models
from django.conf import settings
class Attempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40)
    quiz = models.CharField(max_length=32)
    answers = models.JSONField(default=list)
    score = models.PositiveIntegerField(default=0)
    finished = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    window = models.BigIntegerField(default=0)

class AccountEmail(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    address = models.EmailField(unique=True)
    verified = models.BooleanField(default=False)


class PrivacyOperation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=64, unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='privacy_operations')
    # Identify a deleted account after a restore without retaining its email/name.
    subject_id_at_request = models.PositiveIntegerField()
    subject_joined_at = models.DateTimeField()
    received_on = models.DateField()
    verification_method = models.CharField(max_length=20)
    verified_on = models.DateField()
    action = models.CharField(max_length=16)
    performed_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(default=dict)
    replied_on = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'operazione privacy'
        verbose_name_plural = 'operazioni privacy'
