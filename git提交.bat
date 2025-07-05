@echo off
chcp 65001 >nul
echo ========================================
echo Git 提交工具
echo ========================================
echo.

:: 检查Git是否安装
git --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Git，请先安装Git
    pause
    exit /b 1
)

:: 检查是否在Git仓库中
git status >nul 2>&1
if errorlevel 1 (
    echo 初始化Git仓库...
    git init
)

echo 当前Git状态:
git status --short

echo.
echo 请选择操作:
echo 1. 添加所有文件并提交
echo 2. 查看提交历史
echo 3. 查看当前状态
echo 4. 退出
echo.
set /p choice="请输入选择 (1-4): "

if "%choice%"=="1" goto commit
if "%choice%"=="2" goto log
if "%choice%"=="3" goto status
if "%choice%"=="4" goto exit
echo 无效选择，请重新输入
goto menu

:commit
echo.
set /p commit_msg="请输入提交信息: "
if "%commit_msg%"=="" (
    set commit_msg="更新项目文件"
)

echo 正在添加文件...
git add .

echo 正在提交...
git commit -m %commit_msg%

if errorlevel 1 (
    echo 提交失败！
    pause
    goto menu
)

echo 提交成功！
echo.
echo 提示: 如需推送到远程仓库，请使用以下命令:
echo git remote add origin https://gitee.com/your-username/space-planning-spider.git
echo git push -u origin master
echo.
pause
goto menu

:log
echo.
echo 提交历史:
git log --oneline -10
echo.
pause
goto menu

:status
echo.
echo 当前状态:
git status
echo.
pause
goto menu

:exit
echo 退出Git提交工具
exit /b 0 