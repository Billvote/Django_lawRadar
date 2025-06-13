from django.db import models
from geovote.models import Age

class Bill(models.Model):
    age = models.ForeignKey(Age, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    bill_id = models.CharField(max_length=100, unique=True)
    bill_number = models.CharField(max_length=100, unique=True)
    cleaned = models.TextField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    cluster = models.IntegerField()
    cluster_keyword = models.TextField(blank=True, null=True, default='')
    label = models.IntegerField(null=True, blank=True)
    url = models.TextField(blank=True, null=True, unique=True)

    def __str__(self):
        return self.title

    def get_related_count(self):
        return Bill.objects.filter(label=self.label).count()

    class Meta:
        indexes = [
            models.Index(fields=['label', 'bill_number']),
            models.Index(fields=['cluster_keyword']),
        ]