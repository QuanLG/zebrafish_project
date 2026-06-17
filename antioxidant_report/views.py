import os
import io
import re
import json
import time
import zipfile
import tempfile
import base64
import shutil
from datetime import datetime
from io import BytesIO

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image
from scipy import stats

import django
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm

current_path = os.path.dirname(os.path.realpath(__file__))
try:
    from .oxidant_report_utils import (
        ZebraFishStatRunner,
        pretty_format,
        render_length,
        cal_sign_level,
        cal_sign_word,
        cal_sign_word_model,
        create_zip_from_folder,
        lighten_color,
        map_sign_level,
        merge_images,
        merge_zebrafish_images,
        p_reset,
        p_reset_dec,
    )
except ImportError as e:
    print(f"Warning: Could not import oxidant_report_utils: {e}")
    ZebraFishStatRunner = object

sns.set(font='SimHei', font_scale=1.3, style='ticks')


def index(request):
    """抗氧化报告首页视图。

    清除分析相关旧数据，但保留 antioxidant_report_used 标记用于使用次数追踪。
    """
    for key in ('extract_dir', 'folders', 'df_iod_data', 'group_info_data',
                'form_values', 'edited_df_type', 'edited_df_info',
                'zf_df_data', 'clean_df_data', 'exp_type',
                'con_txt', 'result_txt', 'merged_plot_data',
                'last_img_scale'):
        request.session.pop(key, None)
    return render(request, 'antioxidant_report/index.html', {
        'is_authenticated': request.user.is_authenticated,
        'has_used': request.session.get('antioxidant_report_used', False),
    })


def _check_usage_limit(request):
    """检查匿名用户是否超出使用次数限制。

    Returns:
        tuple: (is_allowed, error_message_or_None)
    """
    if request.user.is_authenticated:
        return True, None
    if request.session.get('antioxidant_report_used'):
        return False, '您已达到免费使用次数限制（1次），请登录后继续使用'
    return True, None

class BeautyZebraFishRunner(ZebraFishStatRunner):
    def make_conclusion(self, target='斑马鱼体内绿色荧光强度', proxy='ROS含量', effect_trend='减弱', no_effect_trend='增强',
                                     exp='斑马鱼氧化应激模型', con_pair=('显著降低斑马鱼体内ROS水平', '抗氧化')):
        # '与正常组相比，模型对照组中斑马鱼肝脏油红O染色加深（图1），且测得肝脏的相对脂肪含量为286.29±25.74%，与正常组（100.00±8.52%）相比极显著升高（p<0.001），说明酒精性脂肪肝斑马鱼模型构建成功（图2）。'
        model_str = '由图1和表4可知，与{}相比，模型对照组中{}{}，{}{}（{}），表明本次{}建立成功。'
        # 阳性对照组中斑马鱼肝脏油红O染色变浅，且测得肝脏的相对脂肪含量为203.83±14.14%，与模型对照组（286.29±25.74%）相比显著降低（p <0.01），说明本次斑马鱼体内脂肪代谢的实验有效。
        pos_str = '与{}相比，阳性对照组中{}{}，{}{}（{}），说明本次实验有效。'
        results_txt = ''
        ## 模型组结论, 当且仅当有模型组和空白组时提供
        if self.model is not None and self.neg_ctrl is not None:
            model_row = self.df[self.df['分组名'] == self.model[1]].iloc[0]
            d = map_sign_level(model_row.p)
            if model_row.p > 0.05:
                c = '无统计学差异变化'
            else:
                c = cal_sign_word_model(model_row.p)
            model_result = model_str.format(self.neg_ctrl[1], target, no_effect_trend, proxy, c, d, exp)
            results_txt += model_result

        ## 阳性对照组结论, 当且仅当有阳性对照组时提供
        if self.pos_ctrl is not None:
            pos_row = self.df[self.df['分组名'] == self.pos_ctrl[1]].iloc[0]
            base_row = self.df[self.df['分组名'] == self.baseline[1]].iloc[0]
            d = map_sign_level(pos_row.p)
            if pos_row.p > 0.05:
                c1 = '无统计学差异变化'
                if pos_row['mean'] > base_row['mean']:
                    c = '升高且' + c1
                    effect_trend = '增强'
                else:
                    c = '降低但' + c1
            else:
                c = cal_sign_word(pos_row.p)
            pos_result = pos_str.format(self.baseline[1], target, effect_trend, proxy, c, d)
            results_txt += pos_result

        if self.exp_type == 'gradient':
            # 与模型组相比，{10^4 CFU/mL} {1004259干酪乳杆菌}组{斑马鱼体内绿色荧光强度}{减弱}，{ROS含量}{极显著降低}（{P < 0.001}）。
            cell = '与{}相比，{} {}组{}{}，{}{}（{}）。'
            useful, not_useful = [], []
            agg_results = ['由图1和表4可知，']
            for i, row in self.df[self.df['组别'] == '实验组'].iterrows():
                # todo 后续需要根据入参进行调整effect_trend
                effect_trend = '减弱'
                base_row = self.df[self.df['分组名'] == self.baseline[1]].iloc[0]
                d = map_sign_level(row.p)
                if row.p > 0.05:
                    c1 = '无统计学差异变化'
                    if row['mean'] > base_row['mean']:
                        c = '升高且' + c1
                        effect_trend = '增强'
                    else:
                        c = '降低但' + c1
                    not_useful.append(row['分组名'].replace('$', ''))
                else:
                    c = cal_sign_word(row.p)
                    if row['mean'] > base_row['mean']:    # p值显著，但是是相反趋势
                        c = c.replace('降低', '升高')
                        effect_trend = '增强'
                    useful.append(row['分组名'].replace('$', ''))
                post_fix = row['样品类型'].split('（')[1].replace('）', '')  # 单位
                pre_fix = row['样品类型'].split('（')[0]
                try:
                    agg_results.append(
                        cell.format(self.baseline[1],row['分组名'].replace('$', '') + ' ' + post_fix, pre_fix, target,
                                    effect_trend, proxy, c, d))
                except:
                    cell = '与{}相比, {}组{}{}，{}{}（{}）。'
                    agg_results.append(
                        cell.format(self.baseline[1], row['分组名'].replace('$', '') + ' ' + post_fix, pre_fix, target,
                                    effect_trend, proxy, c, d))

            con = ''
            n = 1
            if len(useful) > 0:
                # for c in useful:
                #     con += '    ' + '（{}）'.format(n) + '{}在浓度为{} {}时，能够{}，具有潜在{}的作用。\n'.format(row['样品类型'].split('（')[0],
                #                                                   c, post_fix, con_pair[0], con_pair[1])
                con += '    ' + '（{}）'.format(n) + '{}在浓度为{} {}时，能够{}，具有潜在{}的作用。\n'.format(row['样品类型'].split('（')[0],
                                                     '、'.join(useful), post_fix, con_pair[0],con_pair[1])
                n += 1
            if len(not_useful) > 0:
                con += '    ' + '（{}）'.format(n) + '{}在浓度为{} {}时，不能{}，不具有潜在的{}的作用。\n'.format(row['样品类型'].split('（')[0],
                                                    '、'.join(not_useful), post_fix, con_pair[0], con_pair[1])
                n += 1
                # 4个空格用于换行之后首行缩进
        else:
            # 与模型组相比，样品1组斑马鱼体内绿色荧光强度减弱，ROS含量极显著降低（P < 0.001）。
            cell = '与{}相比，{}组{}{}，{}{}（{}）。'
            useful, not_useful = [], []
            agg_results = ['由图1和表4可知，']
            for i, row in self.df[self.df['组别'] == '实验组'].iterrows():
                # todo 后续需要根据入参进行调整effect_trend
                effect_trend = '减弱'
                base_row = self.df[self.df['分组名'] == self.baseline[1]].iloc[0]
                d = map_sign_level(row.p)
                if row.p > 0.05:
                    c1 = '无统计学差异变化'
                    if row['mean'] > base_row['mean']:
                        c = '升高且' + c1
                        effect_trend = '增强'
                    else:
                        c = '降低但' + c1
                    not_useful.append(row['分组名'].replace('$', ''))
                else:
                    c = cal_sign_word(row.p)
                    if row['mean'] > base_row['mean']:    # p值显著，但是是相反趋势
                        c = c.replace('降低', '升高')
                        effect_trend = '增强'
                    useful.append(row['分组名'].replace('$', ''))
                agg_results.append(
                    cell.format(self.baseline[1], row['分组名'].replace('$', ''), target, effect_trend, proxy, c, d))
            con = ''
            n = 1
            ## 多个物质时候，分开写
            if len(useful) > 0:
                for c in useful:
                    con += '    ' + '（{}）'.format(n) + '{}能够{}，具有潜在的{}的作用。\n'.format(c, con_pair[0], con_pair[1])
                    n += 1
            if len(not_useful) > 0:
                for c in not_useful:
                    con += '    ' + '（{}）'.format(n) + '{}不能{}，不具有潜在的{}的作用。\n'.format(c, con_pair[0], con_pair[1])  # 4个空格用于换行之后首行缩进
                    n += 1
        results_txt += '\n'
        results_txt += '    ' + ''.join(agg_results)  # 4个空格用于换行之后首行缩进
        return results_txt, con


def doc_write(request):
    ## template test
    doc = DocxTemplate(current_path + "/oxidant_assets/抗氧化报告2026.docx")
    state = request.session
    # 从JSON字符串还原DataFrame
    clean_df_data = state.get('clean_df_data', '{}')
    clean_df = pd.read_json(clean_df_data) if clean_df_data else pd.DataFrame()
    # edited_df_type是list of dict，需转为DataFrame供模板iterrows()使用
    edited_df_type_raw = state.get('edited_df_type', [])
    edited_df_type = pd.DataFrame(edited_df_type_raw) if edited_df_type_raw else pd.DataFrame()
    context = {
            'exp_id': state['form_values']['exp_id'],
            'exp_client': state['form_values']['exp_client'],
            'exp_project': state['form_values']['exp_project'],
            'sample_name': state['form_values']['sample_name'],
            'sample_id': state['form_values']['sample_id'],
            'sample_status': state['form_values']['sample_status'],
            'sample_num': state['form_values']['sample_num'],
            'sample_date': state['form_values']['sample_date'],
            'test_date': state['form_values']['test_date'],
            'test_dose': state['form_values']['test_dose'],
            'edited_df_type': edited_df_type,
            'conclusion': state.get('con_txt', ''),
            'decision': state.get('result_txt', ''),
            'image1': InlineImage(doc, state['extract_dir'] + '/final_merged.png', width=Mm(160)),
            'df': clean_df,
            }
    doc.render(context, autoescape=True)
    output_path = os.path.join(state['extract_dir'], "oxidant_report.docx")
    doc.save(output_path)



@csrf_exempt
def upload_file(request):
    if request.method == 'POST' and request.FILES.get('zip_file'):
        zip_file = request.FILES['zip_file']
        try:
            temp_dir = settings.TEMP_DIR
            os.makedirs(temp_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extract_dir = os.path.join(temp_dir, f"extracted_{timestamp}")
            os.makedirs(extract_dir, exist_ok=True)

            zip_path = os.path.join(temp_dir, "uploaded.zip")
            with open(zip_path, 'wb') as f:
                for chunk in zip_file.chunks():
                    f.write(chunk)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    original_filename = file_info.filename
                    try:
                        if isinstance(original_filename, bytes):
                            decoded = original_filename.encode('cp437').decode('gbk')
                        else:
                            decoded = original_filename.encode('cp437').decode('gbk')
                    except:
                        decoded = original_filename

                    full_path = os.path.join(extract_dir, decoded)
                    if file_info.is_dir():
                        os.makedirs(full_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        with open(full_path, 'wb') as f:
                            f.write(zip_ref.read(file_info.filename))

            if os.listdir(extract_dir):
                extract_dir = os.path.join(extract_dir, os.listdir(extract_dir)[0])

            folders = [f for f in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, f))]

            request.session['extract_dir'] = extract_dir
            request.session['folders'] = folders

            df_iod = pd.read_excel(os.path.join(extract_dir, 'iod_results.xlsx'))

            group_info = pd.DataFrame()
            group_info['文件夹名'] = df_iod['分组'].unique().astype(str)

            group_to_sample_type = {}
            for i in group_info['文件夹名'].unique():
                if '正常' in i or 'bc' in i.lower() or 'control' in i.lower() or 'normal' in i.lower():
                    group_to_sample_type[i] = '正常对照组'
                elif '模型' in i:
                    group_to_sample_type[i] = '模型对照组'
                elif '阳性' in i:
                    group_to_sample_type[i] = '阳性对照组'
                else:
                    group_to_sample_type[i] = '实验组'

            group_info['分组名'] = group_info['文件夹名']
            group_info['组别'] = group_info['文件夹名'].map(group_to_sample_type)
            group_info['样品类型'] = group_info['文件夹名'].map(group_to_sample_type)

            order_lst = ['正常对照组', '模型对照组', '溶剂对照组', '阳性对照组', '实验组']
            group_info['组别'] = pd.Categorical(group_info['组别'], categories=order_lst, ordered=True)
            group_info = group_info.sort_values(by=['组别', '文件夹名'], ascending=[True, True]).reset_index(drop=True)

            # 只保留成功分析的数据，并选择需要的列
            df_iod = df_iod[df_iod['状态'] == '成功'].copy()
            df_iod['use'] = True
            df_iod['file'] = df_iod['视频']
            
            # 将df_iod的分组映射为组别
            df_iod['组别'] = df_iod['分组'].map(group_to_sample_type)
            # 按照group_info中的组别顺序排序
            df_iod['组别'] = pd.Categorical(df_iod['组别'], categories=order_lst, ordered=True)
            df_iod = df_iod.sort_values(by=['组别', '分组', 'file']).reset_index(drop=True)
            
            # 选择并重命名需要的列
            df_iod = df_iod[['分组', 'IOD值', 'use', 'file']].copy()

            request.session['df_iod_data'] = df_iod.to_json()
            request.session['group_info_data'] = group_info.to_json()

            sample_mode = '单物质梯度浓度实验' if (
                group_info[group_info['组别'] == '实验组']['样品类型'].unique().shape[0] == 1 and
                group_info[group_info['组别'] == '实验组']['分组名'].unique().shape[0] > 1
            ) else '非单物质梯度浓度实验'

            return JsonResponse({
                'success': True,
                'folders': folders,
                'group_info': group_info.to_dict('records'),
                'iod_results': df_iod.to_dict('records'),
                'sample_mode': sample_mode
            })
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'No file provided'})


@csrf_exempt
def save_config(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            form_values = data.get('form_values', {})
            edited_df_type = data.get('edited_df_type', [])
            edited_df_info = data.get('edited_df_info', [])

            request.session['form_values'] = form_values
            request.session['edited_df_type'] = edited_df_type
            request.session['edited_df_info'] = edited_df_info

            return JsonResponse({'success': True})
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def update_filter(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            use_flags = data.get('use_flags', {})

            df_iod_json = request.session.get('df_iod_data')
            if not df_iod_json:
                return JsonResponse({'success': False, 'error': 'No data in session'})
            
            df_iod = pd.read_json(df_iod_json)

            if df_iod.empty:
                return JsonResponse({'success': False, 'error': 'DataFrame is empty'})
            
            # 重置索引以确保从0开始的连续整数索引
            df_iod = df_iod.reset_index(drop=True)
            
            # 确保 use 字段是布尔类型
            df_iod['use'] = df_iod['use'].astype(bool)
            
            # 更新 use 字段
            updated_count = 0
            for idx, use_value in use_flags.items():
                idx_int = int(idx)
                if idx_int in df_iod.index:
                    df_iod.loc[idx_int, 'use'] = bool(use_value)
                    updated_count += 1
            
            # 保存更新后的数据
            request.session['df_iod_data'] = df_iod.to_json()
            
            # 返回更新后的数据用于前端同步
            iod_results_with_use = df_iod[['分组', 'IOD值', 'use', 'file']].to_dict('records')

            return JsonResponse({
                'success': True, 
                'message': f'Filter updated successfully ({updated_count} samples)',
                'iod_results': iod_results_with_use
            })
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def run_statistics(request):
    if request.method == 'POST':
        try:
            # 检查使用次数限制
            allowed, limit_error = _check_usage_limit(request)
            if not allowed:
                return JsonResponse({'success': False, 'error': limit_error}, status=403)

            data = json.loads(request.body)
            palette_name = data.get('palette', 'default_color')

            df_iod_json = request.session.get('df_iod_data')
            group_info_json = request.session.get('group_info_data')

            if not df_iod_json or not group_info_json:
                return JsonResponse({'success': False, 'error': 'No data in session'})

            df_iod = pd.read_json(df_iod_json)
            group_info = pd.read_json(group_info_json)
            
            # 重置索引以确保一致性
            df_iod = df_iod.reset_index(drop=True)
            
            # 确保 use 字段是布尔类型
            df_iod['use'] = df_iod['use'].astype(bool)

            filtered_df = df_iod[df_iod['use'] == True].copy()
            if filtered_df.empty:
                return JsonResponse({'success': False, 'error': 'No samples selected'})

            group_info['文件夹名'] = group_info['文件夹名'].astype(str)
            group_info['分组名'] = group_info['分组名'].astype(str)

            merged_df = group_info.merge(filtered_df, left_on='文件夹名', right_on='分组', how='left').drop(['分组'], axis=1)
            zf = BeautyZebraFishRunner(group_info, merged_df.copy(),'IOD值')
            zf.make_stats()

            SEABORN_PALETTES = {
                'default_color': sns.color_palette(['#FF0000', '#0000FF', '#AD07E3', '#008000', '#CE0665', '#0F99B2', '#C5944E', '#FF6000']),
                "Set1": sns.color_palette("Set1"),
                "Set2": sns.color_palette("Set2"),
                "tab10": sns.color_palette("tab10"),
                "Paired": sns.color_palette("Paired"),
                "husl": sns.color_palette("husl"),
            }
            colors = SEABORN_PALETTES.get(palette_name, SEABORN_PALETTES['default_color'])
            zf.make_plot('ROS相对含量（%）', slim=True, palette=colors)

            plot_path = os.path.join(request.session['extract_dir'], 'iod_diff_zebrafish.png')
            # zf.plot 是 numpy 数组，使用 PIL 保存
            from PIL import Image
            img = Image.fromarray(zf.plot)
            img.save(plot_path)
            # plt.close('all')
            

            plot_data = None
            with open(plot_path, 'rb') as f:
                plot_data = base64.b64encode(f.read()).decode()

            clean_raw = []
            for i, row in zf.df.iterrows():
                clean_raw.append({
                    '组别': row['组别'],
                    '分组名': row['分组名'],
                    '斑马鱼体内ROS含量(%)': '{:.3f}±{:.3f}'.format(row['mean'], row['sem']),
                    'P值': "{:.4f}".format(row.p) if not row.p == 1 else 1,
                    '样品类型': row['样品类型']
                })
            clean_df = pd.DataFrame(clean_raw)

            if '（' in clean_df[clean_df['组别'] == '实验组']['样品类型'].values[0]:
                post_fix = [v.split('（')[1].replace('）', '') for v in clean_df[clean_df['组别'] == '实验组']['样品类型'].values]
                pre_fix = [v.split('（')[0] + '组' for v in clean_df[clean_df['组别'] == '实验组']['样品类型'].values]
                new_name = list(zip(post_fix, pre_fix))
                new_name = [' '.join(n) for n in new_name]
                clean_df.loc[clean_df['组别'] == '实验组', '分组名'] = clean_df[clean_df['组别'] == '实验组']['分组名'] + ' ' + new_name
            clean_df = clean_df.drop(columns='样品类型')

            request.session['zf_df_data'] = zf.df.to_json()
            request.session['clean_df_data'] = clean_df.to_json()
            request.session['exp_type'] = zf.exp_type

            result, con = zf.make_conclusion()

            # 返回包含 use 状态的 iod_results 用于前端筛选
            iod_results_with_use = df_iod[['分组', 'IOD值', 'use', 'file']].to_dict('records')

            # 标记匿名用户已使用
            if not request.user.is_authenticated:
                request.session['antioxidant_report_used'] = True

            return JsonResponse({
                'success': True,
                'stats_df': clean_df.to_dict('records'),
                'plot': plot_data,
                'result': result,
                'con': con,
                'iod_results': iod_results_with_use
            })
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def update_conclusion(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            con_txt = data.get('con_txt', '')
            result_txt = data.get('result_txt', '')

            request.session['con_txt'] = con_txt
            request.session['result_txt'] = result_txt

            return JsonResponse({'success': True})
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

def last_img_scale(last_img_path):
    """
    最后一个图片添加刻度尺
    """
    try:
        # 打开图片
        img = Image.open(last_img_path)
        last_img = np.array(img)
        img_height, img_width = last_img.shape[:2]

        dpi = 96   # 原始dpi
        scale_length = 438   # 200um 等于438个像素点
        fig_width = img_width / dpi
        fig_height = img_height / dpi
        fig = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
        last_ax = fig.add_axes([0, 0, 1, 1])
        last_ax.axis('off')

        last_ax.imshow(last_img, extent=[0, img_width, img_height, 0])

        scale_x = img_width - scale_length - 100
        scale_y = img_height - 100
        last_ax.plot([scale_x, scale_x + scale_length], [scale_y, scale_y],
                    color='white', linewidth=5)
        last_ax.plot([scale_x-5, scale_x-5], [scale_y - 10, scale_y + 10],
                    color='white', linewidth=5)
        last_ax.plot([scale_x + scale_length+5, scale_x + scale_length+5],
                    [scale_y - 10, scale_y + 10], color='white', linewidth=5)
        last_ax.text(scale_x + scale_length/2, scale_y - 12, "200 μm",
                    color='white', fontsize=50, ha='center', va='bottom')

        plt.savefig(last_img_path, dpi=dpi)
        plt.close(fig)
        return None
        
    except Exception as e:
        print(f"打刻度尺时出错: {e}")
        return None


@csrf_exempt
def merge_and_generate(request):
    if request.method == 'POST':
        try:
            # 检查使用次数限制
            allowed, limit_error = _check_usage_limit(request)
            if not allowed:
                return JsonResponse({'success': False, 'error': limit_error}, status=403)

            from PIL import Image
            extract_dir = request.session.get('extract_dir')
            if not extract_dir:
                return JsonResponse({'success': False, 'error': 'No extraction directory'})

                #   # 按分组计算IOD值的平均值
            filtered_df = pd.read_json(request.session.get('df_iod_data', '{}'))
            if filtered_df is None:
                return JsonResponse({'success': False, 'error': 'No data available'})
            df_tmp = filtered_df[filtered_df.use].copy()
            group_means = df_tmp.groupby('分组')['IOD值'].mean()
            # 找出每个分组中IOD值与均值差值最小的视频
            df_mean = {}
            for group, mean_val in group_means.items():
                group_df = df_tmp[df_tmp['分组'] == group]      
                # 计算每个视频与均值的绝对差值
                group_df = group_df.copy()
                group_df['差值'] = abs(group_df['IOD值'] - mean_val)
                # 找出差值最小的视频
                min_idx = group_df['差值'].idxmin()
                df_mean[group] = group_df.loc[min_idx, 'file']
            
            request.session['last_img_scale'] = False
            groups = df_tmp['分组'].unique()
            images_array = {}
            last_group = groups[-1]
            
            # 调试信息
            print(f"Groups: {groups}")
            print(f"df_mean: {df_mean}")
            print(f"Extract dir: {extract_dir}")
            
            for group in groups:
                folder_path = os.path.join(extract_dir, group)
                print(f"Checking folder: {folder_path}")
                print(f"Folder exists: {os.path.exists(folder_path)}")
                
                if not os.path.exists(folder_path):
                    print(f"Folder not found: {folder_path}")
                    continue
                
                # 列出文件夹内容
                if os.path.exists(folder_path):
                    files_in_folder = os.listdir(folder_path)
                    print(f"Files in {folder_path}: {files_in_folder}")
                
                if group == last_group and not request.session['last_img_scale']:
                    # 等于最后一张图，读取进来打标尺，再输出
                    clip_path = os.path.join(folder_path,'iod_'+df_mean[group].replace('.mp4','_clip.tif'))  
                    print(f"Last group clip path: {clip_path}")
                    last_img_scale(clip_path)
                    request.session['last_img_scale']  = True

                clip_file = os.path.join(folder_path,'iod_'+df_mean[group].replace('.mp4','_clip.tif'))
                print(f"Looking for clip file: {clip_file}")
                print(f"Clip file exists: {os.path.exists(clip_file)}")
                    
                if os.path.exists(clip_file):
                    img = Image.open(clip_file)
                    images_array[group] = np.array(img)
                    print(f"Loaded image for group: {group}")
                else:
                    print(f"Clip file not found: {clip_file}")
        
            n_images = len(images_array)
            print(f"Total images loaded: {n_images}")
            if n_images == 0:
                return JsonResponse({'success': False, 'error': 'No images found'})

            group_options = request.session.get('folders', [])
            if group_options is None:
                group_options = []
            images_array_order = {k: images_array[k] for k in group_options if k in images_array}

            fig_plot = merge_zebrafish_images(n_images, images_array_order, group_options, extract_dir)
            
            if fig_plot is not None:
                fig_plot = merge_images(extract_dir)
            # 将 numpy 数组转换为 base64 图片
            if isinstance(fig_plot, np.ndarray):
                img = Image.fromarray(fig_plot)
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                img_base64 = base64.b64encode(buffer.getvalue()).decode()
            else:
                img_base64 = None

            request.session['merged_plot_data'] = img_base64

            try:
                doc_write(request)
            except Exception as e:
                import traceback
                return JsonResponse({'success': False, 'error': f'生成文档失败: {str(e)}', 'trace': traceback.format_exc()})

            return JsonResponse({'success': True, 'merged_image': img_base64})
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def download_results(request):
    if request.method == 'POST':
        try:
            extract_dir = request.session.get('extract_dir')
            if not extract_dir:
                return JsonResponse({'success': False, 'error': 'No extraction directory'})

            zip_bytes = create_zip_from_folder(extract_dir)

            response = HttpResponse(zip_bytes, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="oxidant_results.zip"'
            return response
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request'})
