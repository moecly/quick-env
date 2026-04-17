# quick-env

跨平台开发环境快速配置工具，支持 lazygit、fd、rg、nvim、tmux 等工具的安装、升级、卸载、版本检测。

## 项目目标

- 配置文件（TOML）管理工具定义，方便扩展新工具
- 支持多平台：Git Bash、WSL、Linux、macOS
- 多种安装方式：GitHub 下载、包管理器、Git 克隆
- 不自动修改用户文件（.bashrc 等），只提示需要添加的环境变量
- 工具直接安装到 `~/.quick-env/bin/`

## 当前进度

### 已完成

- [x] 配置文件从代码分离到 `tools.toml`
- [x] 优先级配置化（priority.github、priority.package_manager）
- [x] init 命令 + 自动初始化
- [x] 字段命名优化：
  - `asset_patterns` → `github_asset_patterns`
  - `platform_commands` → `package_manager_commands`
- [x] 测试读取项目配置，用户配置独立
- [x] 错误处理（TOML 解析失败时打印信息）

### 待实现

- [ ] 日志功能（使用 `quick_env_logs` 目录）
- [ ] Tab 补全（启用 typer 自动补全）
- [ ] 配置编辑命令（`quick-env config edit`）
- [ ] 自动创建必要目录（bin、cache、logs）

## 目录结构

```
~/.quick-env/
├── bin/           # 安装的二进制文件
├── cache/         # 下载缓存
├── logs/          # 日志文件（待实现）
└── configs/
    └── tools.toml  # 用户配置
```

## 配置说明

- **项目模板**: `tools.toml`（项目根目录）
- **用户配置**: `~/.quick-env/configs/tools.toml`（首次运行自动创建）
- **测试**: 直接读取项目 `tools.toml`

## 工具定义格式

```toml
[tools.xxx]
name = "xxx"
display_name = "Xxx"
description = "Description"
installable_by = ["github", "package_manager", "git_clone"]
priority.github = 10           # 可选，默认 100
priority.package_manager = 30  # 可选
package_name = "xxx"           # 包管理器包名
repo = "user/repo"            # GitHub 仓库
aliases = ["xxx"]              # 别名

# GitHub 下载的 asset 匹配模式
[tools.xxx.github_asset_patterns]
linux_x86_64 = "xxx_{version}_linux_x86_64.tar.gz"
darwin_x86_64 = "xxx_{version}_darwin_x86_64.tar.gz"

# 包管理器命令名映射
[tools.xxx.package_manager_commands]
apt = "fdfind"   # Debian/Ubuntu
brew = "fd"      # macOS
default = "fd"
```

## 安装方式优先级

在 `tools.toml` 中配置：

```toml
[tools.nvim]
installable_by = ["github", "package_manager"]
priority.github = 10           # 数字越小优先级越高
priority.package_manager = 30
```

默认优先级（未配置时）：
- github: 10
- git_clone: 10
- package_manager: 30

## CLI 命令

```bash
quick-env init              # 初始化配置
quick-env install <tool>    # 安装工具
quick-env install all       # 安装全部
quick-env uninstall <tool>  # 卸载工具
quick-env upgrade <tool>    # 升级工具
quick-env list              # 列出已安装
quick-env list all          # 列出全部
quick-env list --updates    # 显示有更新的
quick-env info <tool>       # 查看详情
quick-env doctor            # 系统检查
```

## 注意事项

1. `installable_by` 只是声明支持哪些安装方式，实际选择由 `get_best_installer()` 按优先级决定
2. `{version}` 在 asset_pattern 中会被替换为实际版本号
3. asset 名称区分大小写，需与 GitHub Release 页面一致
