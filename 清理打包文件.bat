@echo off
chcp 65001 >nul
echo ========================================
echo 清理打包文件
echo ========================================
echo.

echo 正在清理打包产生的临时文件...
echo.

:: 清理build目录
if exist build (
    echo 删除 build 目录...
    rmdir /s /q build
)

:: 清理__pycache__目录
if exist __pycache__ (
    echo 删除 __pycache__ 目录...
    rmdir /s /q __pycache__
)

:: 清理src目录下的__pycache__
for /d /r src %%d in (__pycache__) do @if exist "%%d" (
    echo 删除 %%d...
    rmdir /s /q "%%d"
)

:: 清理.spec文件
if exist *.spec (
    echo 删除 .spec 文件...
    del *.spec
)

:: 清理临时文件
if exist temp_build.spec (
    echo 删除临时spec文件...
    del temp_build.spec
)

echo.
echo 清理完成！
echo.
echo 注意: dist目录中的可执行文件已保留
echo 如需删除dist目录，请手动删除
echo.

pause 