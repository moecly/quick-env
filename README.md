# Quick Env

跨平台开发环境快速配置工具。支持 Git Bash、WSL、Linux、macOS。

## 功能特性

- **多种安装方式**：GitHub 下载、包管理器、Git 克隆
- **版本检测**：自动检测已安装工具和最新版本
- **跨平台支持**：Linux、macOS、Windows Git Bash
- **配置文件**：通过 TOML 自定义工具定义
- **日志记录**：记录安装、卸载、升级操作

## 支持的工具

| 工具 | 说明 | 安装方式 | 优先级 |
|------|------|---------|--------|
| lazygit | Git 终端 UI | GitHub / 包管理器 | GitHub 优先 |
| fd | 快速文件查找 | GitHub / 包管理器 | GitHub 优先 |
| ripgrep | 快速 grep | GitHub / 包管理器 | GitHub 优先 |
| nvim | Neovim 编辑器 | GitHub / 包管理器 | GitHub 优先 |
| tmux | 终端复用器 | 包管理器 | - |
| tmux-config | Tmux 配置 | Git 克隆 | - |
| nvim-config | Neovim 配置 | Git 克隆 | - |

## 快速开始

### 1. 安装

```bash
# pip 安装
pip install -e .

# 或直接运行
python quick-env.py <command>
```

### 2. 初始化

首次运行会自动初始化配置：

```bash
quick-env doctor
```

### 3. 配置 PATH

将以下添加到 `~/.bashrc` 或 `~/.zshrc`：

```bash
export PATH="$HOME/.quick-env/bin:$PATH"
```

然后重启 shell 或运行：

```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

### 4. 安装工具

```bash
# 安装单个工具
quick-env install lazygit

# 安装多个工具
quick-env install fd ripgrep nvim

# 安装全部
quick-env install all
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `quick-env init` | 初始化配置（首次运行自动执行） |
| `quick-env install <tool>` | 安装工具 |
| `quick-env install all` | 安装全部工具 |
| `quick-env install <tool> --force` | 强制重新安装 |
| `quick-env install <tool> -m github` | 指定安装方式 |
| `quick-env uninstall <tool>` | 卸载工具（只删 quick-env 的，不碰系统包） |
| `quick-env upgrade <tool>` | 升级工具 |
| `quick-env list` | 列出已安装的工具 |
| `quick-env list all` | 列出所有工具 |
| `quick-env list --updates` | 显示有更新的工具 |
| `quick-env info <tool>` | 显示工具详细信息 |
| `quick-env doctor` | 系统检查 |
| `quick-env config show` | 显示当前配置 |
| `quick-env config edit` | 编辑配置文件 |

## 配置文件

配置文件位于 `~/.quick-env/configs/tools.toml`

### 文件结构

```toml
[tools.xxx]
name = "xxx"
display_name = "Xxx"
description = "描述"
installable_by = ["github", "package_manager"]
priority.github = 10
priority.package_manager = 30
package_name = "xxx"
repo = "user/repo"
aliases = ["xxx"]

# GitHub 下载的 asset 匹配模式
[tools.xxx.github_asset_patterns]
linux_x86_64 = "xxx_{version}_linux_x86_64.tar.gz"
darwin_x86_64 = "xxx_{version}_darwin_x86_64.tar.gz"

# 包管理器命令名映射
[tools.xxx.package_manager_commands]
apt = "xxx"
brew = "xxx"
default = "xxx"
```

### 字段说明

| 字段 | 必填 | 说明 |
|-----|------|------|
| name | 是 | 工具名称 |
| display_name | 否 | 显示名称 |
| description | 否 | 工具描述 |
| installable_by | 是 | 支持的安装方式：`github`, `package_manager`, `git_clone` |
| priority | 否 | 各安装方式的优先级，数字越小优先级越高 |
| repo | github 必填 | GitHub 仓库 (user/repo) |
| package_name | 否 | 包管理器包名 |
| github_asset_patterns | github 必填 | GitHub asset 匹配模式 |
| package_manager_commands | 否 | 命令名映射（不同系统命令名不同） |
| aliases | 否 | 别名列表 |

### 示例：添加 zoxide

```toml
[tools.zoxide]
name = "zoxide"
display_name = "Zoxide"
description = "快速目录跳转"
installable_by = ["github", "package_manager"]
priority.github = 10
priority.package_manager = 30
package_name = "zoxide"
repo = "ajeetdsouza/zoxide"
aliases = ["z"]

[tools.zoxide.github_asset_patterns]
linux_x86_64 = "zoxide-x86_64-unknown-linux-gnu.tar.gz"
darwin_x86_64 = "zoxide-x86_64-apple-darwin.tar.gz"
darwin_arm64 = "zoxide-aarch64-apple-darwin.tar.gz"
```

## 目录结构

```
~/.quick-env/
├── bin/           # 安装的二进制文件
├── cache/         # 下载缓存
├── logs/          # 日志文件（按天存储，保留 7 天）
└── configs/
    └── tools.toml  # 用户配置文件
```

## 日志

日志保存在 `~/.quick-env/logs/` 目录：
- 按天存储：`quick-env-20260417.log`
- 保留 7 天
- 记录安装、卸载、升级操作

## Tab 补全

启用命令补全。在 `~/.bashrc` 或 `~/.zshrc` 中添加：

```bash
eval "$(quick-env --show-completion)"
```

## 注意事项

### 安装逻辑
1. 按 `installable_by` + `priority` 选择安装方式
2. 已安装的工具会跳过安装（使用 `--force` 强制重新安装）
3. 版本检测按优先级顺序尝试

### 卸载逻辑
- 只删除 `~/.quick-env/bin/` 中的文件
- 不影响系统包管理器安装的工具

## 开发

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码检查
ruff check quick_env/
```

## License

MIT
