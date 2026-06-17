import uuid
from django.db import models
from django.utils import timezone


class AnalysisResult(models.Model):
    """
    分析结果模型，用于存储每次分析的唯一标识和结果数据
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    # 分析配置信息
    analysis_config = models.JSONField(verbose_name='分析配置', default=dict)
    
    # 分析结果数据
    result_data = models.JSONField(verbose_name='分析结果', default=dict)
    
    # 统计摘要信息
    summary_stats = models.JSONField(verbose_name='统计摘要', default=dict)
    
    # 状态字段
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '待处理'),
            ('processing', '处理中'),
            ('completed', '已完成'),
            ('failed', '失败')
        ],
        default='pending',
        verbose_name='处理状态'
    )
    
    # 错误信息
    error_message = models.TextField(blank=True, null=True, verbose_name='错误信息')
    
    class Meta:
        db_table = 'analysis_results'
        verbose_name = '分析结果'
        verbose_name_plural = '分析结果'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"分析结果 {self.id} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

