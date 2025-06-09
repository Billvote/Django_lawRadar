from django.db import models
from geovote.models import Age, Party

# 대수별 통계
class AgeSummary(models.Model):
    age = models.OneToOneField(Age, on_delete=models.CASCADE)
    total_bills = models.PositiveIntegerField(default=0)          # 총 의안 수
    total_parties = models.PositiveIntegerField(default=0)        # 참여 정당 수

    male_count = models.PositiveIntegerField(default=0)           # 남성 의원 수
    female_count = models.PositiveIntegerField(default=0)         # 여성 의원 수
    female_percent = models.FloatField(default=0)                  # 여성 비율(%)

    updated_at = models.DateTimeField(auto_now=True)

# 정당별 표결 통계
class PartyVoteSummary(models.Model):
    age = models.ForeignKey(Age, on_delete=models.CASCADE)       # 국회 대수 (몇 대 국회인지)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)   # 정당

    member_count = models.PositiveIntegerField(default=0)        # 해당 정당 국회의원 수

    support_ratio = models.FloatField(default=0)                 # 찬성 비율(%)
    oppose_ratio = models.FloatField(default=0)                  # 반대 비율(%)
    abstain_ratio = models.FloatField(default=0)                 # 기권 비율(%)
    absent_ratio = models.FloatField(default=0)                   # 불참 비율(%)

    total_votes = models.PositiveIntegerField(default=0)         # 총 투표 수 (해당 대수에서 해당 정당 투표 횟수)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('age', 'party')
        verbose_name = '정당별 표결 요약'
        verbose_name_plural = '정당별 표결 요약들'

    def __str__(self):
        return f"{self.age} - {self.party.party} 표결 요약"

# 정당/클러스터별 투표 통계
class PartyClusterVoteSummary(models.Model):
    age = models.ForeignKey(Age, on_delete=models.CASCADE)               # 국회 대수
    cluster_num = models.IntegerField()                                  # 클러스터 번호
    cluster_keyword = models.TextField(blank=True, null=True)            # 클러스터 키워드 JSON 혹은 텍스트

    party = models.ForeignKey(Party, on_delete=models.CASCADE)           # 정당명

    support_count = models.PositiveIntegerField(default=0)               # 찬성 수
    oppose_count = models.PositiveIntegerField(default=0)                # 반대 수
    abstain_count = models.PositiveIntegerField(default=0)               # 기권 수
    absent_count = models.PositiveIntegerField(default=0)                # 불참 수

    total_votes = models.PositiveIntegerField(default=0)                 # 총 투표 수

    class Meta:
        unique_together = ('age', 'cluster_num', 'party')
        verbose_name = '정당-클러스터 투표 요약'
        verbose_name_plural = '정당-클러스터 투표 요약들'

    def __str__(self):
        return f"{self.age} - 클러스터 {self.cluster_num} - {self.party.party}"

# 클러스터 번호-키워드 매핑
class ClusterKeyword(models.Model):
    age = models.ForeignKey(Age, on_delete=models.CASCADE)
    cluster_num = models.IntegerField()
    keyword_json = models.TextField(blank=True, null=True)

    def get_keywords(self):
        import json
        try:
            return json.loads(self.keyword_json)
        except:
            return []

    def __str__(self):
        return f"{self.age} 클러스터 {self.cluster_num}"