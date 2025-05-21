from django.db import models

# Create your models here.

# bill
from django.db import models

class Bill(models.Model):
    age = models.IntegerField()
    title = models.CharField(max_length=255)                 
    bill_id = models.CharField(max_length=100, unique=True)  
    bill_number = models.CharField(max_length=100, unique=True)
    content = models.TextField(blank=True, null=True)    
    
    def __str__(self):
        return self.title
