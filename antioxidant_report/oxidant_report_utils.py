# notebook src
# notebooks/unique_stat/demo.ipynb

import pandas as pd
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import matplotlib
from sqlalchemy import create_engine
import os,sys,time,zipfile,io
from PIL import Image

# sns.set(font='RomanSong', font_scale=1.3, style='ticks')
import matplotlib.font_manager as fm

font_path = 'C:/Windows/Fonts/simhei.ttf'
try:
    CHINESE_FONT = fm.FontProperties(fname=font_path)
except:
    CHINESE_FONT = fm.FontProperties(family='SimHei')

# plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'STSong', 'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

from docxtpl import RichText
import streamlit as st
import matplotlib.colors as mcolors
import colorsys

def lighten_color(color, amount=0.3):
    c = mcolors.to_rgb(color)
    h, l, s = colorsys.rgb_to_hls(*c)
    l = min(1, l + amount)
    return colorsys.hls_to_rgb(h, l, s)


def merge_zebrafish_images(n_images, images_array, groups=None, extract_dir=None):
    """
    合并斑马鱼图片为单张图片
    
    Args:
        n_images: 图片数量
        images_array: 图片数组字典
        groups: 分组名称列表
        extract_dir: 保存图片的目录路径（可选，为None时不保存文件）
    """
    # 合并所有图片
    # 创建子图
    if n_images <= 5:
        n_rows = n_images
        n_cols = 1
        height = 2 * n_rows
    else:
        n_rows = 5
        n_cols = 2
        height = 2.5 * n_rows
    images_array = list(images_array.values())
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6, height),dpi=300,gridspec_kw={'hspace': 0.01})

    # 处理 axes 维度（统一转为2维数组）
    if n_cols == 1:
        axes = axes.reshape(-1, 1)
    if n_images == 1:
        axes = np.array([[axes]])

    # 按列优先顺序填充图片（先左列，再右列）
    for idx in range(n_images):
        # 计算行列位置：先填满左列，再填右列
        col = idx // n_rows  # 0 或 1
        row = idx % n_rows   # 0-4
        
        ax = axes[row, col]
        img = images_array[idx]
        group = groups[idx] if idx < len(groups) else f"组{idx+1}"
        
        # 显示图片
        ax.imshow(img, cmap='gray')
        ax.axis('off')
        
        # 左上角分组标签
        ax.text(0.02, 0.96, group, transform=ax.transAxes,
                fontsize=12, color='white', fontweight='bold',
                verticalalignment='top', horizontalalignment='left',
                #bbox=dict(boxstyle='round', facecolor='black', alpha=0.5)
                )


    # 隐藏多余的子图
    for idx in range(n_images, n_rows * n_cols):
        col = idx // n_rows
        row = idx % n_rows
        axes[row, col].axis('off')

    # 调整间距
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.03, wspace=0.01)
    # 保存（仅在 extract_dir 不为 None 时）
    if extract_dir is not None:
        plt.savefig(os.path.join(extract_dir, "merged_zebrafish.png"), 
                    dpi=300, 
                    bbox_inches='tight',
                    )
        plt.savefig(os.path.join(extract_dir, "merged_zebrafish.pdf"), 
                    dpi=300, 
                    bbox_inches='tight',
                    )
    fig.canvas.draw()
    rgba_buf = fig.canvas.buffer_rgba()
    (w, h) = fig.canvas.get_width_height()
    fig_plot = np.frombuffer(rgba_buf, dtype=np.uint8).reshape((h, w, 4))
    return fig_plot


def merge_images(base_path):
    # 路径设置 - 使用传入的 base_path 参数
    # 注意：不再使用 st.session_state，因为此函数在 Django 环境中使用
    img1_path = os.path.join(base_path, "merged_zebrafish.png") 
    img2_path = os.path.join(base_path, "iod_diff_zebrafish.png") 
    output_path = os.path.join(base_path, "final_merged.png") 
    output_path_pdf = os.path.join(base_path, "final_merged.pdf") 

    # 读取两张图片 
    img1 = Image.open(img1_path) 
    img2 = Image.open(img2_path) 
    img1_array = np.array(img1) 
    img2_array = np.array(img2) 

    # 获取图片信息 
    height1, width1 = img1_array.shape[:2] 
    height2, width2 = img2_array.shape[:2] 

    print(f"图片1 (merged_zebrafish.png): {width1} x {height1}") 
    print(f"图片2 (iod_diff_zebrafish.png): {width2} x {height2}") 

    # 纵向上下合并 
    print("\n宽度 >= 2700，采用纵向上下合并") 
    # 使用 plt.subplots 创建 2 行 1 列的子图布局
    fig, axes = plt.subplots(2, 1, figsize=(6, 12), gridspec_kw={'hspace': 0.01},dpi=300)
    # 图片1
    axes[0].imshow(img1_array) 
    axes[0].axis('off') 
    # 图片2
    axes[1].imshow(img2_array) 
    axes[1].axis('off') 
    # axes[0].text(-0.05, 1.05, 'A', fontsize=24, color='black', fontweight='bold',
    #             transform=axes[0].transAxes, verticalalignment='top')
    # axes[1].text(-0.05, 1.05, 'B', fontsize=24, color='black', fontweight='bold',
    #             transform=axes[1].transAxes, verticalalignment='top')
    # 使用 fig.text 在 Figure 级别添加标签，确保左对齐
    fig.text(0.08, 0.88, 'A', fontsize=24, color='black', fontweight='bold',
             verticalalignment='top', horizontalalignment='left')
    fig.text(0.08, 0.48, 'B', fontsize=24, color='black', fontweight='bold',
             verticalalignment='top', horizontalalignment='left')
    # 保存图片 
    plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1) 
    plt.savefig(output_path_pdf, dpi=300, bbox_inches='tight', pad_inches=0.1) 
    print(f"\n合并完成！") 
    print(f"保存路径: {output_path}") 
    fig.canvas.draw()
    rgba_buf = fig.canvas.buffer_rgba()
    (w, h) = fig.canvas.get_width_height()
    fig_plot = np.frombuffer(rgba_buf, dtype=np.uint8).reshape((h, w, 4))
    return fig_plot


def create_zip_from_folder(folder_path):
    """创建压缩包，包含指定文件夹下的所有文件，空文件夹不会被压缩
    
    优化点：
    1. 使用多线程并行读取文件
    2. 使用更快的压缩级别
    3. 批量写入减少IO操作
    """
    if not os.path.exists(folder_path):
        st.error(f"文件夹不存在: {folder_path}")
        return None
    
    import concurrent.futures
    from concurrent.futures import ThreadPoolExecutor
    
    # 创建时间戳文件夹名
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outer_folder = f"结果_{timestamp}"
    
    # 收集所有文件路径
    file_list = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, folder_path)
            arcname_with_outer = os.path.join(outer_folder, arcname)
            file_list.append((file_path, arcname_with_outer))
    
    if not file_list:
        st.warning("没有文件需要打包")
        return None
    
    # 使用多线程并行读取文件内容
    def read_file_task(file_info):
        file_path, arcname = file_info
        try:
            with open(file_path, 'rb') as f:
                return (arcname, f.read())
        except Exception as e:
            return (arcname, None)
    
    zip_bytes = io.BytesIO()
    
    # 压缩策略选择：
    # - ZIP_STORED: 不压缩，速度最快，适合已压缩格式（tif, jpg等）
    # - ZIP_DEFLATED(1): 快速压缩，平衡速度和大小
    # - ZIP_DEFLATED(6): 默认压缩，更好的压缩率但更慢
    compression = zipfile.ZIP_DEFLATED  # 改为 ZIP_DEFLATED 如果需要压缩
    compresslevel = 1  # 使用压缩时设为 1-9
    
    if compression == zipfile.ZIP_DEFLATED:
        zipf = zipfile.ZipFile(zip_bytes, 'w', compression, compresslevel=compresslevel or 6)
    else:
        zipf = zipfile.ZipFile(zip_bytes, 'w', compression)
    
    # 使用线程池并行读取文件
    with ThreadPoolExecutor(max_workers=8) as executor:
        # 提交所有读取任务
        future_to_file = {executor.submit(read_file_task, file_info): file_info 
                         for file_info in file_list}
        
        # 收集结果并写入zip
        completed = 0
        for future in concurrent.futures.as_completed(future_to_file):
            arcname, data = future.result()
            if data is not None:
                zipf.writestr(arcname, data)
            completed += 1
    
    zipf.close()
    zip_bytes.seek(0)
    return zip_bytes


def p_reset(text):
    # 统计方法描述p斜体
    conclusion_rt = RichText()
    for word in text.split(' '):
        if 'p' == word:
            print(word)
            # Add "p" in italic and the rest of the word (if any) in normal style
            conclusion_rt.add('p', italic=True, bold=True, size=24)
        else:
            conclusion_rt.add(word + ' ',size=24)
    return conclusion_rt


def p_reset_dec(text):
    # 下结论p斜体
    conclusion_rt = RichText()
    for word in text.split('（')[0:-1]:
        if word.startswith('p'):
            print(word)
            # Add "p" in italic and the rest of the word (if any) in normal style
            conclusion_rt.add('p', italic=True, bold=True, size=24)
            if word != 'p':
                conclusion_rt.add(word[1:] + '（', italic=False, size=24)
        else:
            conclusion_rt.add(word + '（', size=24)
    word = text.split('（')[-1]
    conclusion_rt.add('p', italic=True, bold=True, size=24)
    conclusion_rt.add(word[1:], italic=False, size=24)
    return conclusion_rt



def cal_sign_level(p):
    if p >= 0.05:
        return 0
    elif p >= 0.01:
        return 1
    elif p >= 0.001:
        return 2
    else:
        return 3


def render_length(string):
    import unicodedata
    length = 0
    for char in string:
        width = unicodedata.east_asian_width(char)
        if width in ('F', 'W'):
            length += 2
        else:
            length += 1
    return length


def map_sign_level(p):
    if p >= 0.05:
        return 'p>0.05'
    elif p >= 0.01:
        return 'p<0.05'
    elif p >= 0.001:
        return 'p<0.01'
    else:
        return 'p<0.001'


def cal_sign_word(p):
    if p > 0.05:
        return '无统计学差异'
    elif p > 0.01:
        return '具有统计学差异'
    elif p > 0.001:
        return '具有显著性'
    else:
        return '具有极显著性'


def pretty_format(lst):
    if len(lst) == 1:
        return lst[0]
    elif len(lst) == 2:
        return '{}和{}'.format(lst[0], lst[1])
    else:
        return '{}和{}'.format('、'.join(lst[:-1]), lst[-1])


def cal_sign_word_model(p):
    if p > 0.05:
        return '升高但无统计学差异'
    elif p > 0.01:
        return '升高且有统计学差异'
    elif p > 0.001:
        return '显著升高'
    else:
        return '极显著升高'


def cal_sign_word(p):
    if p > 0.05:
        return '降低但无统计学差异'
    elif p > 0.01:
        return '降低且有统计学差异'
    elif p > 0.001:
        return '显著降低'
    else:
        return '极显著降低'

class ZebraFishStatRunner:
    ALLOW_GROUPs = ['正常对照组', '溶剂对照组', '模型对照组', '阳性对照组', '实验组']

    def __init__(self, df, data, target_column='iod'):
        self.neg_ctrl, self.model, self.pos_ctrl, self.exp = None, None, None, []
        self.baseline = None
        self.exp_type = None
        self.df = df.copy()
        self.df['分组名'] = self.df['分组名'].astype(str)
        self.data = data.copy()
        self.data['分组名'] = self.data['分组名'].astype(str)
        self.target_column = target_column
        self.plot = None

        # 开始分组合规性检查
        # 检查列名
        if not '组别' in self.df.columns or not '分组名' in self.df.columns or not '样品类型' in self.df.columns:
            raise Exception('分组表格应提供【组别】，【分组名】和【样品类型】')
        # 检查是否存在限制以外的组
        for x in df['组别'].values:
            if not x in self.ALLOW_GROUPs:
                raise Exception(f'组别【{x}】不合规，请修改，组别应该在下列选项中选择: {self.ALLOW_GROUPs}')
        # 检查是否存在多出的一个组
        for leone in ['正常对照组', '溶剂对照组', '阴性对照组', '阳性对照组']:
            if df[df['组别'] == leone].shape[0] > 1:
                raise Exception(f'组别【{leone}】要求不超过1组，请检查')
        # 初始化空白组
        if df[df['组别'] == '正常对照组'].shape[0] > 0 and df[df['组别'] == '溶剂对照组'].shape[0] > 0:
            raise Exception('空白组和溶剂对照组不允许同时存在')
        if df[df['组别'] == '正常对照组'].shape[0] == 1:
            self.neg_ctrl = (df[df['组别'] == '正常对照组'].iloc[0].组别, df[df['组别'] == '正常对照组'].iloc[0].分组名)
        if df[df['组别'] == '溶剂对照组'].shape[0] == 1:
            self.neg_ctrl = (df[df['组别'] == '溶剂对照组'].iloc[0].组别, df[df['组别'] == '溶剂对照组'].iloc[0].分组名)
        # 初始化模型组
        if df[df['组别'] == '模型对照组'].shape[0] == 1:
            self.model = (df[df['组别'] == '模型对照组'].iloc[0].组别, df[df['组别'] == '模型对照组'].iloc[0].分组名)
        # 初始化阳性对照组
        if df[df['组别'] == '阳性对照组'].shape[0] == 1:
            self.pos_ctrl = (df[df['组别'] == '阳性对照组'].iloc[0].组别, df[df['组别'] == '阳性对照组'].iloc[0].分组名)
        # 初始化实验组
        if df[df['组别'] == '实验组'].shape[0] == 0:
            raise Exception('请提供实验组')
        # if df[df['组别'] == '实验组'].样品类型.unique().shape[0] == 1:
        if df[df['组别'] == '实验组'].样品类型.unique().shape[0] == 1 and df[df['组别'] == '实验组'].分组名.unique().shape[0] > 1:
            self.exp_type = 'gradient'
        else:
            self.exp_type = 'multiple'
        for i, row in df[df['组别'] == '实验组'].iterrows():
            self.exp.append((row.组别, row.分组名))
        # 初始化后校验
        if self.neg_ctrl is None and self.model is None:
            raise Exception('空白组，溶剂对照组或模型组必须存在一个')
        if self.model is not None:
            self.baseline = self.model
        else:
            self.baseline = self.neg_ctrl

    def __repr__(self):
        txt = '================= 分组情况 ====================\n'
        if self.neg_ctrl:
            txt += f'阴性对照组: 类型：{self.neg_ctrl[0]}，分组名称: {self.neg_ctrl[1]}\n'
        else:
            txt += '阴性对照组: 空\n'
        if self.model:
            txt += f'模型组: 类型：{self.model[0]}，分组名称: {self.model[1]}\n'
        else:
            txt += '模型组: 空\n'
        if self.pos_ctrl:
            txt += f'阳性对照组: 类型：{self.pos_ctrl[0]}，分组名称: {self.pos_ctrl[1]}\n'
        else:
            txt += '阳性对照组: 空\n'
        txt += f'实验类型: {self.exp_type}, 实验组: {self.exp}\n'
        txt += '================ 统计学检验 ===================\n'
        # 判断空白与模型是否需要检验
        if self.neg_ctrl is not None and self.model is not None:
            txt += f'Δ 模型组: {self.model[1]}和阴性对照: {self.neg_ctrl[1]}之间进行t检验，确认建模效果\n'
        # 判断阳性对照组是否需要进行检验
        if self.pos_ctrl:
            txt += f'Δ 阳性对照组: {self.pos_ctrl[1]}和基线：{self.baseline[1]}之间进行t检验，确认实验是否有效\n'
        if self.exp_type == 'gradient':
            txt += f'Δ 实验组为浓度梯度，和基线：{self.baseline[1]}进行单因素方差分析，检验待测物效果\n'
        else:
            txt += f'Δ 实验组为多个物质，和基线：{self.baseline[1]}进行单因素方差分析，检验待测物效果\n'
        return txt

    def make_stats(self, scale=True):
        merged = self.df.merge(self.data[['分组名', self.target_column]], on='分组名')
        self.df['数量'] = self.df.分组名.map(dict(merged.分组名.value_counts()))

        normal_stats = merged[['分组名', self.target_column]].groupby('分组名').agg(['mean', 'sem'])[
            self.target_column].reset_index()

        self.df = self.df.merge(normal_stats, on='分组名')

        if scale:
            if self.neg_ctrl:
                ratio = 100 / self.df.loc[self.df['分组名'] == self.neg_ctrl[1], 'mean'].iloc[0]
            else:
                ratio = 100 / self.df.loc[self.df['分组名'] == self.baseline[1], 'mean'].iloc[0]
            self.df['mean'] = self.df['mean'] * ratio
            self.df['sem'] = self.df['sem'] * ratio
            self.data[f'plot_{self.target_column}'] = self.data[self.target_column] * ratio


        else:
            if self.neg_ctrl:
                ratio = 1 / self.df.loc[self.df['分组名'] == self.neg_ctrl[1], 'mean'].iloc[0]
            else:
                ratio = 1 / self.df.loc[self.df['分组名'] == self.baseline[1], 'mean'].iloc[0]

            self.data[f'plot_{self.target_column}'] = self.data[self.target_column]

        # self.df['mean'] = self.df['mean'] * ratio
        # self.df['sem'] = self.df['sem'] * ratio
        # self.data[f'plot_{self.target_column}'] = self.data[self.target_column] * ratio

        self.df['p'] = 1
        self.df['sign'] = ''

        # if self.exp_type == 'multiple':  # 多物质
        #     if (self.model is not None) and (self.pos_ctrl is not None):
        #         flag_pos = '*'  # 和实验组vs模型组的符号一致
        #         flag_model = '#'
        #     else:
        #         flag_model = '#'
        #         flag_pos = '#'
        # else:
        #     if (self.model is not None) and (self.pos_ctrl is not None):
        #         flag_model = '#'
        #         flag_pos = '&'
        #     else:
        #         flag_model = '#'
        #         flag_pos = '#'
        if self.exp_type == 'multiple':  # 多物质
            if (self.model is not None) and (self.pos_ctrl is not None):
                flag_pos = '*'  # 和实验组vs模型组的符号一致
                flag_model = '*'
            else:
                flag_model = '*'
                flag_pos = '*'
        else:
            if (self.model is not None) and (self.pos_ctrl is not None):
                flag_model = '*'
                flag_pos = '*'
            else:
                flag_model = '*'
                flag_pos = '*'

        if self.neg_ctrl is not None and self.model is not None:
            print(f'Δ 模型组: {self.model[1]}和阴性对照: {self.neg_ctrl[1]}之间进行t检验，确认建模效果')
            # 进行t检验
            tstat, tpval = stats.ttest_ind(
                a=self.data[self.data['分组名'] == self.model[1]][self.target_column].sort_values(),
                b=self.data[self.data['分组名'] == self.neg_ctrl[1]][self.target_column].sort_values(),
                alternative="two-sided")
            # 对结果赋值
            self.df.loc[self.df['分组名'] == '模型对照组', 'p'] = float(tpval)
            self.df.loc[self.df['分组名'] == '模型对照组', 'sign'] = flag_model * cal_sign_level(tpval)

        # 判断阳性对照组是否需要进行检验
        if self.pos_ctrl:
            print(f'Δ 阳性对照组: {self.pos_ctrl[1]}和基线：{self.baseline[1]}之间进行t检验，确认实验是否有效')
            # 进行t检验
            tstat, tpval = stats.ttest_ind(
                a=self.data[self.data['分组名'] == self.pos_ctrl[1]][self.target_column].sort_values(),
                b=self.data[self.data['分组名'] == self.baseline[1]][self.target_column].sort_values(),
                alternative="two-sided")
            # 对结果赋值
            self.df.loc[self.df['分组名'] == '阳性对照组', 'p'] = float(tpval)
            self.df.loc[self.df['分组名'] == '阳性对照组', 'sign'] = flag_pos * cal_sign_level(tpval)

        ## we sort group first
        lst = [self.data.loc[self.data['分组名'] == self.baseline[1], self.target_column]]
        group_names = [self.baseline[1]]
        for gn in self.df[self.df['组别'] == '实验组']['分组名'].unique():
            lst.append(self.data.loc[self.data['分组名'] == gn, self.target_column])
            group_names.append(gn)

        if self.exp_type == 'gradient':
            print(f'Δ 实验组为浓度梯度，和基线：{self.baseline[1]}进行单因素方差分析，检验待测物效果')
            print(lst)
            dun_p = stats.dunnett(*lst[1:], control=lst[0]).pvalue
            dun_res = {group_names[i + 1]: dun_p[i] for i in range(len(dun_p))}

            for k, v in dun_res.items():
                self.df.loc[self.df['分组名'] == k, 'p'] = v
                self.df.loc[self.df['分组名'] == k, 'sign'] = '*' * cal_sign_level(v)

        else:
            print(f'Δ 实验组为多个物质，和基线：{self.baseline[1]}进行逐一T检验')

            tres = {}
            for i, gn in enumerate(group_names[1:]):
                tstat, tpval = stats.ttest_ind(a=lst[1:][i],
                                               b=self.data[self.data['分组名'] == self.baseline[1]][
                                                   self.target_column].sort_values(),
                                               alternative="two-sided")
                tres[gn] = tpval
            for k, v in tres.items():
                self.df.loc[self.df['分组名'] == k, 'p'] = v
                self.df.loc[self.df['分组名'] == k, 'sign'] = '*' * cal_sign_level(v)

    def make_plot(self, ylabel='这是一个测试label', slim=False, palette=None):
        base_groups = (self.df['组别'] != '实验组').sum()
        exp_groups = (self.df['组别'] == '实验组').sum()
        unique_groups_in_comparison = self.df['分组名'].unique()
        order = self.df['分组名'].values.tolist()

        if base_groups+exp_groups <= 4:
            f, ax = plt.subplots(figsize=(5, 5.5), dpi=300)
        elif base_groups+exp_groups >= 7:
            f, ax = plt.subplots(figsize=(7, 5.5), dpi=300)
        else:
            f, ax = plt.subplots(figsize=(6, 5.5), dpi=300)

        f.subplots_adjust(bottom=0.22, left=0.2)

        if slim:
            bar_width = 0.5
        else:
            bar_width = 0.7

        line_width = 2.5
        low_alpha = 0.2
        _colors = palette[:len(unique_groups_in_comparison)]
        face_colors = [lighten_color(c, 0) for c in _colors]
        face_colors_rgba = [(*color, low_alpha) for color in face_colors]
        face_colors_hex = [mcolors.to_hex(c, keep_alpha=True) for c in face_colors_rgba]
        group_spacing = 1
        x = group_spacing * np.arange(len(unique_groups_in_comparison)) * group_spacing
        bars = ax.bar(x, self.df['mean'],  bar_width,
                color=face_colors_hex,
                edgecolor=_colors,
                linewidth=line_width,
                label=unique_groups_in_comparison)
        for i, (xi, yi, ei) in enumerate(zip(x, self.df['mean'], self.df['sem'].values)):
            # 获取对应组的颜色
            _color = palette[i % len(palette)]
            # 竖直误差线
            ax.plot([xi, xi], [yi, yi + ei], color=_color, linewidth=line_width)
            # 上端横线
            ax.plot([xi - 0.1, xi + 0.1], [yi + ei, yi + ei], color=_color, linewidth=line_width)
       
        ax.set_xlabel('')
        ax.set_xticks(x)
        ax.set_xticklabels(unique_groups_in_comparison, rotation=30, ha='right', fontsize=10)
        ax.set_ylabel(ylabel, fontsize=18)
        for i, row in self.df.iterrows():
            x = order.index(row['分组名'])
            y = 1.05 * (row['mean'] + row['sem'])
            # x = x.replace('')
            print(x, y, row['mean'], row['sem'])
            ax.text(x, y, row.sign, ha='center')

        sns.despine(ax=ax, top=True, right=True)

        if self.exp_type == 'gradient':
            for i, label in enumerate(ax.get_xticklabels()):
                # if i < base_groups:  # This will rotate the second tick (indexing starts from 0)
                #     label.set_rotation(30)
                #     label.set_horizontalalignment('right')
                label.set_rotation(30)
                label.set_horizontalalignment('center')
                label.set_fontsize(14)

            dx = 8 / 72
            dy = 0 / 72.
            offset = matplotlib.transforms.ScaledTranslation(dx, dy, f.dpi_scale_trans)

            # apply offset transform to all x ticklabels.
            for i, label in enumerate(ax.xaxis.get_majorticklabels()):
                if i < base_groups:  # This will rotate the second tick (indexing starts from 0)
                    label.set_transform(label.get_transform() + offset)


            ymin, ymax = ax.get_ylim()
            # for i in range(10, 59, 1):
            #     j = i / 100 + 0.38
            underline_start = int(100 * (0.04 + base_groups / (base_groups + exp_groups)))
            for i in range(underline_start, 100, 1):
                j = i / 100.0
               # ax.text(x=j, y=-0.2, s='-', ha='right', va='bottom', color='black', size='18',
                ax.text(x=j, y=-0.245, s='-', ha='right', va='bottom', color='black', size='18',
                        transform=ax.transAxes)

            txt = str(self.df['样品类型'].value_counts().index[0])
            #ax.text(x=underline_start / 130 + 0.4 + render_length(txt) / 81, y=-0.28, s=txt, ha='right', va='bottom',
            ax.text(x=underline_start / 130 + 0.4 + render_length(txt) / 81, y=-0.295, s=txt, ha='right', va='bottom',
                    color='black',
                    size='16',
                    transform=ax.transAxes)
            ax.set_ylim(ymin, ymax)
        else:
            #plt.xticks(rotation=30, ha='right')
            plt.xticks(rotation=30, ha='center', fontsize=14)

            dx = 8 / 72
            dy = 0 / 72.
            offset = matplotlib.transforms.ScaledTranslation(dx, dy, f.dpi_scale_trans)

            # apply offset transform to all x ticklabels.
            for label in ax.xaxis.get_majorticklabels():
                label.set_transform(label.get_transform() + offset)


        f.canvas.draw()
        rgba_buf = f.canvas.buffer_rgba()
        (w, h) = f.canvas.get_width_height()
        self.plot = np.frombuffer(rgba_buf, dtype=np.uint8).reshape((h, w, 4))
