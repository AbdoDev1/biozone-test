from django.db import models

# Create your models here.
from django.db import models
from accounts.models import User, ClientProfile


class ClientManager(models.Manager):
    def pending(self):
        return self.filter(user__status='PENDING')

    def active(self):
        return self.filter(user__status='ACTIVE')


class Client(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='client',
    )
    profile = models.OneToOneField(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='client',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    objects = ClientManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile.business_name}"

    @property
    def is_active(self):
        return self.user.status == 'ACTIVE'

    @property
    def is_pending(self):
        return self.user.status == 'PENDING'

