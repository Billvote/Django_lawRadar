from django.db import models

# 정당
class Party(models.Model):
    # age = models.IntegerField()
    party = models.CharField(max_length=100, unique=True)  # 정당 이름
    def __str__(self):
        return self.party

# 지역구
class District(models.Model):
    # age = models.IntegerField()
    SGG_Code = models.CharField(max_length=100, unique=True) # 선관위 선거구 코드
    SIDO_SGG = models.CharField(max_length=100, unique=True) # 광역시도+선거구
    SIDO = models.CharField(max_length=100) # 광역시도 이름
    SGG = models.CharField(max_length=100) # 선거구
    boundary = models.JSONField()  # 지역구의 경계(공간 데이터)
    def __str__(self):
        return self.SIDO_SGG

# 위원회
# class Committee(models.Model):
#     age = models.IntegerField()
#     committees = models.CharField(max_length=100)  # 위원회 이름
#     def __str__(self):
#         return self.name

# 의안
class Bill(models.Model):
    age = models.IntegerField()
    title = models.CharField(max_length=200)  # 의안명
    bill_id = models.CharField(max_length=100, unique=True) # 의안 id
    bill_number = models.CharField(max_length=50)  # 의안 번호
    content = models.TextField(blank=True, null=True)  # 주요 내용
    def __str__(self):
        return f'{self.name} ({self.bill_number})'

# 의원
class Member(models.Model):
    age = models.IntegerField()
    name = models.CharField(max_length=100)  # 의원명
    party = models.ForeignKey(Party, on_delete=models.CASCADE)  # 정당
    district = models.ForeignKey(District, on_delete=models.CASCADE)  # 지역구
    member_id = models.CharField(max_length=50)
    gender = models.CharField(max_length=10)  # 성별
    # committees = models.ManyToManyField('Committee')  # 소속 위원회
    def __str__(self):
        return f'{self.name} ({self.party.name}, {self.district.name})'
        
# 표결
class Vote(models.Model):
    age = models.IntegerField() # 대수
    member = models.ForeignKey(Member, on_delete=models.CASCADE)  # 의원
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)  # 의안
    vote_result = models.CharField(max_length=10)  # 찬성/반대/기권 등
    def __str__(self):
        return f'{self.member.name} voted {self.vote_result} on {self.bill.name}'
