@echo off
chcp 65001 >nul
echo 空间规划政策爬虫系统卸载工具
echo 版本：v2.1.4
echo.
echo 注意：此操作将删除程序数据目录中的所有数据！
echo.
set /p confirm="确认要卸载程序吗？(y/N): "
if /i "%confirm%"=="y" (
    echo 正在删除数据目录...
    rmdir /s /q "%USERPROFILE%\Documents\空间规划政策爬虫系统" 2>nul
    echo 正在删除程序文件...
    rmdir /s /q "%~dp0" 2>nul
    echo 卸载完成！
) else (
    echo 取消卸载。
)
pause
