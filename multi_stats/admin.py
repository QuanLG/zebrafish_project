from django.contrib import admin
from django.utils.html import format_html
from .models import AnalysisResult


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'status', 'summary_display']
    list_filter = ['status', 'created_at']
    search_fields = ['id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'analysis_config', 'result_data', 'summary_stats', 'error_message']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def summary_display(self, obj):
        """显示统计摘要"""
        summary = obj.summary_stats
        if summary:
            return format_html(
                '字段数: {} | 比较组: {}',
                summary.get('total_fields', 0),
                ', '.join(summary.get('field_names', []))
            )
        return '-'
    summary_display.short_description = '分析摘要'
    
    def has_add_permission(self, request):
        """不允许手动添加分析结果"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """不允许修改分析结果"""
        return False
