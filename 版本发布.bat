@echo off
chcp 65001 >nul
echo ========================================
echo 版本发布脚本 v1.1.1
echo ========================================
echo.

echo 正在提交新版本到Gitee...
echo.

:: 添加所有文件
git add .

:: 提交更改
git commit -m "发布版本 v1.1.1 - 修复数据库路径问题，解决打包后无法爬取的问题"

:: 推送到远程仓库
git push origin main

if errorlevel 1 (
    echo.
    echo 推送失败！请检查网络连接和仓库配置。
    pause
    exit /b 1
)

echo.
echo ========================================
echo 版本发布成功！
echo ========================================
echo.
echo 版本信息: v1.1.1
echo 主要更新:
echo - 修复数据库路径问题
echo - 解决打包后无法爬取的问题
echo - 增强网络环境兼容性
echo - 添加诊断工具
echo - 改进错误处理
echo.
echo 打包文件位置: dist\空间规划政策爬虫系统.exe
echo 文件大小: 45MB
echo.
echo 您可以将dist目录复制到其他电脑上运行。
echo.

pause 