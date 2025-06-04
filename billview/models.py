from django.db import models
from geovote.models import Age

# bill
class Bill(models.Model):
    age = models.ForeignKey(Age, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)                 
    bill_id = models.CharField(max_length=100, unique=True)  
    bill_number = models.CharField(max_length=100, unique=True)
    summary = models.TextField(blank=True, null=True)
    cluster = models.IntegerField()
    cluster_keyword = models.TextField(blank=True, null=True, default='')
    label = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
