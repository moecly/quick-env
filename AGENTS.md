# quick-env

跨平台开发环境快速配置工具，支持 lazygit、fd、rg、nvim、tmux 等工具的安装、升级、卸载、版本检测。

## 项目目标

- 配置文件（TOML）驱动，完全可扩展，添加新工具无需修改代码
- 支持多平台：Git Bash、WSL、Linux、macOS
- 支持两类内容：二进制工具 + 配置文件（dotfiles）
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
- [x] 日志功能（使用 `quick_env_logs` 目录，按天存储，保留 7 天）
- [x] 配置编辑命令（`quick-env config edit`）
- [x] 配置显示命令（`quick-env config show`）
- [x] 自动创建必要目录（bin、cache、logs、data）
- [x] 版本检测按优先级顺序
- [x] 卸载只删 quick-env 的，不碰系统包
- [x] 添加包管理器支持到 lazygit、fd、ripgrep
- [x] 解压目录与 bin 入口分离（data/ + 软链接）
- [x] 平台差异化统一入口（Platform 类）
- [x] Git Bash/MSYS2 支持（使用 .cmd 脚本）

### 待实现

- [ ] 增强 is_installed 检测逻辑：检查软链接目标是否有效，避免"假安装"状态
- [ ] 系统处理统一到 Platform 类：封装 shutil.which、os.symlink、shutil.rmtree 等
- [x] 目录结构重构：`data/` → `tools/`，新增 `dotfiles/` 目录
- [x] 新增 `type` 字段区分工具类型（`binary` / `dotfile`）
- [x] 新增 dotfile 配置格式（`links`、`exclude`、`config_branch`）
- [x] 实现 DotfileInstaller（支持 glob 模式链接）
- [x] 并行安装支持（`install all` 并发下载）
- [x] 配置迁移：更新 `tools.toml` 格式
- [x] 增强 doctor 命令：诊断工具状态（软链接、可用性、dotfile 链接）
- [x] 实现 `doctor --fix` 自动修复功能
- [x] 可扩展安装器架构（InstallerRegistry + 插件机制）
- [x] 新增 custom_script 安装器
- [x] 新增 custom_url 安装器

## 开发规范

### 代码更新同步要求

每次更新代码时，**必须**同步更新测试和文档：

| 更新内容 | 必须同步更新 |
|----------|--------------|
| 新增功能 | 测试用例 + AGENTS.md |
| 修改字段 | 测试断言 + 文档说明 |
| 重构目录 | 所有涉及路径的测试 |
| 新增 API | 对应单元测试 |

### 测试文件结构

```
tests/
├── test_tools.py           # 工具定义、配置解析
├── test_installer.py       # 安装器逻辑
├── test_platform.py        # 平台检测
├── test_github.py          # GitHub API
├── test_downloader.py      # 下载解压
├── test_dotfile.py         # 新增：dotfile 链接逻辑
├── test_parallel.py        # 新增：并行安装
└── test_doctor.py          # 新增：诊断功能
```

### 待补充的测试

| 功能 | 测试内容 |
|------|----------|
| DotfileInstaller | glob 匹配、目录结构、冲突处理测试 |
| 并行安装 | 并发下载、错误处理测试 |
| doctor 增强 | 7 层诊断测试 |

## doctor 命令详细设计

### 诊断分层

```
doctor
├── 1. System Check（系统检查）
├── 2. Directory Check（目录检查）
├── 3. Config Check（配置检查）
├── 4. Binary Tools Check（工具检查）
├── 5. Dotfiles Check（配置文件检查）
├── 6. PATH Check（环境变量检查）
└── 7. Network Check（网络检查，可选）
```

### 1. System Check

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Python 版本 | ✓/✗ | Python ≥ 3.10 |
| Git | ✓/✗ | `git --version` |
| curl/wget | ✓/✗ | 至少一个可用 |
| 包管理器 | ✓/! | apt/brew/dnf 等，! 表示无但不影响 |
| 平台检测 | info | Linux/macOS/WSL/Git Bash |

### 2. Directory Check

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `~/.quick-env/` | ✓/✗ | 主目录 |
| `~/.quick-env/bin/` | ✓/✗ | 软链接目录 |
| `~/.quick-env/cache/` | ✓/✗ | 下载缓存 |
| `~/.quick-env/tools/` | ✓/! | 工具目录（不存在可接受） |
| `~/.quick-env/dotfiles/` | ✓/! | dotfiles 目录 |
| `~/.quick-env/logs/` | ✓/✗ | 日志目录 |
| `~/.quick-env/configs/` | ✓/✗ | 配置目录 |

**状态说明**：✓ 正常，✗ 缺失（错误），! 可选（警告）

### 3. Config Check

| 检查项 | 状态 | 说明 |
|--------|------|------|
| tools.toml 存在 | ✓/✗ | 配置文件存在 |
| TOML 语法正确 | ✓/✗ | 能否解析 |
| 工具定义完整 | ✓/! | 必需字段是否存在 |
| type 字段 | ✓/! | 是否有 type 字段 |
| 无效的工具类型 | ! | 未知 type 给出警告 |

### 4. Binary Tools Check

对每个 `type = "binary"` 的工具：

| 检查项 | 状态 | 说明 |
|--------|------|------|
| bin 入口存在 | ✓/✗ | `~/.quick-env/bin/lazygit` |
| 软链接有效 | ✓/✗ | 指向的目标存在 |
| 目标可执行 | ✓/✗ | 有执行权限 |
| 工具可运行 | ✓/✗ | `lazygit --version` 成功 |
| 版本检测 | info | 显示当前版本 |
| 平台匹配 | ✓/! | asset pattern 是否匹配当前平台 |

**输出示例**：
```
4. Binary Tools Check
  ✓ lazygit      v0.40.0    OK
  ✓ fd           v8.4.7     OK
  ! rg           -          Not installed
  ✗ nvim         -          Broken symlink
```

### 5. Dotfiles Check

对每个 `type = "dotfile"` 的工具：

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 仓库目录存在 | ✓/✗ | `~/.quick-env/dotfiles/nvim-config/` |
| Git 仓库有效 | ✓/✗ | 是有效的 git 仓库 |
| 分支正确 | ✓/! | 当前分支与 config_branch 一致 |
| 链接状态 | ✓/!/✗ | 符号链接存在且有效 |
| 链接目标存在 | ✓/✗ | `~/.config/nvim` 目录存在 |
| Git 脏状态 | ! | 有未提交的更改 |
| links 匹配 | ✓/! | glob 模式能否匹配到文件 |

**输出示例**：
```
5. Dotfiles Check
  ✓ tmux-config (Clean)
      ├─ Repo:    ~/.quick-env/dotfiles/tmux-config/
      ├─ Branch:  main
      ├─ Links:   1
          ├─ ✓ ~/.tmux.conf
  ✗ nvim-config (Clean)
      ├─ Repo:    ~/.quick-env/dotfiles/nvim-config/
      ├─ Branch:  main
      ├─ Links:   1
          ├─ ✗ ~/.config/nvim
```

### 6. PATH Check

| 检查项 | 状态 | 说明 |
|--------|------|------|
| bin 在 PATH 中 | ✓/✗ | `~/.quick-env/bin` 是否在 $PATH |
| 工具可发现 | ✓/✗ | `which lazygit` 能找到 |

### 汇总输出

```
==================================================
quick-env Doctor Report
==================================================
Platform: Linux (linux) x86_64
Time: 2026-04-17 22:00:00

1. System Check
  ✓ Python (version 3.12)
  ✓ Git
  ✓ curl/wget
  ✓ Package Manager (apt)

2. Directory Check
  ✓ quick_env_home: ~/.quick-env
  ✓ quick_env_bin: ~/.quick-env/bin
  ✓ quick_env_cache: ~/.quick-env/cache
  ✓ quick_env_tools: ~/.quick-env/tools
  ✓ quick_env_dotfiles: ~/.quick-env/dotfiles
  ✓ quick_env_logs: ~/.quick-env/logs
  ✓ quick_env_config: ~/.quick-env/configs

3. Config Check
  ✓ Config exists: ~/.quick-env/configs/tools.toml
      Tools: 10 (binary: 8, dotfile: 2)

4. Binary Tools Check
  ✓ lazygit      v0.40.0    OK                   (quick-env)
  ✓ fd           v8.4.7     OK                   (quick-env)
  ✓ tmux         3.3a       OK                   (system)

5. Dotfiles Check
  ✓ tmux-config (Clean)
      ├─ Repo:    ~/.quick-env/dotfiles/tmux-config/
      ├─ Branch:  main
      ├─ Links:   1
          ├─ ✓ ~/.tmux.conf
  ✓ nvim-config (Clean)
      ├─ Repo:    ~/.quick-env/dotfiles/nvim-config/
      ├─ Branch:  main
      ├─ Links:   1
          ├─ ✓ ~/.config/nvim/

6. PATH Check
  ! ~/.quick-env/bin is NOT in PATH

==================================================
Summary
  System:     4/4 passed
  Directory:  7/7 passed
  Config:     OK
  Binary:     3/3 passed
  Dotfiles:   2/2 passed

Action Required
  Add to PATH:
    export PATH="$HOME/.quick-env/bin:$PATH"

==================================================

### Auto-Fix 功能

使用 `--fix` 参数自动修复检测到的问题：

```bash
quick-env doctor --fix
```

**可修复的项目**：

| 检查项 | 修复操作 |
|--------|----------|
| 目录缺失 | 创建缺失的目录 |
| Binary broken symlink | 删除并重建软链接 |
| Binary 未安装 | 使用最佳安装器安装 |
| Dotfiles 链接 broken | 删除并重建链接 |
| Dotfiles 未克隆 | git clone + 创建链接 |

**注意**：PATH 配置需要用户手动添加，不会自动修改用户 shell 配置。
```

## 目录结构

```
~/.quick-env/
├── bin/           # 软链接/脚本入口
├── cache/         # 下载缓存（压缩包）
├── tools/         # 二进制工具（重命名自 data/）
├── dotfiles/      # 用户配置文件仓库（新增）
├── logs/          # 日志文件（按天存储，保留 7 天）
└── configs/
    └── tools.toml  # 工具配置文件
```

### 安装结构说明

**二进制工具 (type = "binary")**：
- **Linux/macOS/WSL**: `bin/lazygit` → `../tools/lazygit_0.40.0/lazygit`（软链接）
- **Git Bash/MSYS2**: `bin/lazygit.cmd` → 调用 `../tools/lazygit_0.40.0/lazygit.exe`

**配置文件 (type = "dotfile")**：
- 仓库克隆到 `~/.quick-env/dotfiles/<name>/`
- 根据 `links` 配置创建符号链接到用户目录

## 配置说明

- **项目模板**: `tools.toml`（项目根目录）
- **用户配置**: `~/.quick-env/configs/tools.toml`（首次运行自动创建）
- **测试**: 直接读取项目 `tools.toml`

## 工具定义格式

### 二进制工具 (type = "binary")

#### GitHub Release 安装

```toml
[tools.xxx]
type = "binary"              # 工具类型：binary
name = "xxx"
display_name = "Xxx"
description = "Description"
installable_by = ["github", "package_manager"]
priority.github = 10           # 可选，默认 10
priority.package_manager = 30 # 可选
package_name = "xxx"         # 包管理器包名
repo = "user/repo"           # GitHub 仓库
aliases = ["xxx"]             # 别名

[tools.xxx.github_asset_patterns]
linux_x86_64 = "xxx_{version}_linux_x86_64.tar.gz"
darwin_x86_64 = "xxx_{version}_darwin_x86_64.tar.gz"

[tools.xxx.package_manager_commands]
apt = "fdfind"
brew = "fd"
default = "fd"
```

### 配置文件 (type = "dotfile")

```toml
[tools.nvim-config]
type = "dotfile"              # 工具类型：dotfile
name = "nvim-config"
description = "My Neovim configuration"
config_repo = "moecly/nvim-config"  # GitHub 仓库
config_branch = "main"       # 可选，默认 main
links = [
    { glob = "nvim", to = "~/.config/nvim" },
]
exclude = ["*.md", "README.md", ".git"]

[tools.zsh-config]
type = "dotfile"
name = "zsh-config"
config_repo = "moecly/zsh-config"
links = [
    { glob = ".zshrc", to = "~/.zshrc" },
    { glob = ".zprofile", to = "~/.zprofile" },
    { glob = ".config/zsh/*", to = "~/.config/zsh/" },
]
exclude = ["*.md"]

[tools.tmux-config]
type = "dotfile"
name = "tmux-config"
config_repo = "moecly/tmux_config"
links = [
    { glob = ".tmux.conf", to = "~/.tmux.conf" },
]
```

### links 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `glob` | string | 仓库内文件/目录的 glob 匹配模式 |
| `to` | string | 目标路径，支持 `~` 展开 |
| `to_linux` | string | Linux 平台目标路径（可选） |
| `to_macos` | string | macOS 平台目标路径（可选） |
| `to_windows` | string | Windows 平台目标路径（可选） |

**平台差异化示例**：
```toml
[tools.nvim-config]
type = "dotfile"
links = [
    { 
        glob = "*", 
        to = "~/.config/nvim",
        to_linux = "~/.config/nvim",
        to_macos = "~/.config/nvim",
        to_windows = "~/AppData/Local/nvim"
    },
]
```

### exclude 字段说明

使用 glob 语法排除文件，如 `["*.md", ".git", "LICENSE"]`

### bin_entries 字段说明

指定解压后哪些可执行文件需要创建软链接到 bin 目录：

| 字段 | 类型 | 说明 |
|------|------|------|
| `bin_entries` | list[string] | 可执行文件名列表（不含扩展名） |

**示例**：下载的压缩包包含多个可执行文件，只链接指定的：
```toml
[tools.my-tool]
type = "binary"
name = "my-tool"
bin_entries = ["my-tool", "my-tool-gui"]  # 创建两个软链接
```

### 扩展安装器

#### 自定义脚本安装 (custom_script)

```toml
[tools.fzf]
type = "binary"
name = "fzf"
display_name = "FZF"
description = "General-purpose command-line fuzzy finder"
installable_by = ["custom_script", "github", "package_manager"]
custom_script = "git clone --depth 1 https://github.com/junegunn/fzf.git ~/.quick-env/tools/fzf_src && ~/.quick-env/tools/fzf_src/install --all"
custom_version_cmd = "fzf --version"
priority.custom_script = 5
priority.github = 10
priority.package_manager = 30
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `custom_script` | string | 自定义安装脚本（shell 命令） |
| `custom_version_cmd` | string | 版本检测命令（可选） |

#### 自定义 URL 安装 (custom_url)

```toml
[tools.delta]
type = "binary"
name = "delta"
display_name = "Delta"
description = "Syntax-highlighting pager for git"
installable_by = ["custom_url", "github"]
custom_url = "https://github.com/dandavison/delta/releases/download/0.18.1/delta-0.18.1-x86_64-unknown-linux-musl.tar.gz"
custom_url_extract = true
custom_version_cmd = "delta --version"
priority.custom_url = 5
priority.github = 10
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `custom_url` | string | 自定义下载 URL |
| `custom_url_extract` | bool | 是否自动解压（默认 true） |
| `custom_version_cmd` | string | 版本检测命令（可选） |

## 安装器架构

### 安装器类型

| 类型 | 标识符 | 说明 |
|------|--------|------|
| GitHub Release | `github` | 从 GitHub Release 下载 |
| 包管理器 | `package_manager` | apt/brew/dnf 等 |
| Dotfile | `dotfile` | Git clone + symlink |
| 自定义脚本 | `custom_script` | 执行自定义 shell 脚本 |
| 自定义 URL | `custom_url` | 从自定义 URL 下载 |

### InstallerRegistry

安装器使用注册表模式管理，支持内置 + 插件扩展：

```python
from quick_env.installer import InstallerRegistry, Installer

class MyInstaller(Installer):
    name = "my_installer"
    # ...

InstallerRegistry.register("my_installer", MyInstaller)
```

### 插件机制

用户可在 `~/.quick-env/plugins/` 目录下放置插件：

```python
# ~/.quick-env/plugins/my_installers.py
from quick_env.installer import InstallerRegistry, Installer

class MyInstaller(Installer):
    name = "my_installer"
    priority = 1
    # 实现抽象方法...

InstallerRegistry.register("my_installer", MyInstaller)
```

## 添加新工具流程

**添加新二进制工具**（无需修改代码）：
```toml
[tools.fzf]
type = "binary"
name = "fzf"
installable_by = ["github", "package_manager"]
repo = "junegunn/fzf"
# ... github_asset_patterns
```

**添加新配置文件**（无需修改代码）：
```toml
[tools.vim-config]
type = "dotfile"
name = "vim-config"
config_repo = "yourusername/vim-config"
links = [
    { glob = "vimrc", to = "~/.vimrc" },
]
```

**添加自定义脚本安装**（无需修改代码）：
```toml
[tools.my-tool]
type = "binary"
name = "my-tool"
installable_by = ["custom_script"]
custom_script = "curl -L https://example.com/install.sh | bash"
```

**添加自定义 URL 安装**（无需修改代码）：
```toml
[tools.my-tool]
type = "binary"
name = "my-tool"
installable_by = ["custom_url"]
custom_url = "https://example.com/tool.tar.gz"
custom_url_extract = true
```

## 安装方式优先级

在 `tools.toml` 中配置：

```toml
[tools.nvim]
type = "binary"
installable_by = ["github", "package_manager"]
priority.github = 10           # 数字越小优先级越高
priority.package_manager = 30
```

默认优先级（未配置时）：
- custom_script: 5
- custom_url: 10
- github: 10
- git_clone: 10
- package_manager: 30

## CLI 命令

```bash
quick-env init              # 初始化配置
quick-env install <tool>    # 安装工具
quick-env install all       # 安装全部（并发）
quick-env install <tool> --force  # 强制重新安装
quick-env install <tool> -m github # 指定安装方式
quick-env install all -P     # 并行安装全部
quick-env uninstall <tool>  # 卸载工具（只删 quick-env 的）
quick-env upgrade <tool>    # 升级工具
quick-env list              # 列出已安装
quick-env list all          # 列出全部
quick-env list --updates    # 显示有更新的
quick-env info <tool>       # 查看详情
quick-env doctor            # 系统检查
quick-env doctor --fix      # 自动修复检测到的问题
quick-env config show       # 显示配置
quick-env config edit       # 编辑配置
```

## 核心逻辑

### 安装逻辑
1. 按 `type` 区分工具类型
2. `binary`: 按 `installable_by` + `priority` 选择安装方式
3. `dotfile`: Git clone + glob 链接
4. 已安装的工具会跳过安装（使用 `--force` 强制重新安装）
5. 下载到 cache/，解压到 tools/<tool>_<version>/
6. 创建 bin/<tool> 入口（软链接或 .cmd 脚本）

### 版本检测逻辑
1. 按 `installable_by` + `priority` 顺序检测
2. 优先用配置中的优先级，没有则用默认值
3. 先检查系统 PATH，找不到再检查 `~/.quick-env/bin/`

### 卸载逻辑
- **binary**: 删除 `~/.quick-env/bin/<tool>` 入口 + `~/.quick-env/tools/<tool>_<version>/`
- **dotfile**: 删除 `~/.quick-env/dotfiles/<name>/` + 用户目录的符号链接
- 不影响系统包管理器安装的工具

## 注意事项

1. `installable_by` 只是声明支持哪些安装方式，实际选择由 `get_best_installer()` 按优先级决定
2. `{version}` 在 github_asset_patterns 中会被替换为实际版本号
3. asset 名称区分大小写，需与 GitHub Release 页面一致
4. 日志保留 7 天，按天存储在 `~/.quick-env/logs/` 目录
5. 配置文件修改后需要重启或重新加载
6. dotfile 链接目标已存在时，会备份为 `.bak` 再创建链接
7. glob 匹配保持目录结构

## 平台差异化处理

所有平台差异化逻辑统一在 `Platform` 类中处理：

```python
# platform.py
@dataclass
class Platform:
    # 基础检测
    is_windows: bool
    is_macos: bool
    is_linux: bool
    is_git_bash: bool
    is_wsl: bool
    is_msys: bool  # Git Bash / MSYS2 环境

    # 统一入口方法
    def exe_name(self, name: str) -> str:
        """可执行文件名（带后缀）"""

    def bin_name(self, name: str) -> str:
        """bin 入口文件名"""

    def find_exe(self, directory: Path, name: str) -> Optional[Path]:
        """在目录中查找可执行文件"""

    def is_bin_installed(self, bin_dir: Path, name: str) -> bool:
        """检测 bin 入口是否存在"""

    def install_bin_entry(self, bin_path: Path, target: Path) -> None:
        """创建 bin 入口（软链接或 .cmd 脚本）"""

    def remove_bin_entry(self, bin_path: Path) -> None:
        """删除 bin 入口"""

    def get_bin_executable_path(self, bin_dir: Path, name: str) -> Optional[Path]:
        """获取 bin 入口指向的可执行文件路径"""
```

### 平台差异说明

| 平台 | exe_name | bin_name | install_bin_entry |
|------|----------|----------|-------------------|
| Linux/macOS/WSL | `tool` | `tool` | 软链接 |
| Git Bash/MSYS2 | `tool.exe` | `tool.cmd` | .cmd 脚本 |
