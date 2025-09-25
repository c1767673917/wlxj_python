# 使用官方Python运行时作为父镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 将当前目录内容复制到容器的/app中
COPY . /app

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建必要的目录
RUN mkdir -p logs instance backup temp

# 暴露端口5001
EXPOSE 5001

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 运行应用
CMD ["python", "app.py"]