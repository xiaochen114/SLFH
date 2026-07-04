@echo off
set TOKEN=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
set FILE=E:\zy\训练集\smoking_dataset.zip
set URL=https://uploads.github.com/repos/xiaochen114/YOLOv8-/releases/330676458/assets?name=smoking_dataset.zip

echo Uploading smoking dataset to GitHub...
echo File: %FILE%

curl -s -X POST -H "Authorization: token %TOKEN%" -H "Content-Type: application/octet-stream" --upload-file "%FILE%" "%URL%"

echo Done.
pause
