from django import forms


class ReportConfigForm(forms.Form):
    exp_id = forms.CharField(label='报告编号', max_length=100, required=False)
    exp_client = forms.CharField(label='委托单位', max_length=200, required=False)
    exp_project = forms.CharField(label='检测项目', max_length=200, required=False)
    sample_name = forms.CharField(label='样品名称', max_length=200, required=False)
    sample_id = forms.CharField(label='样品编号', max_length=100, required=False, initial='/')
    sample_status = forms.CharField(label='样品状态', max_length=200, required=False)
    sample_num = forms.CharField(label='样品数量', max_length=50, required=False)
    sample_date = forms.DateField(label='收样日期', required=False)
    test_date = forms.DateField(label='测试日期', required=False)
    test_dose = forms.CharField(label='供试物剂量', max_length=100, required=False)


class SampleTypeForm(forms.Form):
    pass


class GroupInfoForm(forms.Form):
    pass
