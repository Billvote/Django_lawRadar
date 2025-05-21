from django.db import models
from django.db import models
from django.contrib.gis.db import models as geomodels

# 의원
class Member(models.Model):
    name = models.CharField(max_length=100)  # 의원명
    party = models.ForeignKey(Party, on_delete=models.CASCADE)  # 정당
    district = models.ForeignKey(District, on_delete=models.CASCADE)  # 지역구
    gender = models.CharField(max_length=10)  # 성별
    committees = models.ManyToManyField('Committee')  # 소속 위원회

    def __str__(self):
        return f'{self.name} ({self.party.name}, {self.district.name})'

# 정당
class Party(models.Model):
    name = models.CharField(max_length=100, unique=True)  # 정당 이름

    def __str__(self):
        return self.name

# 지역구
class District(geomodels.Model):
    name = models.CharField(max_length=100, unique=True)  # 지역구 이름
    boundary = geomodels.PolygonField()  # 지역구의 경계(공간 데이터)

    def __str__(self):
        return self.name

# 위원회
class Committee(models.Model):
    name = models.CharField(max_length=100)  # 위원회 이름

    def __str__(self):
        return self.name

# 의안
class Bill(models.Model):
    name = models.CharField(max_length=200)  # 의안명
    bill_number = models.CharField(max_length=50)  # 의안 번호
    content = models.TextField()  # 주요 내용

    def __str__(self):
        return f'{self.name} ({self.bill_number})'

# 표결
class Vote(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)  # 의원
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)  # 의안
    vote_result = models.CharField(max_length=10)  # 찬성/반대/기권 등

    def __str__(self):
        return f'{self.member.name} voted {self.vote_result} on {self.bill.name}'
