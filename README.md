# 🧬 斑马鱼分析系统 (Zebrafish Analysis Platform)

基于 Django 的斑马鱼实验数据综合分析平台，提供 ROS 荧光视频分析、多指标统计作图、抗氧化报告生成等功能。

## 功能模块

### ⚡ ROS IOD 分析

斑马鱼 ROS 荧光视频分析工具，支持 IOD（积分光密度）值计算和视频帧分析。

- 上传包含荧光视频的 ZIP 压缩包
- 选择分析文件夹和视频
- 自动计算 IOD 值并生成可视化图表
- 支持批量视频处理


### 🧪 抗氧化报告

斑马鱼抗氧化实验报告生成工具，支持从 ROS 视频处理结果生成专业的 Word 报告。

- 四步工作流：上传数据 → 配置信息 → 统计分析 → 生成报告
- 支持上传包含 ROS 实验结果的 ZIP 压缩包
- 自动进行多组间统计分析（ANOVA、t 检验等）
- 基于 Word 模板生成专业实验报告（`.docx` 格式）
- 支持对照组与实验组的灵活配置


### 📊 多指标统计作图

通用的多指标统计分析工具，支持上传 Excel 数据进行统计分析和图表生成。

- 上传 `.xlsx` 格式的 Excel 数据文件
- 选择分组字段和数值字段
- 自动进行 t 检验 / Mann-Whitney U 检验
- 生成柱状图、散点图等统计图表
- 支持样本筛选和分页浏览

### 👤 用户管理

完整的用户认证与权限管理系统。

- 用户注册（需管理员审批）
- JWT 认证登录
- 角色管理：管理员、研究员、操作员、观察者
- 登录日志和操作日志记录
- 个人信息修改与密码管理

## 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | Django 4.2 + Django REST Framework 3.17 |
| **认证** | JWT (djangorestframework-simplejwt) |
| **数据库** | SQLite（默认）/ PostgreSQL / MySQL |
| **前端** | Django Templates + 原生 JavaScript + Vue 3（部分页面） |
| **科学计算** | NumPy, Pandas, SciPy |
| **可视化** | Matplotlib, Seaborn |
| **图像处理** | OpenCV, Pillow, scikit-image |
| **深度学习** | PyTorch 2.2, torchvision, MONAI, Ultralytics |
| **报告生成** | python-docx, docxtpl, docxcompose |
| **任务队列** | Celery + Redis |
| **Python** | 3.10 |

## 快速开始

### 环境要求

- Python 3.10+
- Conda（推荐）或 pip

### 安装步骤

**1. 克隆项目**

```bash
git clone <repository-url>
cd zebrafish_project
```

**2. 创建并激活 Conda 环境**

```bash
conda env create -f environment.yml
conda activate analysis_project
```

**3. 配置环境变量**

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置 `DJANGO_SECRET_KEY` 等配置项。

**4. 初始化数据库**

```bash
python manage.py makemigrations
python manage.py migrate
```

**5. 创建管理员账户**

```bash
python manage.py createsuperuser
```

**6. 启动开发服务器**

```bash
python manage.py runserver
```

访问 http://localhost:8000 即可使用。

## 项目结构

```
zebrafish_project/
├── config/                  # Django 项目配置
│   ├── settings.py          # 主配置文件
│   ├── urls.py              # 根 URL 路由
│   └── wsgi.py              # WSGI 入口
├── ros_iod/                 # ROS IOD 分析应用
│   ├── views.py             # 视图逻辑（视频上传、IOD 计算）
│   ├── models.py            # 数据模型
│   └── urls.py              # URL 路由
├── multi_stats/             # 多指标统计作图应用
│   ├── views.py             # 视图逻辑（Excel 上传、统计图表）
│   ├── utils.py             # 统计分析工具函数
│   ├── models.py            # 数据模型
│   └── urls.py              # URL 路由
├── antioxidant_report/      # 抗氧化报告应用
│   ├── views.py             # 视图逻辑（报告生成）
│   ├── oxidant_report_utils.py  # 报告工具函数
│   ├── models.py            # 数据模型
│   └── urls.py              # URL 路由
├── user_management/         # 用户管理应用
│   ├── views.py             # 认证与用户管理 API
│   ├── models.py            # 用户模型（UUID 主键、角色系统）
│   ├── serializers.py       # REST API 序列化器
│   └── urls.py              # API 路由
├── templates/               # Django 模板（前端页面）
│   ├── base.html            # 基础模板（导航栏、全局样式）
│   ├── home.html            # 首页
│   ├── login.html           # 登录页
│   ├── registration.html    # 注册页
│   ├── user_management.html # 用户管理页
│   ├── ros_iod/             # ROS IOD 页面
│   ├── multi_stats/         # 多指标统计页面
│   └── antioxidant_report/  # 抗氧化报告页面
├── static/                  # 静态资源
├── media/                   # 用户上传文件
├── temp/                    # 临时文件目录
├── manage.py                # Django 管理入口
├── environment.yml          # Conda 环境配置
└── .env.example             # 环境变量模板
```

## 使用说明

### 使用权限

- **匿名用户**：每个工具提供 **1 次** 免费试用机会
- **注册用户**：登录后可不限次数使用所有功能
- **管理员**：可通过用户管理页面审批新用户注册

### ROS IOD 分析

1. 准备包含荧光视频（`.mp4`）的 ZIP 压缩包，按文件夹组织
2. 上传 ZIP 文件
3. 选择分析文件夹
4. 系统自动计算 IOD 值并展示结果

### 多指标统计作图

1. 准备 `.xlsx` 格式的 Excel 数据文件
2. 上传文件并选择分组字段和数值字段
3. 系统自动进行统计检验并生成图表
4. 支持切换不同图表类型查看结果

### 抗氧化报告

1. **上传数据**：上传包含 ROS 实验结果的 ZIP 压缩包
2. **配置信息**：设置实验组别、对照组等信息
3. **统计分析**：系统自动进行多组间统计分析
4. **生成报告**：一键生成 Word 格式的专业实验报告

## License

内部使用项目
