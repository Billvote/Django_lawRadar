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

# 지역구 (정식 모델)
class District(models.Model):
    # id = models.CharField(max_length=10, primary_key=True)
    SGG_Code = models.CharField(max_length=100, unique=True)
    SIDO_SGG = models.CharField(max_length=100)
    SIDO = models.CharField(max_length=100)
    SGG = models.CharField(max_length=100)
    SIGUNGU = models.CharField(max_length=30, blank=True, null=True)


    def __str__(self):
        return self.SIDO_SGG

# 의원
class Member(models.Model):
    age = models.ForeignKey(Age, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    district = models.ForeignKey(District, on_delete=models.CASCADE, null=True, blank=True)
    member_id = models.CharField(max_length=50)
    gender = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.name} ({self.party}, {self.district or '비례대표'})"
        
# 표결
class Vote(models.Model):
    age = models.ForeignKey(Age, on_delete=models.CASCADE) # 대수
    member = models.ForeignKey(Member, on_delete=models.CASCADE)  # 의원
    bill = models.ForeignKey('billview.Bill', on_delete=models.CASCADE)  # 의안 id
    result = models.CharField(max_length=10)  # 찬성/반대/기권 등
    date = models.DateField() # 의결 날짜
    def __str__(self):
        return f'{self.member.name} voted {self.result} on {self.bill.title}'