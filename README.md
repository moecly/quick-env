# Quick Env

跨平台开发环境快速配置工具。支持 Git Bash、WSL、Linux、macOS。

## 功能特性

- 支持的工具：lazygit, fd, ripgrep, nvim, tmux
- 多种安装方式：GitHub 下载、包管理器、Git 克隆
- 版本检测与更新提示
- 跨平台支持

## 安装

### 方式一：pip 安装

```bash
pip install -e .
```

### 方式二：直接运行

```bash
python quick-env.py <command>
```

## 配置 PATH

安装后需要添加以下到 `~/.bashrc` 或 `~/.zshrc`：

```bash
export PATH="$HOME/.local/quick-env/bin:$PATH"
```

然后重启 shell 或运行：

```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

## 使用方法

| 命令 | 说明 |
|------|------|
| `quick-env doctor` | 检查系统依赖 |
| `quick-env list` | 列出已安装工具 |
| `quick-env list all` | 列出所有工具 |
| `quick-env list --updates` | 显示有更新的工具 |
| `quick-env install <tool>` | 安装工具 |
| `quick-env install all` | 安装全部工具 |
| `quick-env upgrade <tool>` | 升级工具 |
| `quick-env uninstall <tool>` | 卸载工具 |
| `quick-env info <tool>` | 查看工具详情 |

## 示例

```bash
# 检查系统
quick-env doctor

# 安装全部工具
quick-env install all

# 查看工具状态
quick-env list

# 检查更新
quick-env list --updates

# 安装指定工具
quick-env install lazygit fd ripgrep
```

## 工具说明

| 工具 | 说明 | 安装来源 |
|------|------|---------|
| lazygit | Git TUI | GitHub |
| fd | 快速文件查找 | GitHub |
| ripgrep | 快速 grep | GitHub |
| nvim | Neovim | GitHub |
| tmux | 终端复用器 | 包管理器 |
| tmux-config | Tmux 配置 | Git 克隆 |
| nvim-config | Neovim 配置 | Git 克隆 |

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
