# 空间规划政策爬虫与合规性分析系统

## 📋 项目简介

本项目为"空间规划政策爬虫与合规性分析系统"，集成了政策数据爬取、合规性分析、智能对比、数据导出等功能，适用于国土空间规划、城市更新等领域的政策信息收集与分析。

## ✨ 主要功能

- **🕷️ 智能爬虫**：自动获取国家住建部等机构的最新政策数据
- **📊 合规性分析**：对政策文本进行合规性评分与风险识别
- **🔍 智能对比**：多政策文本相似度对比与关键词高亮
- **📤 数据导出**：支持导出为Word、Excel等格式
- **🔄 批量更新**：一键更新所有政策数据
- **🖥️ 图形界面**：基于PyQt5的可视化操作界面

## 📁 目录结构

```
kj/
├── src/space_planning/     # 源代码目录
│   ├── main.py            # 主程序入口
│   ├── core/              # 核心模块（配置、数据库）
│   ├── gui/               # 图形界面
│   ├── spider/            # 爬虫模块
│   └── utils/             # 工具模块
├── docs/                  # 文档目录
├── requirements.txt       # 依赖包列表
├── 启动程序.bat          # Windows启动脚本
└── README.md             # 项目说明
```

## 🚀 快速开始

### 环境要求
- Python 3.7 及以上版本
- Windows 7/8/10/11 (64位)

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://gitee.com/ViVi141/space-planning-spider.git
   cd space-planning-spider
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动程序**
   ```bash
   # 方式一：直接运行
   python src/space_planning/main.py
   
   # 方式二：Windows下双击启动
   启动程序.bat
   ```

## 📖 使用说明

1. **选择查询模式**：日常监控、项目分析等
2. **输入关键词**：支持空格分隔多个关键词（可选）
3. **设置时间范围**：或使用预设模式
4. **智能查询**：点击获取政策数据
5. **后续操作**：合规性分析、智能对比、数据导出等

## 🔧 技术栈

- **后端框架**：Python 3.7+
- **GUI框架**：PyQt5
- **数据库**：SQLite
- **网络请求**：requests
- **HTML解析**：BeautifulSoup4
- **文档处理**：python-docx
- **文本相似度**：fuzzywuzzy

## 📦 依赖包

```
PyQt5              # GUI界面
requests           # 网络请求
beautifulsoup4     # HTML解析
python-docx        # Word文档处理
fuzzywuzzy         # 文本相似度
python-Levenshtein # 编辑距离算法
lxml               # XML/HTML解析
```

## 🐛 常见问题

### Q: 程序启动慢怎么办？
A: 首次运行需初始化数据库和代理池，请耐心等待。

### Q: 爬虫无法获取数据？
A: 请检查网络连接或代理池状态。

### Q: 依赖包安装失败？
A: 请确保Python版本正确，或尝试使用国内镜像源：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 Issue：[Gitee Issues](https://gitee.com/ViVi141/space-planning-spider/issues)
- 邮箱：747384120@qq.com

## ⭐ 如果这个项目对您有帮助，请给个Star！

---

**注意**：本项目仅供学习和研究使用，请遵守相关法律法规和网站使用条款。 