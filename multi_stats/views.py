import os
import re
import json
import zipfile
import tempfile
import base64
import logging
from io import BytesIO
from datetime import datetime
from itertools import combinations

from .utils import save_analysis_to_db, generate_analysis_uuid

logger = logging.getLogger(__name__)

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import colorsys
import seaborn as sns
from scipy import stats
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

SEABORN_PALETTES = {
    'default_color': sns.color_palette(['#FF0000', '#0000FF', '#AD07E3', '#008000', '#CE0665', '#0F99B2', '#C5944E', '#FF6000']),
    "gray_black": sns.color_palette(["#333333", "#666666", "#999999", "#CCCCCC"]),
    "Greys": sns.color_palette("Greys"),
    "Greys_r": sns.color_palette("Greys_r"),
    "Set1": sns.color_palette("Set1"),
    "Set2": sns.color_palette("Set2"),
    "Set3": sns.color_palette("Set3"),
    "deep": sns.color_palette("deep"),
    "muted": sns.color_palette("muted"),
    "pastel": sns.color_palette("pastel"),
    "bright": sns.color_palette("bright"),
    "colorblind": sns.color_palette("colorblind"),
    "tab10": sns.color_palette("tab10"),
    "Paired": sns.color_palette("Paired"),
    "husl": sns.color_palette("husl"),
    "Spectral": sns.color_palette("Spectral"),
    "coolwarm": sns.color_palette("coolwarm"),
    "RdBu": sns.color_palette("RdBu"),
    "viridis": sns.color_palette("viridis"),
    "plasma": sns.color_palette("plasma"),
}

# plt.rcParams['font.sans-serif'] = ['RomanSong', 'SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
# plt.rcParams['axes.unicode_minus'] = False


import matplotlib.font_manager as fm

font_path = 'C:/Windows/Fonts/simhei.ttf'
try:
    CHINESE_FONT = fm.FontProperties(fname=font_path)
except:
    CHINESE_FONT = fm.FontProperties(family='SimHei')

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'STSong', 'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False


def calculate_significance(p_value):
    """根据 p 值返回统计显著性标记。

    p < 0.001 返回 '***'，p < 0.01 返回 '**'，
    p < 0.05 返回 '*'，否则返回 'ns'。
    """
    if p_value < 0.001:
        return "***"
    elif p_value < 0.01:
        return "**"
    elif p_value < 0.05:
        return "*"
    else:
        return "ns"


def perform_stat_test(data_list, test_method):
    """对两组数据执行统计检验，返回 p 值。

    支持独立样本 t 检验 ('T检验 (ttest_ind)') 和
    Mann-Whitney U 检验 ('秩和检验 (mannwhitneyu)')。
    数据不满足条件时返回 1.0。
    """
    if test_method == "T检验 (ttest_ind)":
        if len(data_list) != 2:
            return 1.0
        data1, data2 = data_list
        if len(data1) < 2 or len(data2) < 2:
            return 1.0
        _, p_value = stats.ttest_ind(data1, data2)
        return p_value
    elif test_method == "秩和检验 (mannwhitneyu)":
        if len(data_list) != 2:
            return 1.0
        data1, data2 = data_list
        if len(data1) < 1 or len(data2) < 1:
            return 1.0
        try:
            _, p_value = stats.mannwhitneyu(data1, data2, alternative='two-sided')
            return p_value
        except:
            return 1.0
    return 1.0


def lighten_color(color, amount=0.3):
    """将颜色变亮，用于柱状图填充色等场景。

    amount 控制变亮程度（0-1，默认 0.3）。
    返回变亮后的 RGB 元组。
    """
    c = mcolors.to_rgb(color)
    h, l, s = colorsys.rgb_to_hls(*c)
    l = min(1, l + amount)
    return colorsys.hls_to_rgb(h, l, s)


def parse_comparison_group(group_str):
    """解析 "A vs B" 格式的比较组字符串，返回 [A, B] 列表。"""
    return group_str.split(" vs ")


def generate_comparison_groups(unique_values):
    """根据唯一分组值生成所有两两比较组合，如 ['A vs B', 'A vs C']。"""
    if len(unique_values) < 2:
        return []
    return [f"{v1} vs {v2}" for v1, v2 in combinations(sorted(unique_values), 2)]


def sanitize_filename(filename):
    """清理文件名中的非法字符，替换为下划线。"""
    return re.sub(r'[/\\:*?"<>|（），,]', '_', filename)


def draw_single_subplot(ax, selected_field, df, group_column, selected_comparison_groups,
                        test_method, colors, chart_type, line_width, low_alpha, point_size,
                        group_spacing, bar_width, show_title, show_legend, show_grid, is_single=False):
    """在给定 axes 上绘制单个统计子图。

    支持柱状图、柱状图叠加点图、散点图三种类型，自动绘制
    误差线和统计显著性标记。

    Returns:
        dict: 包含 field, group_means, group_se, group_labels,
              p_values, unique_groups 的统计信息字典。
    """
    unique_groups_in_comparison = []
    for group_str in selected_comparison_groups:
        g1, g2 = parse_comparison_group(group_str)
        if g1 not in unique_groups_in_comparison:
            unique_groups_in_comparison.append(g1)
        if g2 not in unique_groups_in_comparison:
            unique_groups_in_comparison.append(g2)
    unique_groups_in_comparison = sorted(unique_groups_in_comparison)

    group_means = []
    group_stds = []
    group_se = []
    group_n = []
    group_labels = []
    group_maxs = []

    for group in unique_groups_in_comparison:
        group_data = df[df[group_column] == group][selected_field].values
        group_means.append(np.mean(group_data) if len(group_data) > 0 else 0)
        group_stds.append(np.std(group_data, ddof=1) if len(group_data) > 0 else 0)
        group_maxs.append(max(group_data) if len(group_data) > 0 else 0)
        se = np.std(group_data, ddof=1) / np.sqrt(len(group_data)) if len(group_data) > 0 else 0
        group_se.append(se)
        group_n.append(len(group_data))
        group_labels.append(group)

    p_values = []
    for group_str in selected_comparison_groups:
        g1, g2 = parse_comparison_group(group_str)
        data1 = df[df[group_column] == g1][selected_field].values
        data2 = df[df[group_column] == g2][selected_field].values
        p = perform_stat_test([data1, data2], test_method)
        p_values.append(p)

    _colors = colors[:len(unique_groups_in_comparison)]
    face_colors = [lighten_color(c, 0) for c in _colors]
    face_colors_rgba = [(*color, low_alpha) for color in face_colors]
    face_colors_hex = [mcolors.to_hex(c, keep_alpha=True) for c in face_colors_rgba]

    if "柱状图" in chart_type:
        x = np.arange(len(unique_groups_in_comparison)) * group_spacing

        bars = ax.bar(x, group_means, bar_width,
                      color=face_colors_hex,
                      edgecolor=_colors,
                      linewidth=line_width,
                      label=group_labels)

        for i, (xi, yi, ei) in enumerate(zip(x, group_means, group_se)):
            ax.plot([xi, xi], [yi, yi + ei], color=_colors[i], linewidth=line_width)
            ax.plot([xi - 0.1, xi + 0.1], [yi + ei, yi + ei], color=_colors[i], linewidth=line_width)

        ax.set_xticks(x)
        ax.set_xticklabels(group_labels, rotation=30, ha='center')

        if len(p_values) > 0 and len(selected_comparison_groups) > 0:
            if '点图' not in chart_type:
                max_height = max(group_means) + max(group_se) * 1.1 if group_means else 1
            else:
                max_height = max(group_maxs) * 1.1 if group_maxs else 1

            bar_height = max_height * 0.98
            current_height = max_height * 0.07

            for i, p in enumerate(p_values):
                if i < len(selected_comparison_groups):
                    sig = calculate_significance(p)
                    g1, g2 = parse_comparison_group(selected_comparison_groups[i])
                    if g1 in group_labels and g2 in group_labels:
                        idx1 = group_labels.index(g1)
                        idx2 = group_labels.index(g2)
                        x1 = x[idx1]
                        x2 = x[idx2]

                        y_line = current_height
                        ax.plot([x1, x1], [y_line + bar_height * 0.98, y_line + bar_height],
                                color='black', linewidth=1.5)
                        ax.plot([x2, x2], [y_line + bar_height * 0.98, y_line + bar_height],
                                color='black', linewidth=1.5)
                        ax.plot([x1, x2], [y_line + bar_height, y_line + bar_height],
                                color='black', linewidth=1)

                        ax.text((x1 + x2) / 2, y_line + bar_height * 1.001, sig,
                                ha='center', va='bottom', fontsize=12, fontweight='bold')

                        current_height += bar_height * 0.1

            ax.set_ylim(0, (max_height + current_height) * 1.01)

        if '点图' in chart_type:
            for i, (group, mean_val, std_val) in enumerate(zip(group_labels, group_means, group_stds)):
                group_data = df[df[group_column] == group][selected_field].values
                x_jitter = np.random.normal(x[i], 0.03 * group_spacing, len(group_data))
                ax.scatter(x_jitter, group_data,
                          color=face_colors_hex[i],
                          s=point_size,
                          alpha=1,
                          edgecolors=face_colors_hex[i])

    elif chart_type == "散点图":
        x = np.arange(len(unique_groups_in_comparison)) * group_spacing
        all_data_values = []

        for i, (group, mean_val, std_val) in enumerate(zip(group_labels, group_means, group_stds)):
            group_data = df[df[group_column] == group][selected_field].values
            x_jitter = np.random.normal(x[i], 0.05 * group_spacing, len(group_data))
            ax.scatter(x_jitter, group_data,
                      color=colors[i % len(colors)],
                      alpha=0.6, s=50, label=group, edgecolors='white')
            ax.errorbar(x[i], mean_val, yerr=std_val, fmt='_',
                       color='black', markersize=20, capsize=5, linewidth=2)
            all_data_values.extend(group_data)

        ax.set_xticks(x)
        ax.set_xticklabels(group_labels, rotation=30, ha='center')

        if all_data_values:
            ax.set_ylim(0, max(all_data_values) * 1.3)

    if show_title:
        ax.set_title(selected_field, fontsize=16, fontweight='bold', pad=10)

    ax.set_ylabel(selected_field, fontsize=14)

    if show_legend:
        ax.legend(loc='upper right', framealpha=0.9, fontsize=8)

    if show_grid:
        ax.yaxis.grid(True, alpha=0.3, linestyle='-')
        ax.xaxis.grid(False)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    return {
        'field': selected_field,
        'group_means': group_means,
        'group_se': group_se,
        'group_labels': group_labels,
        'p_values': p_values,
        'unique_groups': unique_groups_in_comparison
    }


def index(request):
    """多指标统计分析工具首页视图。

    清空 session 旧数据，渲染首页并传递调色板和图表类型。
    """
    # 清除分析数据但保留 session 用于使用次数追踪
    for key in ('df_data', 'numeric_columns', 'all_columns', 'all_stats', 'subplot_filenames'):
        request.session.pop(key, None)
    return render(request, 'multi_stats/index.html', {
        'palettes': list(SEABORN_PALETTES.keys()),
        'chart_types': ['柱状图', '柱状图叠加点图', '散点图'],
        'is_authenticated': request.user.is_authenticated,
        'has_used': request.session.get('multi_stats_used', False),
    })



def _check_usage_limit(request):
    """检查匿名用户是否超出使用次数限制。

    Returns:
        tuple: (is_allowed, error_message_or_None)
    """
    if request.user.is_authenticated:
        return True, None
    if request.session.get('multi_stats_used'):
        return False, '您已达到免费使用次数限制（1次），请登录后继续使用'
    return True, None


@csrf_exempt
def upload_file(request):
    """Excel 文件上传接口。

    读取上传的 .xlsx 文件，识别数值型字段，
    将数据保存到 session 供后续分析使用。

    Returns:
        JSON: success, columns, numeric_columns, shape, original_df
              或 error 信息。
    """
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            df = pd.read_excel(excel_file)
            df['use'] = True
            numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
            all_columns = df.columns.tolist()

            original_df = df.drop(columns=['use']).to_dict(orient='records')

            request.session['df_data'] = df.to_json()
            request.session['numeric_columns'] = numeric_columns
            request.session['all_columns'] = all_columns

            return JsonResponse({
                'success': True,
                'columns': all_columns,
                'numeric_columns': numeric_columns,
                'shape': {'rows': len(df), 'cols': len(df.columns)},
                'original_df': original_df
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'No file provided'})


@csrf_exempt
def get_sample_data(request):
    """获取样本数据接口（支持分页）。

    从 session 读取上传数据，按 page 和 page_size 分页返回。

    Returns:
        JSON: success, columns, data, use_flags, total_pages,
              total_items, current_page, page_size 或 error 信息。
    """
    if request.method == 'POST':
        try:
            df_json = request.session.get('df_data')
            if not df_json:
                return JsonResponse({'success': False, 'error': 'No data in session'})

            df = pd.read_json(df_json)
            df_display = df.drop(columns=['use']).to_dict(orient='records')
            columns = df.drop(columns=['use']).columns.tolist()
            use_flags = df['use'].astype(int).tolist()

            # 分页处理
            data = json.loads(request.body) if request.body else {}
            page = int(data.get('page', 1))
            page_size = int(data.get('page_size', 10))
            
            total_items = len(df_display)
            total_pages = (total_items + page_size - 1) // page_size
            
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            paginated_data = df_display[start_idx:end_idx]
            paginated_use_flags = use_flags[start_idx:end_idx]

            return JsonResponse({
                'success': True,
                'columns': columns,
                'data': paginated_data,
                'use_flags': paginated_use_flags,
                'total_pages': total_pages,
                'total_items': total_items,
                'current_page': page,
                'page_size': page_size
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def get_comparison_groups(request):
    """获取分组比较组合接口。

    根据 group_column 获取所有唯一分组值，
    生成所有两两比较组合。

    Returns:
        JSON: success, unique_groups, comparison_groups 或 error 信息。
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            group_column = data.get('group_column')
            df_json = request.session.get('df_data')
            if not df_json:
                return JsonResponse({'success': False, 'error': 'No data in session'})

            df = pd.read_json(df_json)
            df[group_column] = [str(g) for g in list(df[group_column])]
            unique_groups = df[group_column].dropna().unique().tolist()
            unique_groups = [str(g) for g in unique_groups if g != '']
            unique_groups.sort()

            comparison_groups = generate_comparison_groups(unique_groups)
            return JsonResponse({
                'success': True,
                'unique_groups': unique_groups,
                'comparison_groups': comparison_groups
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def update_sample_filter(request):
    """更新样本筛选状态接口。

    根据 use_flags 更新样本行使用状态，
    保存到 session 并返回有效数据行数。

    Returns:
        JSON: success, valid_count 或 error 信息。
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            df_json = request.session.get('df_data')
            if not df_json:
                return JsonResponse({'success': False, 'error': 'No data in session'})

            df = pd.read_json(df_json)
            use_flags = data.get('use_flags', {})

            for idx, use_value in use_flags.items():
                df.loc[int(idx), 'use'] = bool(use_value)

            request.session['df_data'] = df.to_json()

            valid_count = df['use'].sum()
            return JsonResponse({'success': True, 'valid_count': int(valid_count)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def generate_chart(request):
    """生成多指标统计图表接口。

    从 session 获取数据，按 config 配置生成组合图和
    各字段单独图表，计算统计数据并保存分析结果到数据库。

    config 关键字段: group_column, selected_fields,
    selected_comparison_groups, test_method, chart_type,
    selected_palette 等。

    Returns:
        JSON: success, main_chart (base64), individual_charts (base64 字典),
              all_stats, field_count, analysis_uuid 或 error 信息。
    """
    if request.method == 'POST':
        try:
            # 检查使用次数限制
            allowed, limit_error = _check_usage_limit(request)
            if not allowed:
                return JsonResponse({'success': False, 'error': limit_error}, status=403)

            data = json.loads(request.body)
            df_json = request.session.get('df_data')
            if not df_json:
                return JsonResponse({'success': False, 'error': 'No data in session'})

            df = pd.read_json(df_json)
            df_filtered = df[df['use'] == True].reset_index(drop=True)

            # 检查过滤后的数据是否为空
            if len(df_filtered) == 0:
                return JsonResponse({'success': False, 'error': '没有有效的数据行，请检查样本筛选设置'})

            config = data.get('config', {})
            group_column = config.get('group_column')
            selected_fields = config.get('selected_fields', [])
            selected_comparison_groups = config.get('selected_comparison_groups', [])
            test_method = config.get('test_method', 'T检验 (ttest_ind)')
            chart_type = config.get('chart_type', '柱状图')
            palette_name = config.get('selected_palette', 'default_color')
            fig_width = config.get('fig_width', 5)
            fig_height = config.get('fig_height', 4)
            group_spacing = config.get('group_spacing', 1.0)
            bar_width = config.get('bar_width', 0.6)
            line_width = config.get('line_width', 2.5)
            low_alpha = config.get('low_alpha', 0.4)
            point_size = config.get('point_size', 10)
            show_title = config.get('show_title', True)
            show_legend = config.get('show_legend', True)
            show_grid = config.get('show_grid', True)

            # 验证必要参数
            if not group_column:
                return JsonResponse({'success': False, 'error': '未选择分组字段'})
            if not selected_fields:
                return JsonResponse({'success': False, 'error': '未选择数值字段'})
            if not selected_comparison_groups:
                return JsonResponse({'success': False, 'error': '未选择比较组'})

            colors = SEABORN_PALETTES.get(palette_name, SEABORN_PALETTES['default_color'])

            n_fields = len(selected_fields)
            n_cols = 3
            n_rows = (n_fields + n_cols - 1) // n_cols

            fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_width * n_cols, fig_height * n_rows))
            fig.subplots_adjust(hspace=0.3, wspace=0.3)

            if n_fields == 1:
                axes = np.array([axes])
            elif n_rows == 1:
                axes = axes.reshape(1, -1)

            axes = axes.flatten()

            all_stats = {}
            subplot_figs = {}

            for idx, selected_field in enumerate(selected_fields):
                ax = axes[idx]
                all_stats[selected_field] = {}

                for group_str in selected_comparison_groups:
                    group1, group2 = parse_comparison_group(group_str)
                    group1_data = df_filtered[df_filtered[group_column] == group1][selected_field].values
                    group2_data = df_filtered[df_filtered[group_column] == group2][selected_field].values

                    g1_mean = np.mean(group1_data) if len(group1_data) > 0 else 0
                    g2_mean = np.mean(group2_data) if len(group2_data) > 0 else 0

                    all_stats[selected_field][group_str] = {
                        group1: {'mean': float(g1_mean),
                                'sem': float(np.std(group1_data, ddof=1) / np.sqrt(len(group1_data))) if len(group1_data) > 0 else 0,
                                'n': len(group1_data)},
                        group2: {'mean': float(g2_mean),
                                'sem': float(np.std(group2_data, ddof=1) / np.sqrt(len(group2_data))) if len(group2_data) > 0 else 0,
                                'n': len(group2_data)}
                    }

                draw_single_subplot(
                    ax, selected_field, df_filtered, group_column, selected_comparison_groups,
                    test_method, colors, chart_type, line_width, low_alpha, point_size,
                    group_spacing, bar_width, show_title, show_legend and idx == 0, show_grid
                )

                fig_single, ax_single = plt.subplots(figsize=(fig_width, fig_height))
                draw_single_subplot(
                    ax_single, selected_field, df_filtered, group_column, selected_comparison_groups,
                    test_method, colors, chart_type, line_width, low_alpha, point_size,
                    group_spacing, bar_width, show_title, show_legend, show_grid,
                    is_single=True
                )
                plt.tight_layout()
                subplot_figs[selected_field] = fig_single

            for idx in range(n_fields, len(axes)):
                axes[idx].set_visible(False)

            plt.tight_layout()

            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            main_chart_data = base64.b64encode(buf.read()).decode()
            buf.close()

            individual_charts = {}
            for field_name, fig_single in subplot_figs.items():
                buf_single = BytesIO()
                fig_single.savefig(buf_single, format='png', dpi=150, bbox_inches='tight', facecolor='white')
                buf_single.seek(0)
                individual_charts[field_name] = base64.b64encode(buf_single.read()).decode()
                buf_single.close()

            for fig_single in subplot_figs.values():
                plt.close(fig_single)
            plt.close(fig)

            request.session['all_stats'] = json.dumps(all_stats)
            request.session['subplot_filenames'] = list(subplot_figs.keys())

            # 保存分析结果到数据库
            analysis_uuid = generate_analysis_uuid()
            try:
                analysis_result = save_analysis_to_db(config, all_stats, analysis_uuid)
                logger.info(f"分析结果已保存，UUID: {analysis_uuid}")
            except Exception as e:
                logger.error(f"保存分析结果失败: {str(e)}")
                # 继续执行，不影响用户界面

            # 标记匿名用户已使用
            if not request.user.is_authenticated:
                request.session['multi_stats_used'] = True

            return JsonResponse({
                'success': True,
                'main_chart': main_chart_data,
                'individual_charts': individual_charts,
                'all_stats': all_stats,
                'field_count': n_fields,
                'analysis_uuid': analysis_uuid
            })
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def download_charts(request):
    """下载图表接口。

    按配置重新生成图表，保存到临时目录后打包为 ZIP，
    返回 ZIP 文件的 base64 编码。

    Returns:
        JSON: success, filename, data (ZIP base64) 或 error 信息。
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            download_format = data.get('format', 'png').lower()
            dpi_value = data.get('dpi', 300)

            df_json = request.session.get('df_data')
            if not df_json:
                return JsonResponse({'success': False, 'error': 'No data in session'})

            df = pd.read_json(df_json)
            df_filtered = df[df['use'] == True].reset_index(drop=True)

            config = data.get('config', {})
            group_column = config.get('group_column')
            selected_fields = config.get('selected_fields', [])
            selected_comparison_groups = config.get('selected_comparison_groups', [])
            test_method = config.get('test_method', 'T检验 (ttest_ind)')
            chart_type = config.get('chart_type', '柱状图')
            palette_name = config.get('selected_palette', 'default_color')
            fig_width = config.get('fig_width', 5)
            fig_height = config.get('fig_height', 4)
            group_spacing = config.get('group_spacing', 1.0)
            bar_width = config.get('bar_width', 0.6)
            line_width = config.get('line_width', 2.5)
            low_alpha = config.get('low_alpha', 0.4)
            point_size = config.get('point_size', 10)
            show_title = config.get('show_title', True)
            show_legend = config.get('show_legend', True)
            show_grid = config.get('show_grid', True)

            colors = SEABORN_PALETTES.get(palette_name, SEABORN_PALETTES['default_color'])

            n_fields = len(selected_fields)
            n_cols = 3
            n_rows = (n_fields + n_cols - 1) // n_cols

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            with tempfile.TemporaryDirectory() as tmpdir:
                output_folder = os.path.join(tmpdir, f"多指标分析结果_{timestamp}")
                os.makedirs(output_folder)

                fig_total, axes_total = plt.subplots(n_rows, n_cols, figsize=(fig_width * n_cols, fig_height * n_rows))
                fig_total.subplots_adjust(hspace=0.3, wspace=0.3)

                if n_fields == 1:
                    axes_total = np.array([axes_total])
                elif n_rows == 1:
                    axes_total = axes_total.reshape(1, -1)
                axes_total = axes_total.flatten()

                for idx, selected_field in enumerate(selected_fields):
                    ax = axes_total[idx]
                    draw_single_subplot(
                        ax, selected_field, df_filtered, group_column, selected_comparison_groups,
                        test_method, colors, chart_type, line_width, low_alpha, point_size,
                        group_spacing, bar_width, show_title, show_legend and idx == 0, show_grid
                    )

                    fig_single, ax_single = plt.subplots(figsize=(fig_width, fig_height))
                    draw_single_subplot(
                        ax_single, selected_field, df_filtered, group_column, selected_comparison_groups,
                        test_method, colors, chart_type, line_width, low_alpha, point_size,
                        group_spacing, bar_width, show_title, show_legend, show_grid, is_single=True
                    )
                    plt.tight_layout()

                    safe_name = sanitize_filename(selected_field)
                    subplot_path = os.path.join(output_folder, f"{idx + 1:02d}_{safe_name}.{download_format}")
                    fig_single.savefig(subplot_path, format=download_format, dpi=dpi_value, bbox_inches='tight', facecolor='white')
                    plt.close(fig_single)

                for idx in range(n_fields, len(axes_total)):
                    axes_total[idx].set_visible(False)

                plt.tight_layout()
                total_path = os.path.join(output_folder, f"00_总图_{chart_type}.{download_format}")
                fig_total.savefig(total_path, format=download_format, dpi=dpi_value, bbox_inches='tight', facecolor='white')
                plt.close(fig_total)

                zip_path = f"{output_folder}.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(output_folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zipf.write(file_path, os.path.relpath(file_path, output_folder))

                with open(zip_path, 'rb') as f:
                    zip_data = f.read()

                filename = f"多指标分析结果_{timestamp}.zip"
                # 将文件名和数据一起返回，避免响应头解析问题
                import base64
                zip_base64 = base64.b64encode(zip_data).decode('utf-8')
                return JsonResponse({
                    'success': True,
                    'filename': filename,
                    'data': zip_base64
                })

        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request'})
