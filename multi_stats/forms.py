from django import forms
import pandas as pd
from io import BytesIO


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='上传Excel文件',
        help_text='支持 .xlsx 格式',
        widget=forms.FileInput(attrs={'accept': '.xlsx'})
    )


class ChartConfigForm(forms.Form):
    CHART_TYPE_CHOICES = [
        ('柱状图', '柱状图'),
        ('柱状图叠加点图', '柱状图叠加点图'),
        ('散点图', '散点图'),
    ]

    TEST_METHOD_CHOICES = [
        ('T检验 (ttest_ind)', 'T检验 (ttest_ind)'),
        ('秩和检验 (mannwhitneyu)', '秩和检验 (mannwhitneyu)'),
    ]

    group_column = forms.ChoiceField(label='分组字段', required=True)
    test_method = forms.ChoiceField(
        label='统计检验方法',
        choices=TEST_METHOD_CHOICES,
        initial='T检验 (ttest_ind)'
    )
    chart_type = forms.ChoiceField(
        label='图表类型',
        choices=CHART_TYPE_CHOICES,
        initial='柱状图'
    )
    selected_palette = forms.CharField(initial='default_color', required=False)
    selected_fields = forms.CharField(widget=forms.HiddenInput(), required=False)
    selected_comparison_groups = forms.CharField(widget=forms.HiddenInput(), required=False)
    fig_width = forms.IntegerField(label='单图宽度', initial=5, min_value=3, max_value=15)
    fig_height = forms.IntegerField(label='单图高度', initial=4, min_value=3, max_value=15)
    group_spacing = forms.FloatField(label='组间距', initial=1.0, min_value=0.5, max_value=2.0)
    bar_width = forms.FloatField(label='柱子宽度', initial=0.6, min_value=0.3, max_value=1.0)
    line_width = forms.FloatField(label='线宽', initial=2.5, min_value=1.0, max_value=5.0)
    low_alpha = forms.FloatField(label='柱子透明度', initial=0.4, min_value=0.0, max_value=1.0)
    point_size = forms.IntegerField(label='点图点大小', initial=10, min_value=5, max_value=50)
    show_title = forms.BooleanField(label='显示图表标题', initial=True, required=False)
    show_legend = forms.BooleanField(label='显示图例', initial=True, required=False)
    show_grid = forms.BooleanField(label='显示网格', initial=True, required=False)


class SampleFilterForm(forms.Form):
    pass
