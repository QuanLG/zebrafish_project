"""
简单的集成测试脚本，用于验证分析结果保存功能
"""
import os,sys
import django
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 配置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from multi_stats.models import AnalysisResult
from multi_stats.utils import (
    generate_analysis_uuid,
    format_analysis_result,
    generate_summary_stats,
    save_analysis_to_db
)


def test_uuid_generation():
    """测试 UUID 生成"""
    print("=== 测试 UUID 生成 ===")
    uuid1 = generate_analysis_uuid()
    uuid2 = generate_analysis_uuid()
    print(f"UUID 1: {uuid1}")
    print(f"UUID 2: {uuid2}")
    print(f"两个 UUID 不同: {uuid1 != uuid2}")
    return uuid1


def test_json_formatting():
    """测试 JSON 格式化"""
    print("\n=== 测试 JSON 格式化 ===")
    config = {
        "group_column": "组别",
        "selected_fields": ["体重", "体长"],
        "selected_comparison_groups": ["对照组 vs 实验组"],
        "test_method": "T检验 (ttest_ind)",
        "chart_type": "柱状图"
    }
    stats = {
        "体重": {
            "对照组 vs 实验组": {
                "对照组": {"mean": 25.5, "sem": 1.2, "n": 10},
                "实验组": {"mean": 30.2, "sem": 1.5, "n": 10}
            }
        },
        "体长": {
            "对照组 vs 实验组": {
                "对照组": {"mean": 10.5, "sem": 0.5, "n": 10},
                "实验组": {"mean": 12.3, "sem": 0.6, "n": 10}
            }
        }
    }
    formatted = format_analysis_result(config, stats)
    print(f"格式化结果结构: {list(formatted.keys())}")
    print(f"配置字段数: {len(formatted['config'])}")
    print(f"结果字段数: {len(formatted['results'])}")
    return config, stats


def test_summary_generation():
    """测试统计摘要生成"""
    print("\n=== 测试统计摘要生成 ===")
    stats = {
        "体重": {
            "A vs B": {},
            "A vs C": {}
        },
        "体长": {
            "A vs B": {}
        }
    }
    summary = generate_summary_stats(stats)
    print(f"统计摘要: {summary}")
    assert summary["total_fields"] == 2
    assert summary["field_names"] == ["体重", "体长"]
    assert summary["comparison_counts"]["体重"] == 2


def test_db_operations():
    """测试数据库操作"""
    print("\n=== 测试数据库操作 ===")
    
    # 测试数据
    config = {
        "group_column": "组别",
        "selected_fields": ["体重", "体长"],
        "selected_comparison_groups": ["对照组 vs 实验组"],
        "test_method": "T检验 (ttest_ind)",
        "chart_type": "柱状图"
    }
    stats = {
        "体重": {
            "对照组 vs 实验组": {
                "对照组": {"mean": 25.5, "sem": 1.2, "n": 10},
                "实验组": {"mean": 30.2, "sem": 1.5, "n": 10}
            }
        }
    }
    
    # 保存到数据库
    analysis_result = save_analysis_to_db(config, stats)
    print(f"保存成功，UUID: {analysis_result.id}")
    print(f"状态: {analysis_result.status}")
    print(f"创建时间: {analysis_result.created_at}")
    
    # 从数据库读取
    retrieved = AnalysisResult.objects.get(id=analysis_result.id)
    print(f"读取成功，状态一致: {retrieved.status == 'completed'}")
    print(f"配置正确: {retrieved.analysis_config['group_column'] == '组别'}")
    
    return retrieved


if __name__ == "__main__":
    print("开始集成测试...\n")
    
    try:
        # 运行所有测试
        test_uuid_generation()
        test_json_formatting()
        test_summary_generation()
        test_db_operations()
        
        print("\n✅ 所有测试通过！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
