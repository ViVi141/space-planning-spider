# Inno Setup 安装指南

## 什么是Inno Setup？

Inno Setup是一个免费的安装程序制作软件，用于创建Windows安装程序。它可以将我们的Python程序打包成标准的Windows安装程序，具有以下特点：

- ✅ 标准的Windows安装界面
- ✅ 可在"程序和功能"中显示和管理
- ✅ 支持卸载功能
- ✅ 自动创建快捷方式
- ✅ 注册表管理
- ✅ 多语言支持

## 下载和安装

### 1. 下载Inno Setup
- **官方网站：** https://jrsoftware.org/isinfo.php
- **下载地址：** https://jrsoftware.org/isdl.php
- **版本选择：** 推荐下载最新版本（当前为6.2.2）

### 2. 安装步骤
1. 下载Inno Setup安装程序（如：`innosetup-6.2.2.exe`）
2. 双击运行安装程序
3. 按照安装向导完成安装
4. 确保勾选"Add Inno Setup directory to PATH"选项

### 3. 验证安装
安装完成后，打开命令提示符或PowerShell，输入：
```cmd
iscc /?
```
如果显示帮助信息，说明安装成功。

## 生成标准安装程序

### 方法一：使用完整打包脚本（推荐）
1. 确保已安装Inno Setup
2. 双击运行 `完整打包.bat`
3. 脚本会自动检测Inno Setup并生成标准安装程序
4. 生成文件：`installer/空间规划政策爬虫系统_v2.1.0_安装程序.exe`

### 方法二：手动生成
1. 激活虚拟环境：`venv\Scripts\activate.bat`
2. 运行打包脚本：`python build_complete_installer.py`
3. 手动编译安装脚本：`iscc installer_script.iss`

## 安装程序特性

### 标准安装程序功能
- **系统集成：** 在"程序和功能"中显示
- **安装向导：** 完整的安装界面
- **快捷方式：** 自动创建开始菜单和桌面快捷方式
- **卸载功能：** 支持标准卸载
- **注册表管理：** 自动管理注册表信息
- **版本信息：** 包含完整的版本信息
- **权限管理：** 支持用户权限控制

### 安装流程
1. **欢迎界面：** 显示程序信息和版本
2. **许可协议：** 显示软件许可协议
3. **安装位置：** 选择安装目录
4. **开始菜单：** 选择开始菜单文件夹
5. **附加任务：** 选择是否创建桌面快捷方式
6. **安装进度：** 显示安装进度
7. **完成安装：** 安装完成，可选择启动程序

## 常见问题

### 1. Inno Setup安装失败
**问题：** 无法安装Inno Setup
**解决：**
- 检查系统权限，尝试以管理员身份运行
- 检查杀毒软件是否阻止安装
- 下载最新版本的安装程序

### 2. 命令未找到
**问题：** `iscc` 命令未找到
**解决：**
- 重新安装Inno Setup，确保勾选"Add to PATH"
- 手动添加Inno Setup目录到系统PATH
- 重启命令提示符或PowerShell

### 3. 编译失败
**问题：** 安装程序编译失败
**解决：**
- 检查安装脚本语法是否正确
- 确保所有源文件存在
- 查看编译错误信息

### 4. 安装程序无法运行
**问题：** 生成的安装程序无法运行
**解决：**
- 检查目标系统兼容性
- 确保有足够的权限
- 检查防火墙和杀毒软件设置

## 高级配置

### 自定义安装脚本
如果需要自定义安装程序，可以编辑 `installer_script.iss` 文件：

```pascal
[Setup]
AppName=空间规划政策爬虫与合规性分析系统
AppVersion=2.1.0
AppPublisher=空间规划政策分析团队
DefaultDirName={autopf}\空间规划政策爬虫系统
DefaultGroupName=空间规划政策爬虫系统
OutputDir=installer
OutputBaseFilename=空间规划政策爬虫系统_v2.1.0_安装程序
SetupIconFile=docs\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
```

### 添加自定义页面
可以在安装脚本中添加自定义页面：

```pascal
[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 安装完成后的自定义操作
  end;
end;
```

## 技术支持

- **Inno Setup官方文档：** https://jrsoftware.org/ishelp/
- **Inno Setup论坛：** https://groups.google.com/forum/#!forum/innosetup
- **项目技术支持：** https://gitee.com/ViVi141/space-planning-spider

## 注意事项

1. **系统要求：** Inno Setup需要Windows 7或更高版本
2. **权限要求：** 生成安装程序可能需要管理员权限
3. **文件大小：** 安装程序会比便携版稍大
4. **兼容性：** 生成的安装程序兼容Windows 7/8/10/11
5. **测试：** 建议在多个系统上测试安装程序

---

**提示：** 如果只需要便携版，可以不安装Inno Setup，直接使用 `快速打包.bat` 即可。 