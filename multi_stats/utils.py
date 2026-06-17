import uuid
import json
import logging
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from .models import AnalysisResult

logger = logging.getLogger(__name__)


def generate_analysis_uuid() -> str:
    """
    生成符合 RFC 4122 标准的 UUID v4
    """
    return str(uuid.uuid4())


def format_analysis_result(config: dict, stats: dict, summary: dict = None) -> dict:
    """
    将分析结果格式化为标准 JSON 结构
    """
    formatted_result = {
        "metadata": {
            "version": "1.0",
            "generated_at": None,
            "analysis_type": "multi_stats"
        },
        "config": {
            "group_column": config.get("group_column", ""),
            "selected_fields": config.get("selected_fields", []),
            "comparison_groups": config.get("selected_comparison_groups", []),
            "test_method": config.get("test_method", ""),
            "chart_type": config.get("chart_type", ""),
            "chart_config": {
                "palette": config.get("selected_palette", ""),
                "fig_width": config.get("fig_width", 5),
                "fig_height": config.get("fig_height", 4),
                "group_spacing": config.get("group_spacing", 1.0),
                "bar_width": config.get("bar_width", 0.6),
                "line_width": config.get("line_width", 2.5),
                "low_alpha": config.get("low_alpha", 0.4),
                "point_size": config.get("point_size", 10)
            }
        },
        "results": stats,
        "summary": summary or {}
    }
    return formatted_result


def generate_summary_stats(stats: dict) -> dict:
    """
    从分析结果中生成统计摘要
    """
    summary = {
        "total_fields": len(stats),
        "field_names": list(stats.keys()),
        "comparison_counts": {}
    }
    
    for field, comparisons in stats.items():
        summary["comparison_counts"][field] = len(comparisons)
    
    return summary


def save_analysis_to_db(config: dict, stats: dict, analysis_uuid: str = None) -> AnalysisResult:
    """
    将分析结果保存到数据库，包含事务处理和错误回滚机制
    
    Args:
        config: 分析配置
        stats: 统计结果
        analysis_uuid: 可选的分析 UUID，如果不传则自动生成
    
    Returns:
        AnalysisResult: 保存的分析结果对象
    
    Raises:
        Exception: 当保存失败时抛出异常
    """
    try:
        with transaction.atomic():
            # 生成或使用提供的 UUID
            if not analysis_uuid:
                analysis_uuid = generate_analysis_uuid()
            
            # 生成统计摘要
            summary = generate_summary_stats(stats)
            
            # 格式化结果数据
            formatted_result = format_analysis_result(config, stats, summary)
            
            # 创建或更新分析结果记录
            analysis_result = AnalysisResult.objects.create(
                id=uuid.UUID(analysis_uuid),
                analysis_config=config,
                result_data=formatted_result,
                summary_stats=summary,
                status='processing'
            )
            
            # 更新状态为已完成
            analysis_result.status = 'completed'
            analysis_result.save()
            
            logger.info(f"分析结果成功保存到数据库，UUID: {analysis_uuid}")
            return analysis_result
            
    except Exception as e:
        logger.error(f"保存分析结果到数据库失败: {str(e)}")
        
        # 尝试创建失败记录
        try:
            with transaction.atomic():
                AnalysisResult.objects.create(
                    id=uuid.UUID(analysis_uuid) if analysis_uuid else uuid.uuid4(),
                    analysis_config=config,
                    result_data={},
                    summary_stats={},
                    status='failed',
                    error_message=str(e)
                )
        except:
            pass
        
        raise


def get_analysis_result(analysis_uuid: str) -> AnalysisResult:
    """
    根据 UUID 获取分析结果
    
    Args:
        analysis_uuid: 分析 UUID
    
    Returns:
        AnalysisResult: 分析结果对象
    
    Raises:
        AnalysisResult.DoesNotExist: 当找不到对应的分析结果时
    """
    return AnalysisResult.objects.get(id=uuid.UUID(analysis_uuid))


def analysis_to_json(analysis_result: AnalysisResult) -> str:
    """
    将分析结果序列化为 JSON 字符串
    
    Args:
        analysis_result: AnalysisResult 对象
    
    Returns:
        str: JSON 字符串
    """
    data = {
        "uuid": str(analysis_result.id),
        "created_at": analysis_result.created_at.isoformat(),
        "updated_at": analysis_result.updated_at.isoformat(),
        "status": analysis_result.status,
        "config": analysis_result.analysis_config,
        "result": analysis_result.result_data,
        "summary": analysis_result.summary_stats
    }
    
    if analysis_result.error_message:
        data["error"] = analysis_result.error_message
    
    return json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
