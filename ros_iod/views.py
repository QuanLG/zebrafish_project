from django.shortcuts import render

# Create your views here.
import os
import re
import json
import zipfile
import tempfile
import base64
from io import BytesIO
from datetime import datetime
from itertools import combinations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import colorsys
import seaborn as sns
from scipy import stats
import cv2
import matplotlib.pyplot as plt
import zipfile
import io, time
import seaborn as sns
from itertools import combinations
from scipy import stats
from PIL import Image
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def index(request):
    """ROS IOD 分析工具首页视图。

    清除分析相关旧数据，但保留 ros_iod_used 标记用于使用次数追踪。
    """
    for key in ('folders', 'extract_dir', 'current_threshold', 'results_dir',
                'selected_image_frame'):
        request.session.pop(key, None)
    return render(request, 'ros_iod/index.html', {
        'is_authenticated': request.user.is_authenticated,
        'has_used': request.session.get('ros_iod_used', False),
    })


def _check_usage_limit(request):
    """检查匿名用户是否超出使用次数限制。

    Returns:
        tuple: (is_allowed, error_message_or_None)
    """
    if request.user.is_authenticated:
        return True, None
    if request.session.get('ros_iod_used'):
        return False, '您已达到免费使用次数限制（1次），请登录后继续使用'
    return True, None

def analysis_iod(img_array, threshold_value):
    INCIDENT = 255
    BLACK = 0
    if img_array.dtype == np.uint16:
        # x = np.round(
        #     (0.299 * img_array[:, :, 0] + 0.587 * img_array[:, :, 1] + 0.114 * img_array[:, :, 2])
        # ).astype(np.uint16) // 255
        x = np.round(np.mean(img_array, axis=-1) // 255)
    else:
        x = np.round(np.mean(img_array, axis=-1))
    # 剔除标尺
    x = x[300:-200, ]
    invert = 255 - x

    # 目标区域筛选
    cal = -np.log10((invert - BLACK) / (INCIDENT - BLACK))
    cal = np.round(cal, 4)
    binary = cal >= threshold_value
    final_mask = binary

    # iod值计算
    if final_mask.sum() == 0:
        iod = 0
    else:
        iod = (-np.log10((invert - BLACK) / (INCIDENT - BLACK)))[final_mask].mean() * (final_mask).sum()
    area = final_mask.sum()
    raw_value = invert[final_mask].sum()

    colored_image = plt.cm.gray(invert / 255.0)
    colored_image[binary] = [1, 0, 0, 1]
    plot = None
    return iod, area, plot, colored_image, raw_value

# 自动分析函数
def auto_analyze_image(video_path, selected_image_frame, threshold_value):
    """自动分析图片并更新结果"""
    try:
        # img_array = tifffile.imread(video_path, key=selected_image_frame)
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, selected_image_frame)  # 跳转到指定帧
        ret, frame = cap.read()  # 读取该帧
        if ret:
            img_array = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            img_array = None
        cap.release()
        if img_array is not None:
            pic_res = analysis_iod(img_array, threshold_value)
            return img_array, pic_res
    except Exception as e:
        print(f"分析图片时出错: {e}")
        return None, None


def get_video_info(video_path):
    """
    获取视频的基本信息：总帧数、时长(秒)、帧率、分辨率

    Args:
        video_path (str): 视频文件路径

    Returns:
        dict: 包含视频信息的字典，失败时返回None
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"错误：无法打开视频文件 {video_path}")
        return None

    # 获取视频属性
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))  # 总帧数
    fps = cap.get(cv2.CAP_PROP_FPS)  # 帧率
    duration = total_frames / fps if fps > 0 else 0  # 时长(秒)

    offset = int(fps * 20)
    frame_num = 0
    target_frame_num = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame is not None:
            if frame_num >= offset:
                target_frame_num = frame_num
                break
            frame_num += 1
    cap.release()

    return {
        "total_frames": total_frames,
        "fps": round(fps, 2),
        "duration": round(duration, 2),
        'target_frame_num': target_frame_num
    }


from concurrent.futures import ThreadPoolExecutor, as_completed
import cv2
import numpy as np


def analysis_iod_simple(img_array, threshold_value):
    INCIDENT = 255
    BLACK = 0
    if img_array.dtype == np.uint16:
        x = np.round(np.mean(img_array, axis=-1) // 255)
    else:
        x = np.round(np.mean(img_array, axis=-1))
    x = x[300:-200, ]
    invert = 255 - x

    cal = -np.log10((invert - BLACK) / (INCIDENT - BLACK))
    cal = np.round(cal, 4)
    cal = np.nan_to_num(cal, nan=0.0, posinf=0.0, neginf=0.0)
    binary = cal >= threshold_value
    final_mask = binary

    if final_mask.sum() > 0:
        iod = (-np.log10((invert - BLACK) / (INCIDENT - BLACK)))[final_mask].mean() * final_mask.sum()
    else:
        iod = 0
    area = final_mask.sum()
    raw_value = invert[final_mask].sum()
    
    rows, cols = np.where(final_mask)
    brightest_row = int(np.median(rows))
    brightest_col = int(np.median(cols))
    x_clip = img_array[300:-200, ][brightest_row-500:brightest_row+500, brightest_col-1500:brightest_col+1500]
    return iod, area, raw_value,x_clip


# ====================== 多线程获取最大帧（STREAMLIT 最快方案） ======================
def process_single_frame_thread(frame_num, frame, threshold_value):
    try:
        frame_rgb = frame[..., ::-1]
        iod_value, area, raw_value,x_clip  = analysis_iod_simple(frame_rgb, threshold_value)
        if np.isscalar(iod_value) and not np.isnan(iod_value):
            return {
                "frame_num": frame_num,
                "iod_value": float(iod_value),
                "area": int(area),
                "intensity": int(raw_value),
                "frame": frame,
                "frame_clip": x_clip
            }
        return None
    except Exception:
        return None

def get_max_frame_threaded(video_path, threshold_value, max_workers=8):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, 0, 0, 0, None, None

    frame_dict = {}
    frame_count = 0

    fps = cap.get(cv2.CAP_PROP_FPS)
    offset = int(fps * 20)
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, offset)

        # 读取该帧
        ret, frame = cap.read()
        cap.release()
    except:
        return None, 0, 0, 0, None, None
    # best = process_single_frame_thread(frame_count, frame_dict[frame_count], threshold_value)
    best = process_single_frame_thread(offset, frame, threshold_value)

    if not best:
        return None, 0, 0, 0, None, None

    return (
        best["frame_num"],
        best["iod_value"],
        best["area"],
        best["intensity"],
        best["frame"],
        best["frame_clip"]
    )


@csrf_exempt
def upload_file(request):
    if request.method == 'POST' and request.FILES.get('zip_file'):
        temp_dir = settings.TEMP_DIR
        zip_file = request.FILES['zip_file']
        zip_path = os.path.join(temp_dir, "uploaded.zip")
        try:
            with open(zip_path, "wb") as f:
                f.write(zip_file.read())
            local_time = time.localtime()
            # 格式化时间戳为 "YYYYMMDD_HHMMSS" 格式
            timestamp = time.strftime("%Y%m%d_%H%M%S", local_time)
            extract_dir = os.path.join(temp_dir, "extracted_{}".format(timestamp))
            os.makedirs(extract_dir, exist_ok=True)

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

            # 获取解压后的第一个文件夹
            if os.listdir(extract_dir):
                extract_dir = os.path.join(extract_dir, os.listdir(extract_dir)[0])
            folders = [f for f in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, f))]

            request.session['folders'] = folders
            request.session['extract_dir'] = extract_dir
            return JsonResponse({
                'success': True,
                'folders': folders,
                'extract_dir': extract_dir

            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'No file provided'})


@csrf_exempt
def select_folders(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            selected_folders = data.get('folders', [])
            
            if not selected_folders:
                return JsonResponse({'success': False, 'error': 'No folders selected'})
            
            extract_dir = request.session.get('extract_dir')
            all_videos = []
            
            for folder in selected_folders:
                folder_path = os.path.join(extract_dir, folder)
                if os.path.isdir(folder_path):
                    all_videos.extend([os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.mp4')])
            
            return JsonResponse({
                'success': True,
                'folders': selected_folders,
                'extract_dir': extract_dir,
                'all_videos': all_videos
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def select_video(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            selected_video = data.get('video', '')
            current_threshold = data.get('threshold', 0.07)

            if not selected_video:
                return JsonResponse({'success': False, 'error': 'No video selected'})
            
            video_info = get_video_info(selected_video)
            if not video_info:
                return JsonResponse({'success': False, 'error': 'Failed to get video info'})
            
            target_frame_num = video_info['target_frame_num']
            selected_image_frame = request.session.get('selected_image_frame', target_frame_num)
            if not selected_image_frame:
                selected_image_frame = target_frame_num
            
            img_array, pic_res = auto_analyze_image(selected_video, selected_image_frame, current_threshold)
            
            if img_array is None:
                return JsonResponse({'success': False, 'error': 'Failed to analyze image'})
            
            fig_total, axes_total = plt.subplots(2, 1, figsize=(9, 6))
            fig_total.subplots_adjust(hspace=0.3, wspace=0.3)
            axes_total = axes_total.flatten()
            axes_total[0].imshow(img_array)
            axes_total[1].imshow(pic_res[3])
            buf = BytesIO()
            fig_total.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            main_chart_data = base64.b64encode(buf.read()).decode()
            buf.close()
            plt.close(fig_total)

            request.session['current_threshold'] = current_threshold

            return JsonResponse({
                'success': True,
                'main_chart': main_chart_data,
                'video_info': video_info,
                'analysis_frame': selected_image_frame,
                'threshold': current_threshold
            })
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# 处理单个视频
def process_single_video(video_path, video_name, folder_name, out_folder, batch_threshold):
    """处理单个视频，返回分析结果"""
    try:
        # 获取最大帧
        frame_num, iod_value, area, intensity, frame, frame_clip = get_max_frame_threaded(
            video_path, batch_threshold, max_workers=8
        )
        
        if frame_num is None:
            return {
                "视频": video_name,
                "分组": folder_name,
                "最大帧": None,
                "IOD值": 0,
                "面积": 0,
                "强度": 0,
                "阈值": batch_threshold,
                "状态": "失败",
                "错误信息": "无法获取视频帧"
            }
        if frame is not None:
            save_path = os.path.join(out_folder, f"iod_{os.path.splitext(video_name)[0]}.tif")
            save_path_clip = os.path.join(out_folder, f"iod_{os.path.splitext(video_name)[0]}_clip.tif")
            # 确保输出目录存在
            os.makedirs(out_folder, exist_ok=True)          
            # 使用 cv2.imencode 处理中文路径问题
            try:
                _, buffer = cv2.imencode('.tif', frame)
                if buffer is not None:
                    with open(save_path, 'wb') as f:
                        f.write(buffer)
                else:
                    print(f"警告：无法编码图片 {save_path}")
            except Exception as e:
                print(f"警告：写入图片 {save_path} 失败: {e}")
            
            if frame_clip is not None:
                try:
                    _, buffer_clip = cv2.imencode('.tif', frame_clip)
                    if buffer_clip is not None:
                        with open(save_path_clip, 'wb') as f:
                            f.write(buffer_clip)
                    else:
                        print(f"警告：无法编码图片 {save_path_clip}")
                except Exception as e:
                    print(f"警告：写入图片 {save_path_clip} 失败: {e}")
            else:
                print(f"警告：frame_clip 为 None，跳过写入 {save_path_clip}")
        # # 保存结果图片
        # fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        # # 原图
        # axes[0].imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        # axes[0].set_title(f'原图 - {video_name}')
        # axes[0].axis('off')
        
        # # 裁剪图
        # if frame_clip is not None:
        #     axes[1].imshow(cv2.cvtColor(frame_clip, cv2.COLOR_BGR2RGB))
        #     axes[1].set_title(f'裁剪区域 - IOD: {iod_value:.2f}')
        #     axes[1].axis('off')
        
        # plt.tight_layout()
        # result_img_path = os.path.join(out_folder, f"{os.path.splitext(video_name)[0]}_result.png")
        # plt.savefig(result_img_path, dpi=150, bbox_inches='tight')
        # plt.close(fig)
        
        return {
            "视频": video_name,
            "分组": folder_name,
            "最大帧": frame_num,
            "IOD值": round(iod_value, 4),
            "面积": int(area),
            "强度": int(intensity),
            "阈值": batch_threshold,
            "状态": "成功"
        }
    except Exception as e:
        import traceback
        return {
            "视频": video_name,
            "分组": folder_name,
            "最大帧": None,
            "IOD值": 0,
            "面积": 0,
            "强度": 0,
            "阈值": batch_threshold,
            "状态": "异常",
            "错误信息": str(e)
        }


# 处理单个文件夹内的所有视频（使用多线程）
def process_folder(folder_name, extract_dir, out_dir, batch_threshold, folder_workers):
    """处理单个文件夹内的所有视频，文件夹内视频并行处理"""
    folder_path = os.path.join(extract_dir, folder_name)
    out_folder = os.path.join(out_dir, folder_name)
    os.makedirs(out_folder, exist_ok=True)

    videos = [v for v in os.listdir(folder_path) if v.lower().endswith(('.mp4', '.avi', '.mkv', '.mov'))]
    folder_results = []
    # 注意：不要在子线程中使用 st.write，返回结果后统一处理
    # 使用线程池并行处理文件夹内的视频
    with ThreadPoolExecutor(max_workers=folder_workers) as executor:
        # 提交所有视频任务
        future_to_video = {
            executor.submit(process_single_video, 
                          os.path.join(folder_path, video), 
                          video, folder_name, out_folder, batch_threshold): video
            for video in videos
        }

        # 收集结果
        for future in as_completed(future_to_video):
            video_name = future_to_video[future]
            try:
                result = future.result()
                folder_results.append(result)
            except Exception as e:
                # 处理异常情况
                folder_results.append({
                    "视频": video_name,
                    "分组": folder_name,
                    "最大帧": None,
                    "IOD值": 0,
                    "面积": 0,
                    "强度": 0,
                    "阈值": batch_threshold,
                    "状态": "异常",
                    "错误信息": str(e)
                })

    return folder_results

def create_zip_from_folder(folder_path):
    """创建压缩包，包含指定文件夹下的所有文件，空文件夹不会被压缩"""
    zip_bytes = io.BytesIO()
    # 创建时间戳文件夹名
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outer_folder = f"结果_{timestamp}"
    with zipfile.ZipFile(zip_bytes, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                # 在文件名前添加时间戳文件夹
                arcname_with_outer = os.path.join(outer_folder, arcname)
                zipf.write(file_path, arcname_with_outer)
    zip_bytes.seek(0)
    return zip_bytes

@csrf_exempt
def select_all(request):
    if request.method == 'POST':
        try:
            # 检查使用次数限制
            allowed, limit_error = _check_usage_limit(request)
            if not allowed:
                return JsonResponse({'success': False, 'error': limit_error}, status=403)

            data = json.loads(request.body)
            batch_threshold = data.get('threshold', 0.07)

            results = []
            extract_dir = request.session.get('extract_dir')
            folders = request.session.get('folders')
            out_dir = os.path.join(extract_dir, "output")
            os.makedirs(out_dir, exist_ok=True)

            # 计算总视频数
            total_videos = 0
            for f in folders:
                fp = os.path.join(extract_dir, f)
                vs = [v for v in os.listdir(fp) if v.lower().endswith(('.mp4', '.avi', '.mkv', '.mov'))]
                total_videos += len(vs)

            folder_workers =  2 if len(folders) >1 else 1
            video_workers = 4 

            # 使用线程池并行处理文件夹
            with ThreadPoolExecutor(max_workers=folder_workers) as executor:
                # 提交所有文件夹任务
                future_to_folder = {
                    executor.submit(process_folder, folder, extract_dir, out_dir,
                                  batch_threshold, video_workers): folder
                    for folder in folders
                }

                completed_folders = 0
                # 收集结果
                for future in as_completed(future_to_folder):
                    folder_name = future_to_folder[future]
                    try:
                        folder_results = future.result()
                        results.extend(folder_results)
                        completed_folders += 1
                        success_count = sum(1 for r in folder_results if r.get("状态") == "成功")

                    except Exception as e:
                        import traceback
                        error_detail = traceback.format_exc()
                        print(f"❌ 文件夹 '{folder_name}' 处理失败: {e}")

            df = pd.DataFrame(results)
            df.to_excel(os.path.join(out_dir, "iod_results.xlsx"), index=False)
            request.session['results_dir'] = out_dir

            # 标记匿名用户已使用
            if not request.user.is_authenticated:
                request.session['ros_iod_used'] = True

            return JsonResponse({
                'success': True,
                'message': f"✅ 处理完成，结果已保存到 {out_dir}",
                'total_videos': total_videos,
                'completed_folders': completed_folders,
                'success_count': success_count,
            })
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})



@csrf_exempt
def download_results(request):
    if request.method == 'POST':
        try:
            results_dir = request.session.get('results_dir')
            if not results_dir:
                return JsonResponse({'success': False, 'error': 'No results_dir in session'})
            
            zip_bytes = create_zip_from_folder(results_dir)
            outer_folder = os.path.basename(results_dir)

            response = HttpResponse(zip_bytes.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{outer_folder}.zip"'
            return response
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

