# Django AffinMax Transfer

## 安全配置

### AWS 凭证设置

为了安全起见，AWS 访问密钥不应硬编码在代码中。请按以下步骤配置：

#### 1. 创建 .env 文件

在 `affinmax/` 目录下创建 `.env` 文件（基于 `.env.example`）：

```bash
cd affinmax
cp .env.example .env
```

#### 2. 配置 AWS 凭证

编辑 `.env` 文件，填入你的 AWS 凭证：

```bash
AWS_ACCESS_KEY_ID=your_actual_access_key_here
AWS_SECRET_ACCESS_KEY=your_actual_secret_key_here
AWS_DEFAULT_REGION=ap-southeast-1
```

#### 3. 加载环境变量

在运行 Django 应用之前，确保加载环境变量：

**方法 1: 使用 python-dotenv**

安装 python-dotenv:
```bash
pip install python-dotenv
```

在 `settings.py` 顶部添加:
```python
from dotenv import load_dotenv
import os

load_dotenv()
```

**方法 2: 手动导出环境变量**

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=ap-southeast-1
```

#### 4. 运行应用

```bash
python manage.py runserver
```

### 重要提示

⚠️ **切勿将 `.env` 文件提交到 Git！** 
- `.env` 文件已添加到 `.gitignore`
- 只提交 `.env.example` 作为模板
- 不要在代码中硬编码任何密钥或敏感信息

### JavaScript 文件说明

`affinmax_transfer.js` 现在不再包含 AWS 密钥。所有 AWS 操作都通过后端 Django API 处理。

## 依赖安装

```bash
# Python 依赖
pip install -r requirements.txt

# Node.js 依赖
npm install
```

## 运行项目

```bash
cd affinmax
python manage.py runserver
```
