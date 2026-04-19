#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GodView 一键安装脚本
支持 Windows/Linux/macOS + Conda/非Conda 环境
包含数据库自动安装和启动
"""

import os
import sys
import subprocess
import platform
import shutil
import json
import urllib.request
import tarfile
import zipfile
import time
from pathlib import Path
from typing import Optional, List, Tuple, Dict

# 修复 Windows 控制台编码
if platform.system() == 'Windows':
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.system('chcp 65001 >nul 2>&1')

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def print_banner():
    banner = f"""
{Colors.BLUE}{Colors.BOLD}
================================================================
   ██████╗  ██████╗ ██████╗ ███████╗██╗      ██████╗ ███████╗
   ██╔══██╗██╔═══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██╔════╝
   ██████╔╝██║   ██║██║  ██║█████╗  ██║     ██║   ██║███████╗
   ██╔══██╗██║   ██║██║  ██║██╔══╝  ██║     ██║   ██║╚════██║
   ██║  ██║╚██████╔╝██████╔╝███████╗███████╗╚██████╔╝███████║
   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝ ╚═════╝ ╚══════╝

           AI 驱动的小说生成系统 - 安装向导
================================================================
{Colors.END}
"""
    print(banner)

def print_step(step: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}[步骤] {step}{Colors.END}\n")

def print_success(msg: str):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.END}")

def print_error(msg: str):
    print(f"{Colors.RED}[ERROR] {msg}{Colors.END}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.END}")

def print_info(msg: str):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.END}")

def print_menu(options: List[str], title: str = "") -> int:
    """打印菜单并获取用户选择"""
    if title:
        print(f"\n{Colors.BOLD}{title}{Colors.END}\n")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print()
    while True:
        try:
            choice = input("请选择 [输入数字]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
            print_error("无效选项")
        except ValueError:
            print_error("请输入数字")

def run_command(cmd: List[str] or str, cwd: Optional[str] = None, capture: bool = False,
                shell: bool = False, env: Optional[Dict] = None, timeout: int = 300) -> Tuple[bool, str]:
    try:
        if isinstance(cmd, str):
            shell = True
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            shell=shell,
            env=env or os.environ.copy(),
            timeout=timeout
        )
        if capture:
            return result.returncode == 0, result.stdout + result.stderr
        return result.returncode == 0, ""
    except subprocess.TimeoutExpired:
        return False, "命令执行超时"
    except Exception as e:
        return False, str(e)

def check_command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def get_python_version() -> Optional[Tuple[int, int]]:
    try:
        result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
        version_str = result.stdout.strip().split()[1]
        major, minor = map(int, version_str.split('.')[:2])
        return (major, minor)
    except:
        return None

def download_file(url: str, dest: Path, desc: str = "") -> bool:
    """下载文件带进度显示"""
    try:
        print_info(f"下载 {desc or dest.name}...")

        def progress_hook(count, block_size, total_size):
            percent = min(int(count * block_size * 100 / total_size), 100)
            sys.stdout.write(f"\r  进度: {percent}%")
            sys.stdout.flush()

        urllib.request.urlretrieve(url, dest, progress_hook)
        print()  # 换行
        print_success(f"下载完成: {dest.name}")
        return True
    except Exception as e:
        print_error(f"下载失败: {e}")
        return False

def is_admin() -> bool:
    """检查是否有管理员权限"""
    if platform.system() == 'Windows':
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    else:
        return os.geteuid() == 0

def confirm_dangerous_action(message: str) -> bool:
    """确认危险操作"""
    print()
    print_warning(f"⚠️  {message}")
    print_warning("此操作不可撤销！")
    print()
    response = input("请输入 'CONFIRM' 来确认操作: ").strip()
    return response == 'CONFIRM'


class DockerInstaller:
    """Docker 自动安装器"""

    DOCKER_DESKTOP_URL = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
    DOCKER_DESKTOP_MAC_URL = "https://desktop.docker.com/mac/main/arm64/Docker.dmg"

    def __init__(self):
        self.system = platform.system()
        self.is_windows = self.system == 'Windows'
        self.is_linux = self.system == 'Linux'
        self.is_mac = self.system == 'Darwin'

    def check_docker_installed(self) -> bool:
        """检查 Docker 是否已安装"""
        return check_command_exists('docker')

    def check_docker_running(self) -> bool:
        """检查 Docker 服务是否运行"""
        success, _ = run_command(['docker', 'info'], capture=True)
        return success

    def check_docker_compose(self) -> bool:
        """检查 docker-compose 是否可用"""
        # 尝试新版命令
        success, _ = run_command(['docker', 'compose', 'version'], capture=True)
        if success:
            return True
        # 尝试旧版命令
        success, _ = run_command(['docker-compose', '--version'], capture=True)
        return success

    def install_docker_windows(self) -> bool:
        """在 Windows 上自动安装 Docker Desktop"""
        print_step("安装 Docker Desktop (Windows)")

        # 检查是否已安装
        if self.check_docker_installed():
            print_success("Docker 已安装")
            return True

        # 检查管理员权限
        if not is_admin():
            print_warning("需要管理员权限来安装 Docker Desktop")
            print_info("正在以管理员权限重新启动...")
            try:
                import ctypes
                script = os.path.abspath(__file__)
                params = ' '.join([script] + sys.argv[1:])
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
                sys.exit(0)
            except Exception as e:
                print_error(f"无法获取管理员权限: {e}")
                print_info("请右键点击此脚本，选择'以管理员身份运行'")
                return self._manual_install_windows()

        # 检查 WSL2
        print_info("检查 WSL2...")
        success, output = run_command(['wsl', '--status'], capture=True)
        if not success:
            print_info("安装 WSL2...")
            run_command(['wsl', '--install', '-d', 'Ubuntu'], capture=True)
            print_warning("WSL2 安装需要重启电脑，重启后请再次运行此脚本")
            print_info("或者手动运行: wsl --install -d Ubuntu")
            return False

        # 下载 Docker Desktop
        download_dir = Path(os.environ.get('TEMP', os.path.expanduser('~')))
        installer_path = download_dir / "DockerDesktopInstaller.exe"

        if not download_file(self.DOCKER_DESKTOP_URL, installer_path, "Docker Desktop Installer"):
            return self._manual_install_windows()

        # 运行安装程序
        print_info("正在安装 Docker Desktop（可能需要几分钟）...")
        print_info("请在弹出的安装向导中完成安装...")

        success, output = run_command(
            [str(installer_path), "install", "--quiet", "--accept-license"],
            capture=True,
            timeout=600  # 10分钟超时
        )

        # 清理安装程序
        try:
            installer_path.unlink(missing_ok=True)
        except:
            pass

        if success or self.check_docker_installed():
            print_success("Docker Desktop 安装成功")
            print_warning("请重启电脑以完成安装，然后启动 Docker Desktop")
            return True
        else:
            print_warning("自动安装可能未完成")
            return self._manual_install_windows()

    def _manual_install_windows(self) -> bool:
        """Windows 手动安装引导"""
        print()
        print_info("请按以下步骤手动安装 Docker Desktop:")
        print()
        print("1. 访问: https://www.docker.com/products/docker-desktop")
        print("2. 下载 Windows 版本")
        print("3. 运行安装程序（需要管理员权限）")
        print("4. 确保启用 WSL2 后端")
        print("5. 重启电脑")
        print("6. 启动 Docker Desktop")
        print()

        choice = input("安装完成后按回车继续，或输入 's' 跳过: ").strip().lower()
        if choice == 's':
            return False

        return self.check_docker_installed()

    def install_docker_linux(self) -> bool:
        """在 Linux 上自动安装 Docker"""
        print_step("安装 Docker (Linux)")

        if self.check_docker_installed():
            print_success("Docker 已安装")
            return self._ensure_docker_service()

        # 检测发行版
        distro = self._detect_linux_distro()

        if distro == 'debian' or distro == 'ubuntu':
            return self._install_docker_debian()
        elif distro == 'rhel' or distro == 'centos' or distro == 'fedora':
            return self._install_docker_rhel()
        elif distro == 'arch':
            return self._install_docker_arch()
        else:
            return self._manual_install_linux()

    def _detect_linux_distro(self) -> str:
        """检测 Linux 发行版"""
        try:
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release') as f:
                    content = f.read().lower()
                    if 'ubuntu' in content or 'debian' in content:
                        return 'debian' if 'debian' in content else 'ubuntu'
                    elif 'centos' in content or 'rhel' in content or 'red hat' in content:
                        return 'rhel'
                    elif 'fedora' in content:
                        return 'fedora'
                    elif 'arch' in content:
                        return 'arch'
        except:
            pass
        return 'unknown'

    def _install_docker_debian(self) -> bool:
        """Debian/Ubuntu 安装 Docker"""
        print_info("检测到 Debian/Ubuntu 系统")

        commands = [
            # 更新包索引
            ('apt-get', 'update'),
            # 安装依赖
            ('apt-get', 'install', '-y', 'ca-certificates', 'curl', 'gnupg', 'lsb-release'),
        ]

        for cmd in commands:
            print_info(f"执行: {' '.join(cmd)}")
            success, output = run_command(cmd, capture=True)
            if not success:
                print_warning(f"命令执行失败，继续尝试...")

        # 添加 Docker 官方 GPG 密钥
        print_info("添加 Docker GPG 密钥...")
        keyring_path = '/usr/share/keyrings/docker.gpg'

        # 下载并添加 GPG 密钥
        gpg_cmd = f'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o {keyring_path}'
        run_command(gpg_cmd, capture=True)

        # 添加仓库
        print_info("添加 Docker 仓库...")
        release = subprocess.run(['lsb_release', '-cs'], capture_output=True, text=True).stdout.strip()
        repo_cmd = f'echo "deb [arch=$(dpkg --print-architecture) signed-by={keyring_path}] https://download.docker.com/linux/ubuntu {release} stable" | tee /etc/apt/sources.list.d/docker.list'
        run_command(repo_cmd, capture=True)

        # 安装 Docker
        print_info("安装 Docker...")
        install_cmds = [
            ('apt-get', 'update'),
            ('apt-get', 'install', '-y', 'docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-buildx-plugin', 'docker-compose-plugin'),
        ]

        for cmd in install_cmds:
            print_info(f"执行: {' '.join(cmd)}")
            success, output = run_command(cmd, capture=True, timeout=600)
            if not success:
                print_warning(f"安装可能失败: {output[:200]}")

        return self._post_install_linux()

    def _install_docker_rhel(self) -> bool:
        """RHEL/CentOS/Fedora 安装 Docker"""
        print_info("检测到 RHEL/CentOS/Fedora 系统")

        # 检测包管理器
        if check_command_exists('dnf'):
            pkg_mgr = 'dnf'
        else:
            pkg_mgr = 'yum'

        commands = [
            (pkg_mgr, 'install', '-y', 'yum-utils'),
            (pkg_mgr, 'config-manager', '--add-repo', 'https://download.docker.com/linux/centos/docker-ce.repo'),
            (pkg_mgr, 'install', '-y', 'docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-buildx-plugin', 'docker-compose-plugin'),
        ]

        for cmd in commands:
            print_info(f"执行: {' '.join(cmd)}")
            success, output = run_command(cmd, capture=True, timeout=600)
            if not success:
                print_warning(f"命令执行失败，继续尝试...")

        return self._post_install_linux()

    def _install_docker_arch(self) -> bool:
        """Arch Linux 安装 Docker"""
        print_info("检测到 Arch Linux 系统")

        commands = [
            ('pacman', '-Sy', '--noconfirm', 'docker', 'docker-compose'),
        ]

        for cmd in commands:
            print_info(f"执行: {' '.join(cmd)}")
            success, output = run_command(cmd, capture=True, timeout=600)
            if not success:
                print_warning(f"命令执行失败，继续尝试...")

        return self._post_install_linux()

    def _post_install_linux(self) -> bool:
        """Linux Docker 安装后配置"""
        # 启动 Docker 服务
        print_info("启动 Docker 服务...")
        run_command(['systemctl', 'start', 'docker'], capture=True)
        run_command(['systemctl', 'enable', 'docker'], capture=True)

        # 添加当前用户到 docker 组
        print_info("添加当前用户到 docker 组...")
        run_command(['usermod', '-aG', 'docker', os.environ.get('USER', '')], capture=True)

        if self.check_docker_installed():
            print_success("Docker 安装成功")
            print_warning("可能需要重新登录或运行 'newgrp docker' 来使用户组生效")
            return True

        return False

    def _ensure_docker_service(self) -> bool:
        """确保 Docker 服务运行"""
        if self.check_docker_running():
            return True

        print_info("启动 Docker 服务...")
        run_command(['systemctl', 'start', 'docker'], capture=True)
        return self.check_docker_running()

    def _manual_install_linux(self) -> bool:
        """Linux 手动安装引导"""
        print()
        print_info("无法自动检测您的系统，请手动安装 Docker:")
        print()
        print("Ubuntu/Debian:")
        print("  curl -fsSL https://get.docker.com | sh")
        print()
        print("CentOS/RHEL:")
        print("  yum install -y docker-ce docker-ce-cli containerd.io")
        print()
        print("Arch Linux:")
        print("  pacman -S docker docker-compose")
        print()
        print("或访问: https://docs.docker.com/engine/install/")
        print()

        choice = input("安装完成后按回车继续，或输入 's' 跳过: ").strip().lower()
        if choice == 's':
            return False

        return self.check_docker_installed()

    def install_docker_mac(self) -> bool:
        """在 macOS 上安装 Docker Desktop"""
        print_step("安装 Docker Desktop (macOS)")

        if self.check_docker_installed():
            print_success("Docker 已安装")
            return True

        # 检查 Homebrew
        if check_command_exists('brew'):
            print_info("使用 Homebrew 安装 Docker Desktop...")
            success, output = run_command(['brew', 'install', '--cask', 'docker'], capture=True, timeout=600)
            if success or self.check_docker_installed():
                print_success("Docker Desktop 安装成功")
                print_info("请启动 Docker Desktop 应用")
                return True

        # 手动安装引导
        print()
        print_info("请按以下步骤安装 Docker Desktop:")
        print()
        print("1. 访问: https://www.docker.com/products/docker-desktop")
        print("2. 下载 macOS 版本 (Apple Silicon 或 Intel)")
        print("3. 打开 DMG 文件并拖拽到 Applications")
        print("4. 启动 Docker Desktop")
        print()

        choice = input("安装完成后按回车继续，或输入 's' 跳过: ").strip().lower()
        if choice == 's':
            return False

        return self.check_docker_installed()

    def install(self) -> bool:
        """自动安装 Docker"""
        if self.check_docker_installed() and self.check_docker_running():
            print_success("Docker 已安装并运行")
            return True

        if self.is_windows:
            return self.install_docker_windows()
        elif self.is_linux:
            return self.install_docker_linux()
        elif self.is_mac:
            return self.install_docker_mac()
        else:
            print_error(f"不支持的操作系统: {self.system}")
            return False

    def wait_for_docker(self, timeout: int = 60) -> bool:
        """等待 Docker 服务启动"""
        print_info("等待 Docker 服务启动...")

        for i in range(timeout):
            if self.check_docker_running():
                print_success("Docker 服务已启动")
                return True
            time.sleep(1)
            if i % 5 == 0:
                print_info(f"等待中... ({i}/{timeout}s)")

        print_error("Docker 服务启动超时")
        return False


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.data_dir = project_dir / "data"
        self.docker_compose_file = project_dir / "docker-compose.yml"
        self.init_sql_dir = project_dir / "init" / "sql"
        self.is_windows = platform.system() == 'Windows'
        self.docker_installer = DockerInstaller()

    def setup_data_directories(self) -> bool:
        """创建数据持久化目录"""
        print_info("创建数据持久化目录...")

        directories = [
            self.data_dir,
            self.data_dir / "postgres",
            self.data_dir / "qdrant",
            self.data_dir / "nebula" / "meta",
            self.data_dir / "nebula" / "storage",
            self.init_sql_dir,
        ]

        for d in directories:
            try:
                d.mkdir(parents=True, exist_ok=True)
                print_success(f"创建目录: {d.relative_to(self.project_dir)}")
            except Exception as e:
                print_error(f"创建目录失败 {d}: {e}")
                return False

        return True

    def check_docker(self) -> bool:
        """检查 Docker 是否安装"""
        if self.docker_installer.check_docker_installed():
            success, output = run_command(['docker', '--version'], capture=True)
            if success:
                print_success(f"Docker 已安装: {output.strip()}")
                return True
        print_warning("未检测到 Docker")
        return False

    def check_docker_running(self) -> bool:
        """检查 Docker 是否运行"""
        return self.docker_installer.check_docker_running()

    def check_docker_compose(self) -> bool:
        """检查 docker-compose 是否可用"""
        return self.docker_installer.check_docker_compose()

    def install_docker(self) -> bool:
        """安装 Docker"""
        return self.docker_installer.install()

    def create_init_scripts(self) -> bool:
        """创建数据库初始化脚本"""
        print_info("创建数据库初始化脚本...")

        # PostgreSQL 初始化脚本
        init_sql = """-- GodView 数据库初始化脚本
-- 自动生成于安装过程

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 用于模糊搜索
CREATE EXTENSION IF NOT EXISTS "vector";   -- pgvector 向量搜索扩展

-- ================== 项目表 ==================
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ================== 小说章节表 ==================
CREATE TABLE IF NOT EXISTS chapters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    chapter_order INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'draft',
    word_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chapters_project ON chapters(project_id);
CREATE INDEX idx_chapters_status ON chapters(status);

-- ================== 角色表 ==================
CREATE TABLE IF NOT EXISTS characters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100),  -- 主角、配角、反派等
    description TEXT,
    traits JSONB DEFAULT '{}',
    voice_settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_characters_project ON characters(project_id);

-- ================== 世界设定表 ==================
CREATE TABLE IF NOT EXISTS world_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    category VARCHAR(100),  -- 地理、历史、文化、魔法系统等
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_world_project ON world_settings(project_id);
CREATE INDEX idx_world_category ON world_settings(category);

-- ================== 剧情线表 ==================
CREATE TABLE IF NOT EXISTS plot_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    plot_type VARCHAR(100),  -- 主线、支线、暗线
    status VARCHAR(50) DEFAULT 'planning',
    chapter_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_plot_project ON plot_lines(project_id);

-- ================== 钩子表 ==================
CREATE TABLE IF NOT EXISTS hooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
    hook_type VARCHAR(100),  -- 悬念、伏笔、转折
    description TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_chapter_id UUID,
    importance INTEGER DEFAULT 5,  -- 1-10
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_hooks_project ON hooks(project_id);
CREATE INDEX idx_hooks_chapter ON hooks(chapter_id);

-- ================== 干预记录表 ==================
CREATE TABLE IF NOT EXISTS interventions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
    intervention_type VARCHAR(100),  -- 剧情、角色、节奏
    trigger_condition TEXT,
    action_taken TEXT,
    result TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_interventions_project ON interventions(project_id);

-- ================== 技能表 ==================
CREATE TABLE IF NOT EXISTS skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    skill_type VARCHAR(100),
    level INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skills_project ON skills(project_id);
CREATE INDEX idx_skills_character ON skills(character_id);

-- ================== 设定条目表 (Lore) ==================
CREATE TABLE IF NOT EXISTS lore_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    category VARCHAR(100),
    priority VARCHAR(20) DEFAULT 'standard',
    content TEXT,
    summary TEXT DEFAULT '',
    keywords JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    constraints JSONB DEFAULT '[]',
    related_characters JSONB DEFAULT '[]',
    related_locations JSONB DEFAULT '[]',
    related_items JSONB DEFAULT '[]',
    forbidden_actions JSONB DEFAULT '[]',
    source TEXT DEFAULT '',
    importance INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_lore_project ON lore_entries(project_id);
CREATE INDEX idx_lore_category ON lore_entries(category);
CREATE INDEX idx_lore_tags ON lore_entries USING GIN(tags);

-- ================== 对话历史表 ==================
CREATE TABLE IF NOT EXISTS conversation_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
    role VARCHAR(50),  -- user, assistant, character
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_conversation_project ON conversation_history(project_id);
CREATE INDEX idx_conversation_character ON conversation_history(character_id);

-- ================== 向量嵌入缓存表 ==================
CREATE TABLE IF NOT EXISTS embedding_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding_model VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX idx_embedding_entity ON embedding_cache(entity_type, entity_id);

-- ================== 世界表 ==================
CREATE TABLE IF NOT EXISTS worlds (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    world_type VARCHAR(50) DEFAULT 'fantasy',
    tone VARCHAR(50) DEFAULT 'serious',
    content_styles JSONB DEFAULT '[]',
    protagonist_types JSONB DEFAULT '[]',
    character_archetypes JSONB DEFAULT '[]',
    power_types JSONB DEFAULT '[]',
    rules JSONB DEFAULT '[]',
    power_system TEXT,
    technology_level TEXT,
    history TEXT,
    geography TEXT,
    factions JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_worlds_project ON worlds(project_id);

-- ================== 区域表 ==================
CREATE TABLE IF NOT EXISTS regions (
    id VARCHAR(64) PRIMARY KEY,
    world_id VARCHAR(64),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    region_type VARCHAR(50) DEFAULT 'custom',
    terrain_type VARCHAR(50) DEFAULT 'custom',
    description TEXT,
    atmosphere TEXT,
    coordinates JSONB,
    area_size FLOAT,
    terrain_features JSONB DEFAULT '[]',
    landmarks JSONB DEFAULT '[]',
    encounters JSONB DEFAULT '[]',
    connections JSONB DEFAULT '[]',
    local_rules JSONB DEFAULT '[]',
    is_generated BOOLEAN DEFAULT FALSE,
    visit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_regions_world ON regions(world_id);
CREATE INDEX idx_regions_project ON regions(project_id);

-- ================== 章节大纲表 ==================
CREATE TABLE IF NOT EXISTS chapter_outlines (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    scenes JSONB DEFAULT '[]',
    emotion_curve JSONB,
    chapter_goals JSONB DEFAULT '[]',
    plot_advancement TEXT,
    character_arcs JSONB DEFAULT '{}',
    hooks_planted JSONB DEFAULT '[]',
    hooks_resolved JSONB DEFAULT '[]',
    quality_metrics JSONB DEFAULT '{}',
    target_word_count INTEGER DEFAULT 3000,
    estimated_word_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP WITH TIME ZONE,
    approved_by VARCHAR(255),
    previous_outline_id VARCHAR(64),
    next_outline_id VARCHAR(64)
);

CREATE INDEX idx_chapter_outlines_project ON chapter_outlines(project_id);
CREATE INDEX idx_chapter_outlines_chapter ON chapter_outlines(chapter_number);

-- ================== 卷大纲表 ==================
CREATE TABLE IF NOT EXISTS volume_outlines (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    volume_number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    chapter_range VARCHAR(50),
    main_plot TEXT,
    sub_plots JSONB DEFAULT '[]',
    key_events JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_volume_outlines_project ON volume_outlines(project_id);

-- ================== 反派表 ==================
CREATE TABLE IF NOT EXISTS villains (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    villain_type VARCHAR(100),
    threat_level INTEGER DEFAULT 5,
    evil_deeds JSONB DEFAULT '[]',
    weakness TEXT,
    motivation TEXT,
    defeat_condition TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_villains_project ON villains(project_id);
CREATE INDEX idx_villains_character ON villains(character_id);

-- ================== 伏笔表 ==================
CREATE TABLE IF NOT EXISTS foreshadowings (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
    hook_type VARCHAR(100),
    description TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_chapter_id UUID,
    importance INTEGER DEFAULT 5,
    foreshadow_type VARCHAR(50) DEFAULT 'suspense',
    plant_chapter INTEGER,
    resolve_chapter INTEGER,
    status VARCHAR(50) DEFAULT 'planted',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_foreshadowings_project ON foreshadowings(project_id);
CREATE INDEX idx_foreshadowings_chapter ON foreshadowings(chapter_id);

-- ================== 冲突表 ==================
CREATE TABLE IF NOT EXISTS conflicts (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
    conflict_type VARCHAR(100),
    description TEXT,
    intensity INTEGER DEFAULT 5,
    parties JSONB DEFAULT '[]',
    resolution TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_conflicts_project ON conflicts(project_id);
CREATE INDEX idx_conflicts_chapter ON conflicts(chapter_id);

-- ================== 事件摘要表 ==================
CREATE TABLE IF NOT EXISTS event_summaries (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
    event_type VARCHAR(100),
    summary TEXT,
    key_characters JSONB DEFAULT '[]',
    importance INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_event_summaries_project ON event_summaries(project_id);
CREATE INDEX idx_event_summaries_chapter ON event_summaries(chapter_id);

-- ================== 角色生命周期表 ==================
CREATE TABLE IF NOT EXISTS character_lifecycles (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    lifecycle_stage VARCHAR(100),
    stage_description TEXT,
    start_chapter INTEGER,
    end_chapter INTEGER,
    key_events JSONB DEFAULT '[]',
    growth_points JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_character_lifecycles_project ON character_lifecycles(project_id);
CREATE INDEX idx_character_lifecycles_character ON character_lifecycles(character_id);

-- ================== 角色技能关联表 ==================
CREATE TABLE IF NOT EXISTS character_skills (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    proficiency_level INTEGER DEFAULT 1,
    acquired_chapter INTEGER,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_character_skills_project ON character_skills(project_id);
CREATE INDEX idx_character_skills_character ON character_skills(character_id);
CREATE INDEX idx_character_skills_skill ON character_skills(skill_id);

-- ================== 全局状态表 ==================
CREATE TABLE IF NOT EXISTS global_state (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE UNIQUE,
    state_key VARCHAR(255) NOT NULL,
    state_value JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, state_key)
);

CREATE INDEX idx_global_state_project ON global_state(project_id);

-- ================== 全局状态历史表 ==================
CREATE TABLE IF NOT EXISTS global_state_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    state_key VARCHAR(255) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    change_reason TEXT,
    chapter_id UUID,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_global_state_history_project ON global_state_history(project_id);
CREATE INDEX idx_global_state_history_key ON global_state_history(state_key);

-- ================== 黄金三章规则表 ==================
CREATE TABLE IF NOT EXISTS golden_three_rules (
    id VARCHAR(64) PRIMARY KEY,
    rule_type VARCHAR(50) NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    description TEXT,
    check_points JSONB DEFAULT '[]',
    examples JSONB DEFAULT '[]',
    weight FLOAT DEFAULT 1.0,
    severity VARCHAR(50) DEFAULT 'important',
    applicable_genres JSONB DEFAULT '[]',
    applicable_chapter INTEGER DEFAULT 1,
    fix_suggestions JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_golden_three_rules_type ON golden_three_rules(rule_type);
CREATE INDEX idx_golden_three_rules_chapter ON golden_three_rules(applicable_chapter);

-- ================== 黄金三章检测结果表 ==================
CREATE TABLE IF NOT EXISTS golden_three_checks (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_results JSONB DEFAULT '{}',
    total_score FLOAT DEFAULT 0.0,
    hook_score FLOAT DEFAULT 0.0,
    conflict_score FLOAT DEFAULT 0.0,
    protagonist_score FLOAT DEFAULT 0.0,
    critical_issues JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    suggestions JSONB DEFAULT '[]',
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_golden_three_checks_project ON golden_three_checks(project_id);

-- ================== 干预日志表 ==================
CREATE TABLE IF NOT EXISTS intervention_logs (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    workflow_execution_id VARCHAR(64),
    node_id VARCHAR(64),
    agent_type VARCHAR(100),
    agent_name VARCHAR(255),
    intervention_type VARCHAR(50) DEFAULT 'guidance',
    user_message TEXT,
    agent_response TEXT,
    context_snapshot JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    response_time_ms INTEGER
);

CREATE INDEX idx_intervention_logs_project ON intervention_logs(project_id);
CREATE INDEX idx_intervention_logs_workflow ON intervention_logs(workflow_execution_id);

-- ================== 世界快照表 ==================
CREATE TABLE IF NOT EXISTS world_snapshots (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_number INTEGER,
    character_states JSONB DEFAULT '{}',
    active_hooks JSONB DEFAULT '[]',
    recent_events JSONB DEFAULT '[]',
    world_state JSONB DEFAULT '{}',
    key_memories JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_world_snapshots_project ON world_snapshots(project_id);
CREATE INDEX idx_world_snapshots_chapter ON world_snapshots(chapter_number);

-- ================== 记忆条目表 ==================
CREATE TABLE IF NOT EXISTS memory_entries (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    memory_type VARCHAR(50) DEFAULT 'medium_term',
    category VARCHAR(50) DEFAULT 'event',
    content TEXT,
    summary TEXT,
    chapter_number INTEGER,
    character_ids JSONB DEFAULT '[]',
    event_ids JSONB DEFAULT '[]',
    location_ids JSONB DEFAULT '[]',
    embedding VECTOR(384),
    importance_score FLOAT DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    source_type VARCHAR(50),
    source_agent VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_memory_entries_project ON memory_entries(project_id);
CREATE INDEX idx_memory_entries_type ON memory_entries(memory_type);
CREATE INDEX idx_memory_entries_category ON memory_entries(category);

-- ================== 记忆嵌入表 ==================
CREATE TABLE IF NOT EXISTS memory_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id VARCHAR(100) NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(100) NOT NULL,
    agent_id VARCHAR(100),
    content TEXT NOT NULL,
    content_hash VARCHAR(64),
    embedding JSONB DEFAULT NULL,
    memory_type VARCHAR(50),
    importance VARCHAR(50),
    tags JSONB DEFAULT '[]',
    access_count INT DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    last_used_in_chapter INT,
    last_used_context VARCHAR(200),
    decay_factor FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE NULLS NOT DISTINCT (memory_id, project_id, agent_type, agent_id)
);

CREATE INDEX idx_memory_embeddings_memory ON memory_embeddings(memory_id);
CREATE INDEX idx_memory_embeddings_project ON memory_embeddings(project_id);
CREATE INDEX idx_memory_embeddings_agent ON memory_embeddings(agent_type);
CREATE INDEX idx_memory_embeddings_project_agent_instance ON memory_embeddings(project_id, agent_type, agent_id);
CREATE INDEX idx_memory_embeddings_type ON memory_embeddings(memory_type);
CREATE INDEX idx_memory_embeddings_content_hash ON memory_embeddings(content_hash);

-- ================== 记忆衰减规则表 ==================
CREATE TABLE IF NOT EXISTS memory_decay_rules (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    memory_type VARCHAR(50),
    importance VARCHAR(50),
    initial_weight FLOAT DEFAULT 1.0,
    decay_rate FLOAT DEFAULT 0.1,
    min_weight FLOAT DEFAULT 0.1,
    access_boost FLOAT DEFAULT 0.1,
    max_decay_days INTEGER DEFAULT 90,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_memory_decay_rules_project ON memory_decay_rules(memory_type);

-- ================== 记忆上下文配置表 ==================
CREATE TABLE IF NOT EXISTS memory_context_configs (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    task_types JSONB DEFAULT '[]',
    agent_types JSONB DEFAULT '[]',
    selection_strategy VARCHAR(50) DEFAULT 'hybrid',
    max_memories INTEGER DEFAULT 10,
    type_weights JSONB DEFAULT '{"decision": 2.0, "observation": 1.0, "fact": 1.5}',
    time_decay_days INTEGER DEFAULT 30,
    time_decay_factor FLOAT DEFAULT 0.5,
    required_tags JSONB DEFAULT '[]',
    excluded_tags JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_memory_context_configs_project ON memory_context_configs USING GIN(agent_types);

-- ================== 记忆使用日志表 ==================
CREATE TABLE IF NOT EXISTS memory_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id VARCHAR(100) NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(100) NOT NULL,
    agent_id VARCHAR(100),
    usage_context VARCHAR(200),
    chapter_number INT,
    workflow_execution_id VARCHAR(100),
    workflow_node_id VARCHAR(100),
    relevance_score FLOAT,
    was_helpful BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_memory_usage_logs_project ON memory_usage_logs(project_id);
CREATE INDEX idx_memory_usage_logs_memory ON memory_usage_logs(memory_id);
CREATE INDEX idx_memory_usage_logs_project_agent_instance ON memory_usage_logs(project_id, agent_type, agent_id);
CREATE INDEX idx_memory_usage_logs_context ON memory_usage_logs(usage_context);
CREATE INDEX idx_memory_usage_logs_created ON memory_usage_logs(created_at);

CREATE TABLE IF NOT EXISTS token_usage (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    provider VARCHAR(100),
    model VARCHAR(100),
    category VARCHAR(50),
    agent_name VARCHAR(255),
    session_id VARCHAR(64),
    chapter_id UUID,
    character_id UUID,
    estimated_cost FLOAT DEFAULT 0.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_token_usage_project ON token_usage(project_id);
CREATE INDEX idx_token_usage_category ON token_usage(category);
CREATE INDEX idx_token_usage_created ON token_usage(created_at);

-- ================== Prompt模板表 ==================
CREATE TABLE IF NOT EXISTS prompt_templates (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    tags JSONB DEFAULT '[]',
    content TEXT NOT NULL,
    variables JSONB DEFAULT '[]',
    default_values JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 50,
    is_system BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_prompt_templates_category ON prompt_templates(category);
CREATE INDEX idx_prompt_templates_tags ON prompt_templates USING GIN(tags);

-- ================== 写作规则表 ==================
CREATE TABLE IF NOT EXISTS writing_rules (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(50) DEFAULT 'recommended',
    tags JSONB DEFAULT '[]',
    content TEXT NOT NULL,
    examples JSONB DEFAULT '[]',
    counter_examples JSONB DEFAULT '[]',
    conditions JSONB DEFAULT '[]',
    exceptions JSONB DEFAULT '[]',
    is_system BOOLEAN DEFAULT FALSE,
    version VARCHAR(20) DEFAULT '1.0.0',
    author VARCHAR(255),
    source VARCHAR(255),
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_writing_rules_category ON writing_rules(category);
CREATE INDEX idx_writing_rules_severity ON writing_rules(severity);

-- ================== 写作规则集表 ==================
CREATE TABLE IF NOT EXISTS writing_rule_sets (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_ids JSONB DEFAULT '[]',
    rule_overrides JSONB DEFAULT '{}',
    category VARCHAR(50) NOT NULL,
    tags JSONB DEFAULT '[]',
    target_genres JSONB DEFAULT '[]',
    is_system BOOLEAN DEFAULT FALSE,
    version VARCHAR(20) DEFAULT '1.0.0',
    author VARCHAR(255),
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_writing_rule_sets_category ON writing_rule_sets(category);

-- ================== 项目写作配置表 ==================
CREATE TABLE IF NOT EXISTS project_writing_configs (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE UNIQUE,
    enabled_rule_ids JSONB DEFAULT '[]',
    enabled_rule_set_ids JSONB DEFAULT '[]',
    rule_overrides JSONB DEFAULT '{}',
    rule_priorities JSONB DEFAULT '{}',
    default_severity VARCHAR(50) DEFAULT 'recommended',
    apply_to_chapters BOOLEAN DEFAULT TRUE,
    apply_to_characters BOOLEAN DEFAULT TRUE,
    apply_to_descriptions BOOLEAN DEFAULT TRUE,
    apply_to_narration BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    version VARCHAR(20) DEFAULT '1.0.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_project_writing_configs_project ON project_writing_configs(project_id);

-- ================== 满意度分析表 ==================
CREATE TABLE IF NOT EXISTS satisfaction_analyses (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    overall_score FLOAT DEFAULT 0.0,
    satisfaction_index FLOAT DEFAULT 0.0,
    detected_points JSONB DEFAULT '[]',
    pibu_burst_structures JSONB DEFAULT '[]',
    analysis_details JSONB DEFAULT '{}',
    suggestions JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_satisfaction_analyses_project ON satisfaction_analyses(project_id);
CREATE INDEX idx_satisfaction_analyses_chapter ON satisfaction_analyses(chapter_number);

-- ================== Agent模板表 ==================
CREATE TABLE IF NOT EXISTS agent_templates (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    agent_type VARCHAR(100) NOT NULL,
    tags JSONB DEFAULT '[]',
    prompt_slots JSONB DEFAULT '[]',
    default_prompt_order JSONB DEFAULT '[]',
    skill_slots JSONB DEFAULT '[]',
    default_skill_order JSONB DEFAULT '[]',
    default_model VARCHAR(100),
    default_temperature FLOAT DEFAULT 0.7,
    is_system BOOLEAN DEFAULT FALSE,
    is_optional BOOLEAN DEFAULT FALSE,
    is_enabled BOOLEAN DEFAULT TRUE,
    version VARCHAR(20) DEFAULT '1.0.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_templates_type ON agent_templates(agent_type);

-- ================== Agent记忆表 ==================
CREATE TABLE IF NOT EXISTS agent_memories (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(100) NOT NULL,
    agent_id VARCHAR(64),
    memories JSONB DEFAULT '[]',
    knowledge JSONB DEFAULT '{}',
    working_memory JSONB DEFAULT '{}',
    total_memories INTEGER DEFAULT 0,
    last_execution TIMESTAMP WITH TIME ZONE,
    execution_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_agent_in_project UNIQUE NULLS NOT DISTINCT (project_id, agent_type, agent_id)
);

CREATE INDEX idx_agent_memories_project ON agent_memories(project_id);
CREATE INDEX idx_agent_memories_type ON agent_memories(agent_type);
CREATE INDEX idx_agent_memories_project_type ON agent_memories(project_id, agent_type);

-- ================== Agent执行记录表 ==================
CREATE TABLE IF NOT EXISTS agent_execution_records (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(100) NOT NULL,
    agent_name VARCHAR(255),
    execution_type VARCHAR(50),
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    execution_time_ms INTEGER,
    token_used INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_execution_records_project ON agent_execution_records(project_id);
CREATE INDEX idx_agent_execution_records_type ON agent_execution_records(agent_type);

-- ================== Agent执行日志表 ==================
CREATE TABLE IF NOT EXISTS agent_execution_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    record_id VARCHAR(64) REFERENCES agent_execution_records(id) ON DELETE CASCADE,
    log_level VARCHAR(20) DEFAULT 'info',
    message TEXT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_execution_logs_record ON agent_execution_logs(record_id);

-- ================== Agent Prompt绑定表 ==================
CREATE TABLE IF NOT EXISTS agent_prompt_bindings (
    id VARCHAR(64) PRIMARY KEY,
    agent_template_id VARCHAR(64) REFERENCES agent_templates(id) ON DELETE CASCADE,
    prompt_template_id VARCHAR(64) REFERENCES prompt_templates(id) ON DELETE CASCADE,
    slot_name VARCHAR(100),
    priority INTEGER DEFAULT 50,
    is_enabled BOOLEAN DEFAULT TRUE,
    variable_overrides JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_prompt_bindings_agent ON agent_prompt_bindings(agent_template_id);
CREATE INDEX idx_agent_prompt_bindings_prompt ON agent_prompt_bindings(prompt_template_id);

-- ================== Skill执行表 ==================
CREATE TABLE IF NOT EXISTS skill_executions (
    id VARCHAR(64) PRIMARY KEY,
    skill_id VARCHAR(64) NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_id VARCHAR(64),
    input_params JSONB DEFAULT '{}',
    output_result TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    execution_time_ms INTEGER,
    token_usage JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skill_executions_skill ON skill_executions(skill_id);
CREATE INDEX idx_skill_executions_project ON skill_executions(project_id);

-- ================== Skill执行日志表 ==================
CREATE TABLE IF NOT EXISTS skill_execution_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    skill_execution_id VARCHAR(64) REFERENCES skill_executions(id) ON DELETE CASCADE,
    log_level VARCHAR(20) DEFAULT 'info',
    message TEXT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skill_execution_logs_execution ON skill_execution_logs(skill_execution_id);

-- ================== Skill分配表 ==================
CREATE TABLE IF NOT EXISTS skill_assignments (
    id VARCHAR(64) PRIMARY KEY,
    skill_id VARCHAR(64) NOT NULL,
    agent_type VARCHAR(100) NOT NULL,
    slot_name VARCHAR(100),
    custom_parameters JSONB,
    variable_overrides JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 50,
    execution_condition TEXT,
    is_enabled BOOLEAN DEFAULT TRUE,
    is_required BOOLEAN DEFAULT FALSE,
    load_mode VARCHAR(50),
    trigger_keywords JSONB DEFAULT '[]',
    assigned_by VARCHAR(50) DEFAULT 'user',
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skill_assignments_skill ON skill_assignments(skill_id);
CREATE INDEX idx_skill_assignments_agent ON skill_assignments(agent_type);

-- ================== Skill调用记录表 ==================
CREATE TABLE IF NOT EXISTS skill_call_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    skill_id VARCHAR(64) NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_id VARCHAR(64),
    call_context JSONB DEFAULT '{}',
    success BOOLEAN DEFAULT TRUE,
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skill_call_records_skill ON skill_call_records(skill_id);
CREATE INDEX idx_skill_call_records_project ON skill_call_records(project_id);

-- ================== 工作流定义表 ==================
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id VARCHAR(64) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    nodes JSONB DEFAULT '[]',
    edges JSONB DEFAULT '[]',
    variables JSONB DEFAULT '{}',
    is_template BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workflow_definitions_project ON workflow_definitions(project_id);
CREATE INDEX idx_workflow_definitions_template ON workflow_definitions(is_template);

-- ================== 工作流执行表 ==================
CREATE TABLE IF NOT EXISTS workflow_executions (
    id VARCHAR(64) PRIMARY KEY,
    workflow_id VARCHAR(64) REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    current_node VARCHAR(64),
    node_states JSONB DEFAULT '{}',
    context JSONB DEFAULT '{}',
    intervention_ids JSONB DEFAULT '[]',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    total_duration_ms INTEGER,
    error TEXT
);

CREATE INDEX idx_workflow_executions_workflow ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_project ON workflow_executions(project_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);

-- ================== 更新时间触发器 ==================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为需要的表添加触发器
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY['projects', 'chapters', 'characters', 'world_settings', 'plot_lines', 'lore_entries'])
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trigger_update_%s ON %s', t, t);
        EXECUTE format('CREATE TRIGGER trigger_update_%s BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION update_updated_at()', t, t);
    END LOOP;
END;
$$;

-- ================== 全文搜索索引 ==================
CREATE INDEX IF NOT EXISTS idx_chapters_content_fts ON chapters USING gin(to_tsvector('simple', coalesce(content, '')));
CREATE INDEX IF NOT EXISTS idx_characters_desc_fts ON characters USING gin(to_tsvector('simple', coalesce(description, '')));

-- 插入示例项目（可选）
INSERT INTO projects (name, description)
VALUES ('示例项目', '这是一个示例项目，您可以删除它或在其基础上开始创作')
ON CONFLICT DO NOTHING;

-- 完成
SELECT 'Database initialization completed!' AS status;
"""

        try:
            init_file = self.init_sql_dir / "01_init.sql"
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write(init_sql)
            print_success(f"创建初始化脚本: init/sql/01_init.sql")
            return True
        except Exception as e:
            print_error(f"创建初始化脚本失败: {e}")
            return False

    def create_docker_compose(self) -> bool:
        """创建 docker-compose.yml（使用本地数据目录持久化）"""
        compose_content = f"""services:
  # PostgreSQL 数据库
  postgres:
    image: pgvector/pgvector:pg16
    container_name: godview-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: godview
      # 性能优化
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C.UTF-8"
    ports:
      - "5432:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./init/sql:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    command:
      - "postgres"
      - "-c"
      - "shared_buffers=256MB"
      - "-c"
      - "work_mem=64MB"
      - "-c"
      - "maintenance_work_mem=128MB"
      - "-c"
      - "effective_cache_size=512MB"

  # Qdrant 向量数据库
  qdrant:
    image: qdrant/qdrant:latest
    container_name: godview-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./data/qdrant:/qdrant/storage
    healthcheck:
      test: ["CMD-SHELL", "timeout 5 sh -c 'curl -f http://localhost:6333/ || exit 1' || exit 0"]
      interval: 10s
      timeout: 10s
      retries: 5
    environment:
      QDRANT__LOG_LEVEL: INFO

  # NebulaGraph 图数据库
  nebula:
    image: vesoft/nebula-graphd:v3
    container_name: godview-nebula-graphd
    restart: unless-stopped
    environment:
      USER: root
    ports:
      - "9669:9669"
      - "19669:19669"
    depends_on:
      - nebula-metad
      - nebula-storaged
    networks:
      godview-network:
        aliases:
          - nebula-graphd
    entrypoint: ["/usr/local/nebula/bin/nebula-graphd"]
    command:
      - "--flagfile=/usr/local/nebula/etc/nebula-graphd.conf"
      - "--daemonize=false"
      - "--containerized=true"
      - "--meta_server_addrs=nebula-metad:9559"
      - "--local_ip=nebula"
      - "--port=9669"
      - "--ws_ip=0.0.0.0"
      - "--ws_http_port=19669"
      - "--enable_ssl=false"

  nebula-metad:
    image: vesoft/nebula-metad:v3
    container_name: godview-nebula-metad
    restart: unless-stopped
    environment:
      USER: root
    ports:
      - "9559:9559"
      - "19559:19559"
    volumes:
      - ./data/nebula/meta:/data/meta
    networks:
      godview-network:
        aliases:
          - nebula-metad
    entrypoint: ["/usr/local/nebula/bin/nebula-metad"]
    command:
      - "--flagfile=/usr/local/nebula/etc/nebula-metad.conf"
      - "--daemonize=false"
      - "--containerized=true"
      - "--meta_server_addrs=nebula-metad:9559"
      - "--local_ip=nebula-metad"
      - "--port=9559"
      - "--data_path=/data/meta"
      - "--ws_ip=0.0.0.0"
      - "--ws_http_port=19559"
      - "--enable_ssl=false"

  nebula-storaged:
    image: vesoft/nebula-storaged:v3
    container_name: godview-nebula-storaged
    restart: unless-stopped
    environment:
      USER: root
    ports:
      - "9779:9779"
      - "19779:19779"
    volumes:
      - ./data/nebula/storage:/data/storage
    networks:
      godview-network:
        aliases:
          - nebula-storaged
    entrypoint: ["/usr/local/nebula/bin/nebula-storaged"]
    command:
      - "--flagfile=/usr/local/nebula/etc/nebula-storaged.conf"
      - "--daemonize=false"
      - "--containerized=true"
      - "--meta_server_addrs=nebula-metad:9559"
      - "--local_ip=nebula-storaged"
      - "--port=9779"
      - "--data_path=/data/storage"
      - "--ws_ip=0.0.0.0"
      - "--ws_http_port=19779"
      - "--enable_ssl=false"

networks:
  godview-network:
    name: godview-network
"""
        try:
            with open(self.docker_compose_file, 'w', encoding='utf-8') as f:
                f.write(compose_content)
            print_success("创建 docker-compose.yml")
            return True
        except Exception as e:
            print_error(f"创建 docker-compose.yml 失败: {e}")
            return False

    def _get_compose_cmd(self) -> List[str]:
        """获取 docker-compose 命令"""
        # 优先使用新版命令
        success, _ = run_command(['docker', 'compose', 'version'], capture=True)
        if success:
            return ['docker', 'compose']
        return ['docker-compose']

    def start_databases(self, include_nebula: bool = True) -> bool:
        """启动数据库容器（默认包含 NebulaGraph）"""
        if not self.check_docker_running():
            print_error("Docker 未运行")
            if not self.docker_installer.wait_for_docker():
                return False

        print_step("启动数据库服务...")

        # 创建数据目录
        self.setup_data_directories()

        # 创建初始化脚本
        self.create_init_scripts()

        # 创建 docker-compose 文件
        if not self.docker_compose_file.exists():
            self.create_docker_compose()

        compose_cmd = self._get_compose_cmd()

        # 默认启动所有服务（包含 NebulaGraph）
        if include_nebula:
            cmd = compose_cmd + ['up', '-d']
        else:
            cmd = compose_cmd + ['up', '-d', 'postgres', 'qdrant']

        # 首次启动可能需要拉取镜像，不捕获输出以显示进度
        print_info("正在启动数据库服务（首次启动需要拉取镜像，请耐心等待）...")
        print_info("执行命令: " + ' '.join(cmd))

        success, output = run_command(
            cmd,
            cwd=str(self.project_dir),
            capture=True,
            timeout=600  # 10分钟，首次拉取镜像可能较慢
        )

        # 检查容器是否正在创建或运行
        time.sleep(2)  # 等待一下让容器状态稳定

        # 检查容器状态
        check_cmd = ['docker', 'ps', '--filter', 'name=godview-', '--format', '{{.Names}}: {{.Status}}']
        check_success, check_output = run_command(check_cmd, capture=True)

        if check_output.strip():
            print_success("数据库容器状态:")
            for line in check_output.strip().split('\n'):
                print(f"  {line}")

            self.wait_for_databases()

            # 初始化 Qdrant 集合（检测是否已初始化）
            self.init_qdrant_collections_if_needed()

            # 初始化 NebulaGraph（如果启动了）
            if include_nebula:
                time.sleep(5)  # 等待 NebulaGraph 完全启动
                self.init_nebula_graphspace_if_needed()

            return True
        else:
            # 如果没有运行的容器，显示错误信息
            if output:
                print_error(f"启动数据库失败")
                # 只显示关键错误信息
                for line in output.split('\n'):
                    if 'error' in line.lower() or 'failed' in line.lower():
                        print(f"  {line}")
            print_info("请检查 Docker 是否正常运行，或手动运行: docker compose up -d")
            return False

    def stop_databases(self) -> bool:
        """停止数据库容器"""
        compose_cmd = self._get_compose_cmd()
        success, output = run_command(
            compose_cmd + ['down'],
            cwd=str(self.project_dir),
            capture=True
        )
        if success:
            print_success("数据库服务已停止")
            return True
        return False

    def wait_for_databases(self):
        """等待数据库就绪"""
        print_info("等待数据库就绪...")

        # 等待 PostgreSQL
        for i in range(30):
            success, _ = run_command(
                ['docker', 'exec', 'godview-postgres', 'pg_isready', '-U', 'postgres'],
                capture=True
            )
            if success:
                print_success("PostgreSQL 就绪")
                break
            time.sleep(1)
        else:
            print_warning("PostgreSQL 启动超时")

        # 等待 Qdrant
        for i in range(30):
            try:
                urllib.request.urlopen('http://localhost:6333/', timeout=2)
                print_success("Qdrant 就绪")
                break
            except:
                time.sleep(1)
        else:
            print_warning("Qdrant 启动超时")

    def init_qdrant_collections(self) -> bool:
        """初始化 Qdrant 向量集合"""
        print_info("初始化 Qdrant 向量集合...")

        import json

        # 定义需要的集合
        collections = [
            {
                "name": "character_embeddings",
                "description": "角色特征向量",
                "vectors": {"size": 384, "distance": "Cosine"}  # all-MiniLM-L6-v2 维度
            },
            {
                "name": "plot_embeddings",
                "description": "剧情片段向量",
                "vectors": {"size": 384, "distance": "Cosine"}
            },
            {
                "name": "lore_embeddings",
                "description": "设定条目向量",
                "vectors": {"size": 384, "distance": "Cosine"}
            },
            {
                "name": "chapter_embeddings",
                "description": "章节内容向量",
                "vectors": {"size": 384, "distance": "Cosine"}
            }
        ]

        base_url = "http://localhost:6333"

        for collection in collections:
            try:
                # 检查集合是否存在
                req = urllib.request.Request(
                    f"{base_url}/collections/{collection['name']}",
                    method='GET'
                )
                try:
                    urllib.request.urlopen(req, timeout=5)
                    print_info(f"集合 '{collection['name']}' 已存在")
                    continue
                except urllib.error.HTTPError as e:
                    if e.code != 404:
                        raise

                # 创建集合
                create_data = {
                    "vectors": collection["vectors"]
                }
                req = urllib.request.Request(
                    f"{base_url}/collections/{collection['name']}",
                    data=json.dumps(create_data).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='PUT'
                )
                urllib.request.urlopen(req, timeout=10)
                print_success(f"创建集合: {collection['name']}")

            except Exception as e:
                print_warning(f"创建集合 '{collection['name']}' 失败: {e}")

        return True

    def init_qdrant_collections_if_needed(self) -> bool:
        """检测并初始化 Qdrant 向量集合（如果未初始化）"""
        print_info("检查 Qdrant 初始化状态...")

        base_url = "http://localhost:6333"
        required_collections = ["character_embeddings", "plot_embeddings", "lore_embeddings", "chapter_embeddings"]

        try:
            # 获取所有集合
            req = urllib.request.Request(f"{base_url}/collections", method='GET')
            response = urllib.request.urlopen(req, timeout=5)
            data = json.loads(response.read().decode('utf-8'))

            existing_collections = []
            if 'result' in data and 'collections' in data['result']:
                existing_collections = [c['name'] for c in data['result']['collections']]

            # 检查是否所有必需集合都存在
            missing_collections = [c for c in required_collections if c not in existing_collections]

            if not missing_collections:
                print_success("Qdrant 已初始化，所有集合都已存在")
                return True
            else:
                print_info(f"检测到缺失的集合: {', '.join(missing_collections)}")
                print_info("正在初始化 Qdrant 集合...")
                return self.init_qdrant_collections()

        except Exception as e:
            print_warning(f"检查 Qdrant 状态失败: {e}")
            print_info("尝试初始化 Qdrant 集合...")
            return self.init_qdrant_collections()

    def init_nebula_graphspace(self) -> bool:
        """初始化 NebulaGraph 图空间"""
        print_info("初始化 NebulaGraph 图空间...")

        # 等待 NebulaGraph 完全启动
        print_info("等待 NebulaGraph 服务就绪...")
        max_wait = 60
        for i in range(max_wait):
            # 检查容器状态
            success, output = run_command(
                ['docker', 'exec', 'godview-nebula-graphd', 'echo', 'ready'],
                capture=True
            )
            if success:
                break
            time.sleep(1)
            if i % 10 == 0:
                print_info(f"等待中... ({i}/{max_wait}s)")

        # 额外等待服务完全就绪
        time.sleep(5)

        # 使用 nebula-console 执行初始化命令
        # 先检查 nebula-console 是否可用
        success, _ = run_command(
            ['docker', 'exec', 'godview-nebula-graphd', 'which', 'nebula-console'],
            capture=True
        )

        if not success:
            print_warning("nebula-console 不可用，尝试使用 Python SDK 初始化...")
            return self._init_nebula_via_python()

        # 创建图空间的命令
        commands = [
            # 添加存储主机（NebulaGraph v3 必需）
            'ADD HOSTS "nebula-storaged":9779;',
            # 创建图空间
            'CREATE SPACE IF NOT EXISTS godview(partition_num=10, replica_factor=1, vid_type=FIXED_STRING(64));',
            'USE godview;',
            # 创建标签（与 nebulagraph.py 保持一致）
            'CREATE TAG IF NOT EXISTS character(name STRING, description STRING, role STRING, status STRING, personality_traits STRING, created_at TIMESTAMP, updated_at TIMESTAMP);',
            'CREATE TAG IF NOT EXISTS world(name STRING, world_type STRING, description STRING, created_at TIMESTAMP);',
            'CREATE TAG IF NOT EXISTS region(name STRING, region_type STRING, description STRING, world_id STRING);',
            'CREATE TAG IF NOT EXISTS hook(title STRING, hook_type STRING, status STRING, priority INT, created_at TIMESTAMP);',
            'CREATE TAG IF NOT EXISTS event(summary STRING, event_type STRING, timestamp TIMESTAMP);',
            'CREATE TAG IF NOT EXISTS memory(content STRING, memory_type STRING, importance FLOAT, created_at TIMESTAMP);',
            # 创建边
            'CREATE EDGE IF NOT EXISTS knows(relationship_type STRING, strength FLOAT, since TIMESTAMP);',
            'CREATE EDGE IF NOT EXISTS located_in(since TIMESTAMP);',
            'CREATE EDGE IF NOT EXISTS belongs_to(since TIMESTAMP);',
            'CREATE EDGE IF NOT EXISTS connects_to(distance FLOAT);',
            'CREATE EDGE IF NOT EXISTS involves_character(role STRING);',
            'CREATE EDGE IF NOT EXISTS involves_location(context STRING);',
            'CREATE EDGE IF NOT EXISTS remembers(created_at TIMESTAMP);',
            'CREATE EDGE IF NOT EXISTS participated_in(role STRING);',
        ]

        for cmd in commands:
            # 使用 docker exec 执行命令
            full_cmd = [
                'docker', 'exec', 'godview-nebula-graphd',
                'nebula-console', '-addr', '127.0.0.1', '-port', '9669',
                '-u', 'root', '-p', 'nebula', '-e', cmd
            ]
            success, output = run_command(full_cmd, capture=True, timeout=30)
            if success or 'created' in output.lower() or 'existed' in output.lower() or 'Execution succeeded' in output:
                if 'CREATE' in cmd:
                    print_success(f"执行: {cmd[:50]}...")
            else:
                # 检查是否是因为已存在
                if 'Existed' in output or 'existed' in output.lower():
                    print_info(f"已存在: {cmd[:40]}...")
                else:
                    print_warning(f"执行失败: {cmd[:50]}...")
                    if output:
                        print_info(f"错误信息: {output[:100]}")

        print_success("NebulaGraph 图空间初始化完成")
        return True

    def _init_nebula_via_python(self) -> bool:
        """使用 Python SDK 初始化 NebulaGraph"""
        try:
            from nebula3.gclient.net import ConnectionPool
            from nebula3.Config import Config
            import time

            config = Config()
            config.max_connection_pool_size = 10

            pool = ConnectionPool()
            pool.init([('127.0.0.1', 9669)], config)

            session = pool.get_session('root', 'nebula')

            # 首先添加存储主机（NebulaGraph v3 必需）
            print_info("添加存储主机...")
            result = session.execute('ADD HOSTS "nebula-storaged":9779;')
            if result.is_succeeded():
                print_success("添加存储主机: nebula-storaged:9779")
            else:
                print_warning(f"添加存储主机失败: {result.error_msg()}")

            # 等待存储主机上线
            time.sleep(5)

            # 创建图空间
            print_info("创建图空间...")
            result = session.execute('CREATE SPACE IF NOT EXISTS godview(partition_num=10, replica_factor=1, vid_type=FIXED_STRING(64));')
            if result.is_succeeded():
                print_success("创建图空间: godview")
            else:
                print_error(f"创建图空间失败: {result.error_msg()}")
                session.release()
                pool.close()
                return False

            # 等待图空间创建
            time.sleep(10)

            # 切换到 godview
            session.execute('USE godview;')

            # 创建标签和边（与 nebulagraph.py 保持一致）
            commands = [
                # Tags
                'CREATE TAG IF NOT EXISTS character(name STRING, description STRING, role STRING, status STRING, personality_traits STRING, created_at TIMESTAMP, updated_at TIMESTAMP);',
                'CREATE TAG IF NOT EXISTS world(name STRING, world_type STRING, description STRING, created_at TIMESTAMP);',
                'CREATE TAG IF NOT EXISTS region(name STRING, region_type STRING, description STRING, world_id STRING);',
                'CREATE TAG IF NOT EXISTS hook(title STRING, hook_type STRING, status STRING, priority INT, created_at TIMESTAMP);',
                'CREATE TAG IF NOT EXISTS event(summary STRING, event_type STRING, timestamp TIMESTAMP);',
                'CREATE TAG IF NOT EXISTS memory(content STRING, memory_type STRING, importance FLOAT, created_at TIMESTAMP);',
                # Edges
                'CREATE EDGE IF NOT EXISTS knows(relationship_type STRING, strength FLOAT, since TIMESTAMP);',
                'CREATE EDGE IF NOT EXISTS located_in(since TIMESTAMP);',
                'CREATE EDGE IF NOT EXISTS belongs_to(since TIMESTAMP);',
                'CREATE EDGE IF NOT EXISTS connects_to(distance FLOAT);',
                'CREATE EDGE IF NOT EXISTS involves_character(role STRING);',
                'CREATE EDGE IF NOT EXISTS involves_location(context STRING);',
                'CREATE EDGE IF NOT EXISTS remembers(created_at TIMESTAMP);',
                'CREATE EDGE IF NOT EXISTS participated_in(role STRING);',
            ]

            for cmd in commands:
                result = session.execute(cmd)
                if result.is_succeeded():
                    print_success(f"执行: {cmd[:50]}...")
                else:
                    print_warning(f"执行失败: {cmd[:50]}... - {result.error_msg()}")

            session.release()
            pool.close()

            print_success("NebulaGraph 图空间初始化完成")
            return True

        except ImportError:
            print_warning("未安装 nebula3-python，跳过 NebulaGraph 初始化")
            print_info("安装命令: pip install nebula3-python")
            return False
        except Exception as e:
            print_error(f"Python SDK 初始化失败: {e}")
            return False

    def init_nebula_graphspace_if_needed(self) -> bool:
        """检测并初始化 NebulaGraph 图空间（如果未初始化）"""
        print_info("检查 NebulaGraph 初始化状态...")

        try:
            # 检查图空间是否存在
            check_cmd = [
                'docker', 'exec', '-i', 'godview-nebula-graphd',
                'nebula-console', '-addr', '127.0.0.1', '-port', '9669',
                '-u', 'root', '-p', 'nebula', '-e',
                'SHOW SPACES;'
            ]
            success, output = run_command(check_cmd, capture=True)

            if success and 'godview' in output:
                print_success("NebulaGraph 已初始化，图空间 'godview' 已存在")
                return True
            else:
                print_info("检测到 NebulaGraph 未初始化")
                print_info("正在初始化 NebulaGraph 图空间...")
                return self.init_nebula_graphspace()

        except Exception as e:
            print_warning(f"检查 NebulaGraph 状态失败: {e}")
            print_info("尝试初始化 NebulaGraph 图空间...")
            return self.init_nebula_graphspace()

    def get_status(self) -> Dict[str, str]:
        """获取数据库状态"""
        status = {}

        # PostgreSQL
        success, _ = run_command(
            ['docker', 'exec', 'godview-postgres', 'pg_isready', '-U', 'postgres'],
            capture=True
        )
        status['PostgreSQL'] = 'running' if success else 'stopped'

        # Qdrant
        try:
            urllib.request.urlopen('http://localhost:6333/', timeout=2)
            status['Qdrant'] = 'running'
        except:
            status['Qdrant'] = 'stopped'

        # NebulaGraph
        success, _ = run_command(
            ['docker', 'exec', 'godview-nebula-graphd', 'echo', 'ok'],
            capture=True
        )
        status['NebulaGraph'] = 'running' if success else 'stopped'

        return status

    def reset_databases(self) -> bool:
        """重置数据库（删除所有数据）"""
        print_warning("正在停止数据库...")
        self.stop_databases()

        print_warning("删除数据目录...")
        import shutil
        data_dirs = [
            self.data_dir / "postgres",
            self.data_dir / "qdrant",
            self.data_dir / "nebula",
        ]

        for d in data_dirs:
            if d.exists():
                try:
                    shutil.rmtree(d)
                    print_success(f"删除: {d.relative_to(self.project_dir)}")
                except Exception as e:
                    print_error(f"删除失败 {d}: {e}")

        print_info("重新创建数据目录...")
        self.setup_data_directories()

        print_success("数据库已重置，请重新启动数据库")
        return True

    def backup_data(self) -> bool:
        """备份数据库数据"""
        import datetime

        backup_dir = self.project_dir / "backups"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_{timestamp}"

        try:
            backup_dir.mkdir(exist_ok=True)
            backup_path.mkdir()

            # 备份 PostgreSQL
            print_info("备份 PostgreSQL...")
            success, output = run_command([
                'docker', 'exec', 'godview-postgres',
                'pg_dump', '-U', 'postgres', 'godview'
            ], capture=True)

            if success:
                with open(backup_path / 'postgres_backup.sql', 'w', encoding='utf-8') as f:
                    f.write(output)
                print_success("PostgreSQL 备份完成")

            # 备份 Qdrant（快照）
            print_info("创建 Qdrant 快照...")
            try:
                req = urllib.request.Request(
                    'http://localhost:6333/collections/character_embeddings/snapshots',
                    method='POST'
                )
                urllib.request.urlopen(req, timeout=30)
                print_success("Qdrant 快照已创建")
            except Exception as e:
                print_warning(f"Qdrant 快照创建失败: {e}")

            # 复制数据目录
            print_info("复制数据文件...")
            import shutil
            for subdir in ['postgres', 'qdrant']:
                src = self.data_dir / subdir
                if src.exists():
                    dst = backup_path / subdir
                    shutil.copytree(src, dst)
                    print_success(f"备份: {subdir}")

            print_success(f"备份完成: {backup_path}")
            return True

        except Exception as e:
            print_error(f"备份失败: {e}")
            return False

    def restore_from_backup(self, backup_path: str) -> bool:
        """从备份恢复数据库数据

        Args:
            backup_path: 备份目录路径

        Returns:
            bool: 恢复是否成功
        """
        import shutil

        backup_dir = Path(backup_path)
        if not backup_dir.exists():
            print_error(f"备份目录不存在: {backup_path}")
            return False

        print_step(f"从备份恢复数据: {backup_path}")

        # 检查数据库是否运行
        if not self.check_docker_running():
            print_error("Docker 未运行，请先启动 Docker")
            return False

        # 检查容器状态
        success, _ = run_command(['docker', 'ps', '--filter', 'name=godview-postgres'], capture=True)
        if not success:
            print_info("启动数据库容器...")
            self.start_databases(include_nebula=True)
            time.sleep(5)

        # 1. 恢复 PostgreSQL 数据
        postgres_backup_file = backup_dir / "postgres_backup_*.json"
        postgres_sql_file = backup_dir / "postgres_backup.sql"

        # 优先使用 JSON 格式备份
        json_files = list(backup_dir.glob("postgres_backup_*.json"))
        if json_files:
            print_info("从 JSON 备份恢复 PostgreSQL...")
            if self._restore_postgres_from_json(json_files[0]):
                print_success("PostgreSQL JSON 数据恢复完成")
            else:
                print_warning("PostgreSQL JSON 恢复失败，尝试 SQL 恢复...")
                if postgres_sql_file.exists():
                    self._restore_postgres_from_sql(postgres_sql_file)
        elif postgres_sql_file.exists():
            print_info("从 SQL 备份恢复 PostgreSQL...")
            self._restore_postgres_from_sql(postgres_sql_file)
        else:
            print_warning("未找到 PostgreSQL 备份文件")

        # 2. 恢复 Qdrant 数据
        qdrant_backup_file = backup_dir / "qdrant_backup_*.json"
        qdrant_files = list(backup_dir.glob("qdrant_backup_*.json"))
        if qdrant_files:
            print_info("从 JSON 备份恢复 Qdrant...")
            self._restore_qdrant_from_json(qdrant_files[0])
        else:
            print_warning("未找到 Qdrant 备份文件")

        # 3. 恢复 NebulaGraph 数据
        nebula_backup_file = backup_dir / "nebula_backup_*.json"
        nebula_files = list(backup_dir.glob("nebula_backup_*.json"))
        if nebula_files:
            print_info("从 JSON 备份恢复 NebulaGraph...")
            self._restore_nebula_from_json(nebula_files[0])
        else:
            print_warning("未找到 NebulaGraph 备份文件")

        print_success("数据恢复完成")
        return True

    def _restore_postgres_from_json(self, json_file: Path) -> bool:
        """从 JSON 文件恢复 PostgreSQL 数据"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            if 'tables' not in backup_data:
                print_error("备份文件格式错误：缺少 tables 字段")
                return False

            tables = backup_data['tables']
            print_info(f"找到 {len(tables)} 个表的数据")

            # 按依赖顺序排序表
            table_order = [
                'projects', 'worlds', 'characters', 'chapters', 'skills',
                'world_settings', 'plot_lines', 'hooks', 'interventions',
                'lore_entries', 'conversation_history', 'embedding_cache',
                'regions', 'chapter_outlines', 'volume_outlines', 'villains',
                'foreshadowings', 'conflicts', 'event_summaries', 'character_lifecycles',
                'character_skills', 'global_state', 'global_state_history',
                'golden_three_rules', 'golden_three_checks', 'intervention_logs',
                'world_snapshots', 'memory_entries', 'memory_embeddings',
                'memory_decay_rules', 'memory_context_configs', 'memory_usage_logs',
                'token_usage', 'prompt_templates', 'writing_rules', 'writing_rule_sets',
                'project_writing_configs', 'satisfaction_analyses', 'agent_templates',
                'agent_memories', 'agent_execution_records', 'agent_execution_logs',
                'agent_prompt_bindings', 'skill_executions', 'skill_execution_logs',
                'skill_assignments', 'skill_call_records', 'workflow_definitions',
                'workflow_executions'
            ]

            # 首先清空现有数据（按依赖顺序反向）
            print_info("清空现有数据...")
            for table in reversed(table_order):
                if table in tables:
                    run_command([
                        'docker', 'exec', 'godview-postgres',
                        'psql', '-U', 'postgres', '-d', 'godview', '-c',
                        f'TRUNCATE TABLE {table} CASCADE;'
                    ], capture=True)

            # 插入备份数据
            print_info("插入备份数据...")
            for table in table_order:
                if table not in tables:
                    continue

                rows = tables[table]
                if not rows:
                    continue

                print_info(f"恢复表 {table} ({len(rows)} 行)...")

                for row in rows:
                    # 构建 INSERT 语句
                    columns = list(row.keys())
                    values = []
                    for col in columns:
                        val = row[col]
                        if val is None:
                            values.append('NULL')
                        elif isinstance(val, bool):
                            values.append('TRUE' if val else 'FALSE')
                        elif isinstance(val, (int, float)):
                            values.append(str(val))
                        elif isinstance(val, (dict, list)):
                            # JSON 类型
                            import json as json_mod
                            escaped = json_mod.dumps(val).replace("'", "''")
                            values.append(f"'{escaped}'")
                        else:
                            # 字符串类型，需要转义
                            escaped = str(val).replace("'", "''")
                            values.append(f"'{escaped}'")

                    columns_str = ', '.join(columns)
                    values_str = ', '.join(values)

                    insert_sql = f"INSERT INTO {table} ({columns_str}) VALUES ({values_str}) ON CONFLICT DO NOTHING;"

                    success, output = run_command([
                        'docker', 'exec', 'godview-postgres',
                        'psql', '-U', 'postgres', '-d', 'godview', '-c', insert_sql
                    ], capture=True)

                    if not success and 'ERROR' in output:
                        # 单条插入失败可能是数据问题，继续尝试其他数据
                        pass

            return True

        except Exception as e:
            print_error(f"PostgreSQL JSON 恢复失败: {e}")
            return False

    def _restore_postgres_from_sql(self, sql_file: Path) -> bool:
        """从 SQL 文件恢复 PostgreSQL 数据"""
        try:
            # 读取 SQL 文件
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # 通过 docker exec 执行 SQL
            success, output = run_command([
                'docker', 'exec', '-i', 'godview-postgres',
                'psql', '-U', 'postgres', '-d', 'godview'
            ], capture=True, timeout=300)

            # 使用管道传入 SQL 内容
            import subprocess
            process = subprocess.Popen(
                ['docker', 'exec', '-i', 'godview-postgres', 'psql', '-U', 'postgres', '-d', 'godview'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=sql_content, timeout=300)

            if process.returncode == 0:
                print_success("PostgreSQL SQL 数据恢复完成")
                return True
            else:
                print_warning(f"部分恢复可能失败: {stderr[:500]}")
                return False

        except Exception as e:
            print_error(f"PostgreSQL SQL 恢复失败: {e}")
            return False

    def _restore_qdrant_from_json(self, json_file: Path) -> bool:
        """从 JSON 文件恢复 Qdrant 数据"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            if 'collections' not in backup_data:
                print_error("备份文件格式错误：缺少 collections 字段")
                return False

            collections = backup_data['collections']
            base_url = "http://localhost:6333"

            for collection_name, collection_data in collections.items():
                print_info(f"恢复 Qdrant 集合: {collection_name}")

                # 检查集合是否存在
                try:
                    req = urllib.request.Request(
                        f"{base_url}/collections/{collection_name}",
                        method='GET'
                    )
                    urllib.request.urlopen(req, timeout=5)
                    collection_exists = True
                except:
                    collection_exists = False

                # 创建集合（如果不存在）
                if not collection_exists:
                    vectors_config = collection_data.get('vectors_config', {"size": 384, "distance": "Cosine"})
                    create_data = {"vectors": vectors_config}
                    req = urllib.request.Request(
                        f"{base_url}/collections/{collection_name}",
                        data=json.dumps(create_data).encode('utf-8'),
                        headers={'Content-Type': 'application/json'},
                        method='PUT'
                    )
                    urllib.request.urlopen(req, timeout=10)

                # 插入数据点
                points = collection_data.get('points', [])
                if points:
                    # 分批上传（每批 100 条）
                    batch_size = 100
                    for i in range(0, len(points), batch_size):
                        batch = points[i:i+batch_size]
                        upload_data = {"points": batch}
                        req = urllib.request.Request(
                            f"{base_url}/collections/{collection_name}/points",
                            data=json.dumps(upload_data).encode('utf-8'),
                            headers={'Content-Type': 'application/json'},
                            method='PUT'
                        )
                        urllib.request.urlopen(req, timeout=30)

                    print_success(f"集合 {collection_name}: 恢复 {len(points)} 个数据点")

            return True

        except Exception as e:
            print_error(f"Qdrant 恢复失败: {e}")
            return False

    def _restore_nebula_from_json(self, json_file: Path) -> bool:
        """从 JSON 文件恢复 NebulaGraph 数据"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            print_info("NebulaGraph 数据恢复需要 Python SDK...")

            # 尝试使用 Python SDK
            try:
                from nebula3.gclient.net import ConnectionPool
                from nebula3.Config import Config

                config = Config()
                config.max_connection_pool_size = 10
                pool = ConnectionPool()
                pool.init([('127.0.0.1', 9669)], config)
                session = pool.get_session('root', 'nebula')

                # 切换到 godview 图空间
                session.execute('USE godview;')

                # 恢复顶点
                if 'vertices' in backup_data:
                    for vertex in backup_data['vertices']:
                        vid = vertex.get('vid')
                        tag = vertex.get('tag')
                        props = vertex.get('properties', {})

                        # 构建 INSERT 语句
                        prop_names = list(props.keys())
                        prop_values = []
                        for p in prop_names:
                            val = props[p]
                            if isinstance(val, str):
                                prop_values.append(f'"{val}"')
                            else:
                                prop_values.append(str(val))

                        prop_str = ', '.join([f'"{n}":{v}' for n, v in zip(prop_names, prop_values)])
                        insert_stmt = f'INSERT VERTEX {tag}({", ".join(prop_names)}) VALUES "{vid}":({prop_str});'
                        session.execute(insert_stmt)

                    print_success(f"恢复 {len(backup_data['vertices'])} 个顶点")

                # 恢复边
                if 'edges' in backup_data:
                    for edge in backup_data['edges']:
                        edge_type = edge.get('type')
                        src = edge.get('src')
                        dst = edge.get('dst')
                        props = edge.get('properties', {})

                        prop_names = list(props.keys())
                        prop_values = []
                        for p in prop_names:
                            val = props[p]
                            if isinstance(val, str):
                                prop_values.append(f'"{val}"')
                            else:
                                prop_values.append(str(val))

                        insert_stmt = f'INSERT EDGE {edge_type}({", ".join(prop_names)}) VALUES "{src}"->"{dst}":({", ".join(prop_values)});'
                        session.execute(insert_stmt)

                    print_success(f"恢复 {len(backup_data['edges'])} 条边")

                session.release()
                pool.close()
                return True

            except ImportError:
                print_warning("未安装 nebula3-python，跳过 NebulaGraph 恢复")
                print_info("安装命令: pip install nebula3-python")
                return False

        except Exception as e:
            print_error(f"NebulaGraph 恢复失败: {e}")
            return False


class GodViewInstaller:
    def __init__(self):
        self.system = platform.system()
        self.is_windows = self.system == 'Windows'
        self.is_linux = self.system == 'Linux'
        self.is_mac = self.system == 'Darwin'
        self.use_conda = False
        self.install_dir = None
        self.project_dir = None
        self.venv_path = None
        self.conda_env_name = "godview"
        self.db_manager = None
        self.install_databases = True

    def ask_install_options(self) -> bool:
        """询问安装选项"""
        print(f"{Colors.BOLD}请选择安装模式：{Colors.END}\n")

        modes = [
            "完整安装（Python环境 + 数据库 + Docker自动安装）",
            "仅安装 Python 环境",
            "仅安装/管理数据库",
            "仅安装 Docker",
            "更新 pip 并补安装缺失依赖",
        ]

        mode_idx = print_menu(modes)

        if mode_idx == 0:  # 完整安装
            self.install_databases = True
        elif mode_idx == 1:  # 仅 Python
            self.install_databases = False
        elif mode_idx == 2:  # 仅数据库
            self.manage_databases_only()
            return False
        elif mode_idx == 3:  # 仅 Docker
            self.install_docker_only()
            return False
        elif mode_idx == 4:  # 更新 pip 并补缺
            self.update_pip_and_fix_deps()
            return False

        # 选择环境类型
        print(f"\n{Colors.BOLD}选择 Python 环境：{Colors.END}\n")
        env_types = [
            "Conda 环境（推荐）",
            "系统 Python + venv",
        ]
        env_idx = print_menu(env_types)
        self.use_conda = (env_idx == 0)

        # 输入安装目录
        print()
        default_dir = os.path.join(os.path.expanduser("~"), "GodView")
        print(f"{Colors.BOLD}安装目录（直接回车使用默认: {default_dir}）{Colors.END}")

        dir_input = input("路径: ").strip()
        if dir_input:
            self.install_dir = Path(dir_input).resolve()
        else:
            self.install_dir = Path(default_dir)

        print_info(f"安装目录: {self.install_dir}")

        return True

    def manage_databases_only(self):
        """仅管理数据库"""
        self.project_dir = Path(__file__).parent.resolve()
        self.db_manager = DatabaseManager(self.project_dir)

        while True:
            print(f"\n{Colors.BOLD}数据库管理{Colors.END}\n")

            # 显示当前状态
            if self.db_manager.check_docker():
                status = self.db_manager.get_status()
                print("当前状态:")
                for name, state in status.items():
                    color = Colors.GREEN if state == 'running' else Colors.RED
                    print(f"  {name}: {color}{state}{Colors.END}")
                print()

            actions = [
                "启动所有数据库（PostgreSQL + Qdrant + NebulaGraph）",
                "启动 PostgreSQL + Qdrant（不含 NebulaGraph）",
                "停止所有数据库",
                "重启所有数据库",
                "查看数据库状态",
                "重新初始化数据库（清除所有数据！）",
                "初始化 Qdrant 向量集合",
                "初始化 NebulaGraph 图空间",
                "备份数据库数据",
                "从备份恢复数据",
                "安装 Docker",
                "返回主菜单",
            ]

            idx = print_menu(actions)

            if idx == 0:
                self.db_manager.start_databases(include_nebula=True)
            elif idx == 1:
                self.db_manager.start_databases(include_nebula=False)
            elif idx == 2:
                self.db_manager.stop_databases()
            elif idx == 3:
                self.db_manager.stop_databases()
                time.sleep(2)
                self.db_manager.start_databases(include_nebula=True)
            elif idx == 4:
                status = self.db_manager.get_status()
                print("\n数据库状态:")
                for name, state in status.items():
                    color = Colors.GREEN if state == 'running' else Colors.RED
                    print(f"  {name}: {color}{state}{Colors.END}")
            elif idx == 5:
                if confirm_dangerous_action("这将删除所有数据库数据！"):
                    self.db_manager.reset_databases()
            elif idx == 6:
                self.db_manager.init_qdrant_collections()
            elif idx == 7:
                self.db_manager.init_nebula_graphspace()
            elif idx == 8:
                self.db_manager.backup_data()
            elif idx == 9:
                # 从备份恢复
                print_info("可用的备份目录:")
                backup_dir = self.project_dir / "backups"
                if backup_dir.exists():
                    backups = sorted(backup_dir.glob("backup_*"), reverse=True)
                    if backups:
                        for i, b in enumerate(backups[:10], 1):
                            print(f"  {i}. {b.name}")
                        print()
                        choice = input("选择备份编号（或输入完整路径）: ").strip()
                        try:
                            idx_choice = int(choice) - 1
                            if 0 <= idx_choice < len(backups):
                                self.db_manager.restore_from_backup(str(backups[idx_choice]))
                            else:
                                self.db_manager.restore_from_backup(choice)
                        except ValueError:
                            if choice:
                                self.db_manager.restore_from_backup(choice)
                    else:
                        print_warning("未找到备份目录")
                        backup_path = input("请输入备份路径: ").strip()
                        if backup_path:
                            self.db_manager.restore_from_backup(backup_path)
                else:
                    print_warning("未找到 backups 目录")
                    backup_path = input("请输入备份路径: ").strip()
                    if backup_path:
                        self.db_manager.restore_from_backup(backup_path)
            elif idx == 10:
                self.db_manager.install_docker()
            elif idx == 11:
                break

    def install_docker_only(self):
        """仅安装 Docker"""
        docker_installer = DockerInstaller()

        print(f"\n{Colors.BOLD}Docker 安装{Colors.END}\n")

        if docker_installer.check_docker_installed():
            print_success("Docker 已安装")
            if docker_installer.check_docker_running():
                print_success("Docker 服务正在运行")
            else:
                print_warning("Docker 服务未运行")
                print_info("请启动 Docker Desktop 或运行 'dockerd'")
        else:
            print_info("开始安装 Docker...")
            if docker_installer.install():
                print_success("Docker 安装成功")
                if self.is_linux:
                    print_info("您可能需要运行 'newgrp docker' 或重新登录")
            else:
                print_error("Docker 安装失败")

    def update_pip_and_fix_deps(self):
        """更新 pip 并补安装缺失依赖"""
        self.project_dir = Path(__file__).parent.resolve()

        print(f"\n{Colors.BOLD}更新 Pip 并补安装缺失依赖{Colors.END}\n")

        # 选择 Python 环境
        print(f"{Colors.BOLD}选择 Python 环境：{Colors.END}\n")
        env_types = [
            "Conda 环境",
            "系统 Python + venv",
            "当前系统 Python",
        ]
        env_idx = print_menu(env_types)

        if env_idx == 0:  # Conda
            self.use_conda = True
            print_info("使用 Conda 环境")
            # 列出可用的 conda 环境
            result = subprocess.run(['conda', 'env', 'list'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"\n{Colors.BOLD}可用的 Conda 环境：{Colors.END}")
                lines = result.stdout.strip().split('\n')
                envs = []
                for line in lines:
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if parts:
                            env_name = parts[0]
                            if env_name:
                                envs.append(env_name)
                                print(f"  {len(envs)}. {env_name}")

                if envs:
                    print()
                    choice = input(f"选择环境编号 [默认: godview]: ").strip()
                    if choice:
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(envs):
                                self.conda_env_name = envs[idx]
                        except ValueError:
                            pass
                    print_info(f"使用环境: {self.conda_env_name}")
            else:
                self.conda_env_name = "godview"

        elif env_idx == 1:  # venv
            self.use_conda = False
            # 查找 venv - 扩展搜索范围
            possible_venvs = [
                # 项目目录下的 venv
                self.project_dir / "venv",
                # 同级目录的 _env/venv 模式
                self.project_dir.parent / f"{self.project_dir.name}_env" / "venv",
                # 父目录下以项目名命名的 venv
                self.project_dir.parent / f"{self.project_dir.name}_venv",
                # 兄弟目录中查找
                self.project_dir.parent / "venv",
                # 常见的虚拟环境目录名
                self.project_dir / ".venv",
                self.project_dir.parent / f"{self.project_dir.name}_env",
            ]

            # 去重并检查存在性
            found_venvs = []
            seen = set()
            for venv_path in possible_venvs:
                venv_str = str(venv_path)
                if venv_path.exists() and venv_str not in seen:
                    # 验证是否是有效的 venv（检查是否有 Scripts/python.exe 或 bin/python）
                    if self.is_windows:
                        python_check = venv_path / "Scripts" / "python.exe"
                    else:
                        python_check = venv_path / "bin" / "python"
                    if python_check.exists():
                        found_venvs.append(venv_path)
                        seen.add(venv_str)

            # 显示找到的 venv 并让用户选择
            if found_venvs:
                print(f"\n{Colors.BOLD}找到以下虚拟环境：{Colors.END}")
                for i, venv in enumerate(found_venvs, 1):
                    print(f"  {i}. {venv}")
                print(f"  {len(found_venvs) + 1}. 手动输入路径")
                print()
                choice = input(f"请选择 [1-{len(found_venvs) + 1}]: ").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(found_venvs):
                        self.venv_path = found_venvs[idx]
                        print_success(f"选择虚拟环境: {self.venv_path}")
                    else:
                        # 手动输入
                        venv_input = input("请输入 venv 路径: ").strip()
                        if venv_input:
                            self.venv_path = Path(venv_input)
                            if not self.venv_path.exists():
                                print_error(f"路径不存在: {self.venv_path}")
                                return
                        else:
                            print_error("未输入有效路径")
                            return
                except ValueError:
                    print_error("无效输入")
                    return
            else:
                print_warning("未自动找到虚拟环境")
                venv_input = input("请输入 venv 路径: ").strip()
                if venv_input:
                    self.venv_path = Path(venv_input)
                    if not self.venv_path.exists():
                        print_error(f"路径不存在: {self.venv_path}")
                        return
                else:
                    print_error("未指定有效的虚拟环境路径")
                    return

        else:  # 系统 Python
            self.use_conda = False
            self.venv_path = None
            print_info("使用当前系统 Python")

        # 获取 pip 和 python 路径
        pip_path = self.get_pip_path()
        python_path = self.get_python_path()

        print_info(f"Python: {python_path}")
        print_info(f"Pip: {pip_path}")

        # 步骤 1: 更新 pip
        print_step("更新 pip...")
        success, output = run_command(
            [python_path, '-m', 'pip', 'install', '--upgrade', 'pip'],
            capture=True,
            timeout=120
        )
        if success or 'Successfully installed' in output:
            print_success("pip 已更新到最新版本")
        else:
            print_warning(f"pip 更新可能失败: {output[:200]}")

        # 步骤 2: 读取 requirements.txt
        print_step("检查依赖...")
        requirements_file = self.project_dir / "requirements.txt"
        if not requirements_file.exists():
            print_error("未找到 requirements.txt")
            return

        # 解析 requirements.txt
        required_packages = []
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # 简单解析包名（去掉版本约束）
                    pkg_name = line.split('>=')[0].split('==')[0].split('<')[0].split('>')[0].split('[')[0]
                    required_packages.append((pkg_name, line))

        print_info(f"requirements.txt 中共有 {len(required_packages)} 个依赖")

        # 步骤 3: 检查已安装的包
        print_info("检查已安装的包...")
        success, output = run_command([pip_path, 'list', '--format=freeze'], capture=True)

        installed_packages = set()
        if success:
            for line in output.strip().split('\n'):
                if '==' in line:
                    pkg_name = line.split('==')[0].lower().replace('-', '_')
                    installed_packages.add(pkg_name)

        # 步骤 4: 找出缺失的包
        missing_packages = []
        for pkg_name, full_spec in required_packages:
            normalized_name = pkg_name.lower().replace('-', '_')
            if normalized_name not in installed_packages:
                missing_packages.append(full_spec)

        if not missing_packages:
            print_success("所有依赖都已安装，无需补安装")
            return

        print_info(f"发现 {len(missing_packages)} 个缺失的依赖：")
        for pkg in missing_packages:
            print(f"  - {pkg}")

        # 步骤 5: 安装缺失的包
        print_step("安装缺失的依赖...")
        print_info("这可能需要几分钟...")

        success, output = run_command(
            [pip_path, 'install'] + missing_packages,
            capture=True,
            timeout=600
        )

        if success or 'Successfully installed' in output:
            print_success("缺失依赖安装完成")

            # 显示安装结果
            if 'Successfully installed' in output:
                for line in output.split('\n'):
                    if 'Successfully installed' in line:
                        print_info(line.strip())
        else:
            print_error("部分依赖安装失败")
            print_info(output[:500])

        # 步骤 6: 验证
        print_step("验证安装...")
        still_missing = []
        for pkg_name, full_spec in required_packages:
            normalized_name = pkg_name.lower().replace('-', '_')
            if normalized_name not in installed_packages:
                # 重新检查
                success, _ = run_command(
                    [python_path, '-c', f'import {pkg_name.replace("-", "_")}'],
                    capture=True
                )
                if not success:
                    still_missing.append(full_spec)

        if still_missing:
            print_warning(f"以下包可能需要手动安装：")
            for pkg in still_missing:
                print(f"  - {pkg}")
        else:
            print_success("所有依赖验证通过")

    def check_conda(self) -> bool:
        if check_command_exists('conda'):
            print_success("Conda 已安装")
            return True
        print_warning("未检测到 Conda")
        if self.is_windows:
            print_info("下载地址: https://docs.conda.io/en/latest/miniconda.html")
        else:
            print_info("安装命令: wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && bash Miniconda3-latest-Linux-x86_64.sh")
        return False

    def check_python(self) -> bool:
        version = get_python_version()
        if version and version >= (3, 10):
            print_success(f"Python 版本: {version[0]}.{version[1]}")
            return True
        print_error("需要 Python 3.10+")
        return False

    def check_nodejs(self) -> bool:
        if check_command_exists('node'):
            success, output = run_command(['node', '--version'], capture=True)
            if success:
                print_success(f"Node.js 版本: {output.strip()}")
                return True
        print_warning("未检测到 Node.js")
        print_info("下载地址: https://nodejs.org/")
        return False

    def create_conda_env(self) -> bool:
        print_step("创建 Conda 环境...")

        result = subprocess.run(['conda', 'env', 'list'], capture_output=True, text=True)
        if self.conda_env_name in result.stdout:
            print_info(f"Conda 环境 '{self.conda_env_name}' 已存在")
            return True

        success, output = run_command([
            'conda', 'create', '-n', self.conda_env_name, 'python=3.11', '-y'
        ], capture=True, timeout=1800)

        if success or 'done' in output.lower():
            print_success(f"Conda 环境 '{self.conda_env_name}' 创建成功")
            return True
        print_error(f"创建失败: {output[:200]}")
        return False

    def create_venv(self) -> bool:
        print_step("创建虚拟环境...")

        self.venv_path = self.project_dir / "venv"
        if self.venv_path.exists():
            print_info("虚拟环境已存在")
            return True

        success, _ = run_command([sys.executable, '-m', 'venv', str(self.venv_path)])
        if success:
            print_success("虚拟环境创建成功")
            return True
        return False

    def get_pip_path(self) -> str:
        if self.use_conda:
            return 'pip'
        if self.venv_path is None:
            return 'pip'  # 系统 Python
        if self.is_windows:
            return str(self.venv_path / "Scripts" / "pip.exe")
        return str(self.venv_path / "bin" / "pip")

    def get_python_path(self) -> str:
        if self.use_conda:
            return 'python'
        if self.venv_path is None:
            return sys.executable  # 系统 Python
        if self.is_windows:
            return str(self.venv_path / "Scripts" / "python.exe")
        return str(self.venv_path / "bin" / "python")

    def install_python_deps(self) -> bool:
        print_step("安装 Python 依赖...")

        requirements = self.project_dir / "requirements.txt"
        if not requirements.exists():
            print_error("未找到 requirements.txt")
            return False

        # 升级 pip
        print_info("升级 pip...")
        run_command([self.get_python_path(), '-m', 'pip', 'install', '--upgrade', 'pip'], capture=True)

        # 安装依赖
        print_info("安装项目依赖（可能需要几分钟）...")
        success, output = run_command(
            [self.get_pip_path(), 'install', '-r', str(requirements)],
            capture=True,
            timeout=600
        )

        if success or 'Successfully installed' in output:
            print_success("Python 依赖安装完成")
            return True
        print_error(f"安装失败: {output[:500]}")
        return False

    def install_frontend_deps(self) -> bool:
        print_step("安装前端依赖...")

        frontend_dir = self.project_dir / "frontend"
        if not check_command_exists('npm'):
            print_warning("未找到 npm，跳过前端安装")
            return False

        success, output = run_command(['npm', 'install'], cwd=str(frontend_dir), capture=True, timeout=300)
        if success:
            print_success("前端依赖安装完成")
            return True
        print_warning(f"前端依赖安装失败: {output[:200]}")
        return False

    def create_env_file(self) -> bool:
        print_step("创建配置文件...")

        env_file = self.project_dir / ".env"
        if env_file.exists():
            print_info(".env 文件已存在")
            return True

        env_content = """# ======================== 应用配置 ========================
APP_NAME=Godview
APP_VERSION=1.0.0
DEBUG=True
LOG_LEVEL=INFO

# ======================== 服务器配置（前后端分离时需要修改）========================
API_BASE_URL=http://localhost:8000
WS_BASE_URL=ws://localhost:8000
FRONTEND_URL=http://localhost:5173

# ======================== 数据库配置 ========================
# PostgreSQL (docker 启动)
#   地址: localhost:5432
#   用户: postgres
#   密码: password
#   数据库: godview
# 注意: Windows 上使用 127.0.0.1 而非 localhost，避免 IPv6 解析问题
DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview

# NebulaGraph 图数据库 (docker 启动)
#   地址: 127.0.0.1:9669
#   用户: root
#   密码: nebula
NEBULA_HOST=127.0.0.1
NEBULA_PORT=9669
NEBULA_USER=root
NEBULA_PASSWORD=nebula

# Qdrant 向量数据库 (docker 启动)
#   地址: http://127.0.0.1:6333
# 注意: Windows 上使用 127.0.0.1 而非 localhost，避免 IPv6 解析问题
QDRANT_URL=http://127.0.0.1:6333

# ======================== Embedding 配置 ========================
# 当前使用的 Provider (openai / sentence_transformers / ollama)
EMBEDDING_PROVIDER=sentence_transformers

# OpenAI Embedding 配置
EMBEDDING_OPENAI_MODEL=text-embedding-3-small
EMBEDDING_OPENAI_API_KEY=your-openai-api-key-here
EMBEDDING_OPENAI_BASE_URL=https://api.openai.com/v1

# Sentence-Transformers 配置（本地推荐）
EMBEDDING_ST_MODEL=all-MiniLM-L6-v2
EMBEDDING_ST_CACHE_FOLDER=

# Ollama Embedding 配置
# 注意: Windows 上使用 127.0.0.1 而非 localhost，避免 IPv6 解析问题
EMBEDDING_OLLAMA_MODEL=nomic-embed-text
EMBEDDING_OLLAMA_BASE_URL=http://127.0.0.1:11434

# ======================== LLM 配置 ========================
# 当前使用的 Provider
LLM_PROVIDER=openai

# OpenAI 配置
LLM_OPENAI_MODEL=gpt-4o
LLM_OPENAI_API_KEY=your-openai-api-key-here
LLM_OPENAI_BASE_URL=https://api.openai.com/v1
LLM_OPENAI_TEMPERATURE=0.7
LLM_OPENAI_MAX_TOKENS=4096

# Anthropic 配置
LLM_ANTHROPIC_MODEL=claude-sonnet-4-20250514
LLM_ANTHROPIC_API_KEY=your-anthropic-api-key-here
LLM_ANTHROPIC_BASE_URL=https://api.anthropic.com
LLM_ANTHROPIC_TEMPERATURE=0.7
LLM_ANTHROPIC_MAX_TOKENS=4096

# 智谱 AI 配置
LLM_ZHIPU_MODEL=glm-4-plus
LLM_ZHIPU_API_KEY=your-zhipu-api-key-here
LLM_ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_ZHIPU_TEMPERATURE=0.7
LLM_ZHIPU_MAX_TOKENS=4096

# 通义千问配置
LLM_QWEN_MODEL=qwen-max
LLM_QWEN_API_KEY=your-qwen-api-key-here
LLM_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_QWEN_TEMPERATURE=0.7
LLM_QWEN_MAX_TOKENS=4096

# DeepSeek 配置
LLM_DEEPSEEK_MODEL=deepseek-chat
LLM_DEEPSEEK_API_KEY=your-deepseek-api-key-here
LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK_TEMPERATURE=0.7
LLM_DEEPSEEK_MAX_TOKENS=4096

# ======================== 导演系统配置 ========================
MAX_TURNS_THRESHOLD=5
TARGET_WORD_COUNT_PER_INTENT=200
MIN_CHAPTER_WORD_COUNT=2000
"""
        try:
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(env_content)
            print_success(".env 配置文件已创建")
            return True
        except Exception as e:
            print_error(f"创建失败: {e}")
            return False

    def create_start_scripts(self) -> bool:
        print_step("创建启动脚本...")

        # Windows
        if self.is_windows:
            if self.use_conda:
                start_bat = f"""@echo off
chcp 65001 >nul
echo Starting GodView...
echo.
echo Starting databases...
cd /d {self.project_dir}
docker compose up -d
timeout /t 8 /nobreak >nul
echo.
echo Starting backend...
start "GodView Backend" cmd /k "conda activate {self.conda_env_name} && python -m uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload"
echo.
echo Starting frontend...
cd /d {self.project_dir}\\frontend
start "GodView Frontend" cmd /k "npm run dev"
echo.
echo ========================================
echo   GodView 已启动!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ========================================
echo   数据库: PostgreSQL:5432 Qdrant:6333 NebulaGraph:9669
echo ========================================
pause
"""
            else:
                start_bat = f"""@echo off
chcp 65001 >nul
echo Starting GodView...
echo.
echo Starting databases...
cd /d {self.project_dir}
docker compose up -d
timeout /t 8 /nobreak >nul
echo.
echo Starting backend...
start "GodView Backend" cmd /k "{self.venv_path}\\Scripts\\python.exe -m uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload"
echo.
echo Starting frontend...
cd /d {self.project_dir}\\frontend
start "GodView Frontend" cmd /k "npm run dev"
echo.
echo ========================================
echo   GodView 已启动!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ========================================
echo   数据库: PostgreSQL:5432 Qdrant:6333 NebulaGraph:9669
echo ========================================
pause
"""
            with open(self.project_dir / "start.bat", 'w', encoding='utf-8') as f:
                f.write(start_bat)
            print_success("创建 start.bat")

        # Linux/Mac
        conda_init_block = '''# 添加 conda 初始化（适用于非交互式 shell）
CONDA_BASE=$(conda info --base 2>/dev/null || echo "$HOME/miniconda3")
if [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
    source "$CONDA_BASE/etc/profile.d/conda.sh"
fi
''' if self.use_conda else ''

        start_sh = f"""#!/bin/bash
{conda_init_block}echo "Starting GodView..."
echo ""
echo "Starting databases..."
cd {self.project_dir}
docker compose up -d
sleep 8
echo ""
echo "Starting backend..."
{'conda activate ' + self.conda_env_name + ' && ' if self.use_conda else ''} \\
    python -m uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo ""
echo "Starting frontend..."
cd {self.project_dir}/frontend && npm run dev &
FRONTEND_PID=$!
echo ""
echo "========================================"
echo "  GodView 已启动!"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "========================================"
echo "  数据库: PostgreSQL:5432 Qdrant:6333 NebulaGraph:9669"
echo "========================================"
echo "Press Ctrl+C to stop"
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker compose down" EXIT
wait
"""
        with open(self.project_dir / "start.sh", 'w', encoding='utf-8') as f:
            f.write(start_sh)
        if not self.is_windows:
            os.chmod(self.project_dir / "start.sh", 0o755)
        print_success("创建 start.sh")

        # 停止脚本
        stop_content = """@echo off
echo Stopping GodView...
docker compose down
echo Done.
pause
""" if self.is_windows else """#!/bin/bash
echo "Stopping GodView..."
docker compose down
echo "Done."
"""
        stop_file = self.project_dir / ("stop.bat" if self.is_windows else "stop.sh")
        with open(stop_file, 'w', encoding='utf-8') as f:
            f.write(stop_content)
        if not self.is_windows:
            os.chmod(stop_file, 0o755)
        print_success(f"创建 {'stop.bat' if self.is_windows else 'stop.sh'}")

        return True

    def print_final_instructions(self):
        print()
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}              安装完成！{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*60}{Colors.END}")
        print()
        print(f"{Colors.BOLD}下一步：{Colors.END}\n")
        print("1. 编辑 .env 配置 LLM API Key")
        print(f"   文件: {self.project_dir / '.env'}\n")
        print("2. 启动应用：")
        if self.is_windows:
            print(f"   双击: {self.project_dir / 'start.bat'}")
        else:
            print(f"   运行: {self.project_dir / 'start.sh'}")
        print()
        print("3. 访问：")
        print(f"   前端: {Colors.CYAN}http://localhost:5173{Colors.END}")
        print(f"   后端: {Colors.CYAN}http://localhost:8000{Colors.END}")
        print(f"   文档: {Colors.CYAN}http://localhost:8000/docs{Colors.END}")
        print()
        print(f"{Colors.YELLOW}数据库信息：{Colors.END}")
        print("  PostgreSQL:")
        print(f"    地址: {Colors.CYAN}localhost:5432{Colors.END}")
        print(f"    用户: {Colors.CYAN}postgres{Colors.END}")
        print(f"    密码: {Colors.CYAN}password{Colors.END}")
        print(f"    数据库: {Colors.CYAN}godview{Colors.END}")
        print("  Qdrant:")
        print(f"    地址: {Colors.CYAN}http://localhost:6333{Colors.END}")
        print("  NebulaGraph:")
        print(f"    地址: {Colors.CYAN}localhost:9669{Colors.END}")
        print(f"    用户: {Colors.CYAN}root{Colors.END}")
        print(f"    密码: {Colors.CYAN}nebula{Colors.END}")
        print()
        print(f"{Colors.YELLOW}数据持久化目录：{Colors.END}")
        print(f"  {self.project_dir / 'data' / 'postgres'}")
        print(f"  {self.project_dir / 'data' / 'qdrant'}")
        print(f"  {self.project_dir / 'data' / 'nebula'}")
        print()
        print(f"{Colors.YELLOW}初始化脚本：{Colors.END}")
        print(f"  {self.project_dir / 'init' / 'sql' / '01_init.sql'}")
        print()
        print(f"{Colors.CYAN}数据库管理：{Colors.END}")
        print("  运行 'python install.py' 选择 '仅安装/管理数据库'")
        print()

    def install(self) -> bool:
        clear_screen()
        print_banner()

        if not self.ask_install_options():
            return True  # 用户选择退出或进入子菜单

        # 检查依赖
        print_step("检查系统依赖...")

        if self.use_conda:
            if not self.check_conda():
                return False
        else:
            if not self.check_python():
                return False

        self.check_nodejs()

        # 设置项目目录
        self.project_dir = Path(__file__).parent.resolve()
        self.db_manager = DatabaseManager(self.project_dir)
        print_info(f"项目目录: {self.project_dir}")

        # 数据库安装
        if self.install_databases:
            print_step("检查数据库环境...")

            if not self.db_manager.check_docker():
                print_warning("需要安装 Docker 来运行数据库")
                if not self.db_manager.install_docker():
                    print_error("Docker 安装失败，请手动安装")
                    print_info("安装文档: https://docs.docker.com/get-docker/")
                    choice = input("是否继续安装其他组件？(y/n): ").strip().lower()
                    if choice != 'y':
                        return False

            if self.db_manager.check_docker():
                # 等待 Docker 启动
                if not self.db_manager.check_docker_running():
                    self.db_manager.docker_installer.wait_for_docker()

                self.db_manager.create_docker_compose()
                self.db_manager.start_databases(include_nebula=True)

        # 创建虚拟环境
        if self.use_conda:
            self.create_conda_env()
        else:
            self.create_venv()

        # 安装依赖
        self.install_python_deps()
        self.install_frontend_deps()

        # 创建配置
        self.create_env_file()
        self.create_start_scripts()

        # 完成
        self.print_final_instructions()
        return True


def main():
    try:
        installer = GodViewInstaller()
        success = installer.install()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n安装已取消")
        sys.exit(1)
    except Exception as e:
        print_error(f"安装错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
