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

- 无

## 目录结构

```
~/.quick-env/
├── bin/           # 软链接/脚本入口
├── cache/         # 下载缓存（压缩包）
├── data/          # 解压后的完整目录
├── logs/          # 日志文件（按天存储，保留 7 天）
└── configs/
    └── tools.toml  # 用户配置
```

### 安装结构说明

- **Linux/macOS/WSL**: `bin/lazygit` → `../data/lazygit_0.40.0/lazygit`（软链接）
- **Git Bash/MSYS2**: `bin/lazygit.cmd` → 调用 `../data/lazygit_0.40.0/lazygit.exe`
- **Windows 原生**: 使用 `.cmd` 脚本（同 Git Bash）

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
quick-env install <tool> --force  # 强制重新安装
quick-env install <tool> -m github # 指定安装方式
quick-env uninstall <tool>  # 卸载工具（只删 quick-env 的）
quick-env upgrade <tool>    # 升级工具
quick-env list              # 列出已安装
quick-env list all          # 列出全部
quick-env list --updates    # 显示有更新的
quick-env info <tool>       # 查看详情
quick-env doctor            # 系统检查
quick-env config show       # 显示配置
quick-env config edit       # 编辑配置
```

## 核心逻辑

### 安装逻辑
1. 按 `installable_by` + `priority` 选择安装方式
2. 已安装的工具会跳过安装（使用 `--force` 强制重新安装）
3. 下载到 cache/，解压到 data/<tool>_<version>/
4. 创建 bin/<tool> 入口（软链接或 .cmd 脚本）
5. 清理旧版本目录

### 版本检测逻辑
1. 按 `installable_by` + `priority` 顺序检测
2. 优先用配置中的优先级，没有则用默认值
3. 先检查系统 PATH，找不到再检查 `~/.quick-env/bin/`

### 卸载逻辑
- 删除 `~/.quick-env/bin/<tool>` 入口
- 删除 `~/.quick-env/data/<tool>_<version>/` 目录
- 不影响系统包管理器安装的工具

## 注意事项

1. `installable_by` 只是声明支持哪些安装方式，实际选择由 `get_best_installer()` 按优先级决定
2. `{version}` 在 github_asset_patterns 中会被替换为实际版本号
3. asset 名称区分大小写，需与 GitHub Release 页面一致
4. 日志保留 7 天，按天存储在 `~/.quick-env/logs/` 目录
5. 配置文件修改后需要重启或重新加载

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
