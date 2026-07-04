@echo off
REM 从GitHub下载吸烟数据集
echo 下载吸烟检测数据集...

curl -L -o smoking_dataset.zip ^
  https://github.com/xiaochen114/YOLOv8-/releases/download/v1.0/smoking_dataset.zip

if exist smoking_dataset.zip (
    echo 下载成功! (42MB)
    move smoking_dataset.zip data\ 2>nul
    echo 已保存到 data\smoking_dataset.zip
) else (
    echo 下载失败，请手动上传
)
pause
