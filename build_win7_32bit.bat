@echo off
chcp 65001
echo 正在创建Windows 7 32位便携版...

REM 安装依赖
pip install -r requirements_win7.txt

REM 使用PyInstaller打包
pyinstaller win7_32bit.spec --noconfirm

REM 创建data目录
mkdir "dist\空间规划政策爬虫_Win7_32位便携版\data"

REM 复制版本信息
copy "version_info.txt" "dist\空间规划政策爬虫_Win7_32位便携版"

REM 创建ZIP包
powershell Compress-Archive -Path "dist\空间规划政策爬虫_Win7_32位便携版" -DestinationPath "dist\空间规划政策爬虫_Win7_32位便携版.zip" -Force

echo 打包完成！
pause