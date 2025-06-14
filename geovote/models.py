from django.db import models

# 대수
class Age(models.Model):
    number = models.IntegerField(unique=True)
    def __str__(self):
        return f"{self.number}대"

# 정당
class Party(models.Model):
    # age = models.IntegerField()
    party = models.CharField(max_length=100, unique=True)  # 정당 이름
    color = models.CharField(max_length=7, default="#000000") # 상징 컬러 코드
    def __str__(self):
        return self.party

# 지역구
from django.db import models

class District(models.Model):
    age = models.IntegerField()
    SGG_Code = models.CharField(max_length=100, unique=True)
    SIDO_SGG = models.CharField(max_length=100, unique=True)
    SIDO = models.CharField(max_length=100)
    SGG = models.CharField(max_length=100)
    boundary = models.JSONField()  # Django 3.1 이상에서 사용 가능

    def __str__(self):
        return self.SIDO_SGG

# # 위원회
# class Committee(models.Model):
#     age = models.IntegerField()Add commentMore actions
#     committees = models.CharField(max_length=100)  # 위원회 이름
#     def __str__(self):
#         return self.name

# 의원 
class Member(models.Model):
    age = models.IntegerField()
    name = models.CharField(max_length=100)  # 의원명
    party = models.ForeignKey(Party, on_delete=models.CASCADE)  # 정당
    district = models.ForeignKey(District, on_delete=models.CASCADE)  # 지역구
    member_id = models.CharField(max_length=50)
    gender = models.CharField(max_length=10)  # 성별

    # class Meta:
    #     managed = False
    #     db_table = 'geovote_member'

    def __str__(self):
        district_name = self.district.name if self.district else "비례대표"
        return f'{self.name} ({self.party.name}, {self.district.name})'

        
# 표결
class Vote(models.Model):
    age = models.ForeignKey(Age, on_delete=models.CASCADE) # 대수
    member = models.ForeignKey(Member, on_delete=models.CASCADE)  # 의원
    bill = models.ForeignKey('billview.Bill', on_delete=models.CASCADE)  # 의안 id
    result = models.CharField(max_length=10)  # 찬성/반대/기권 등
    date = models.DateField() # 의결 날짜
    def __str__(self):
        return f'{self.member.name} voted {self.vote_result} on {self.bill.name}'