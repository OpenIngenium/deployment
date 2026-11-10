#!/usr/bin/env python3
"""
Ingenium Interactive Wizard
Nice CLI experience for managing Ingenium repositories and deployments
"""

import sys
from pathlib import Path

try:
    import questionary
    from questionary import Style
except ImportError:
    print("Error: questionary is not installed")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)

import config
import subprocess
import os
from typing import Dict, List, Optional, Tuple


# Custom style for the wizard
custom_style = Style([
    ('qmark', 'fg:#e91e63 bold'),
    ('question', 'fg:#ffffff bold'),
    ('answer', 'fg:#2196f3 bold'),
    ('pointer', 'fg:#e91e63 bold'),
    ('highlighted', 'fg:#e91e63 bold'),
    ('selected', 'fg:#4caf50 bold'),
    ('separator', 'fg:#6c757d'),
    ('instruction', 'fg:#9e9e9e'),
    ('text', ''),
])


# ── ANSI Color Helpers ──────────────────────────────────────────────

class C:
    """ANSI color codes for terminal output."""
    RESET    = "\033[0m"
    BOLD     = "\033[1m"
    DIM      = "\033[2m"
    RED      = "\033[91m"
    GREEN    = "\033[92m"
    YELLOW   = "\033[93m"
    BLUE     = "\033[94m"
    MAGENTA  = "\033[95m"
    CYAN     = "\033[96m"
    WHITE    = "\033[97m"
    GRAY     = "\033[90m"


def header(title: str, style: str = "main"):
    """Print a styled section header."""
    width = 70
    if style == "main":
        color = C.CYAN
        print(f"\n{color}{C.BOLD}{'━' * width}")
        print(f"  {title}")
        print(f"{'━' * width}{C.RESET}\n")
    elif style == "step":
        color = C.MAGENTA
        print(f"\n{color}{C.BOLD}{'─' * width}")
        print(f"  {title}")
        print(f"{'─' * width}{C.RESET}\n")
    elif style == "success":
        color = C.GREEN
        print(f"\n{color}{C.BOLD}{'═' * width}")
        print(f"  {title}")
        print(f"{'═' * width}{C.RESET}\n")
    elif style == "warn":
        color = C.YELLOW
        print(f"\n{color}{C.BOLD}{'═' * width}")
        print(f"  {title}")
        print(f"{'═' * width}{C.RESET}\n")


def success(msg: str):
    """Print a success message."""
    print(f"{C.GREEN}{C.BOLD}  ✅ {msg}{C.RESET}")


def warn(msg: str):
    """Print a warning message."""
    print(f"{C.YELLOW}{C.BOLD}  ⚠️  {msg}{C.RESET}")


def error(msg: str):
    """Print an error message."""
    print(f"{C.RED}{C.BOLD}  ❌ {msg}{C.RESET}")


def info(msg: str):
    """Print an info message."""
    print(f"{C.CYAN}  💡 {msg}{C.RESET}")


def dim(msg: str):
    """Print dimmed text."""
    print(f"{C.GRAY}  {msg}{C.RESET}")


def print_banner():
    """Print welcome banner."""
    banner = f"""
{C.CYAN}{C.BOLD}  ╔════════════════════════════════════════════════════════════════════╗
  ║                                                                    ║
  ║   ██╗███╗   ██╗ ██████╗ ███████╗███╗   ██╗██╗██╗   ██╗███╗   ███╗  ║
  ║   ██║████╗  ██║██╔════╝ ██╔════╝████╗  ██║██║██║   ██║████╗ ████║  ║
  ║   ██║██╔██╗ ██║██║  ███╗█████╗  ██╔██╗ ██║██║██║   ██║██╔████╔██║  ║
  ║   ██║██║╚██╗██║██║   ██║██╔══╝  ██║╚██╗██║██║██║   ██║██║╚██╔╝██║  ║
  ║   ██║██║ ╚████║╚██████╔╝███████╗██║ ╚████║██║╚██████╔╝██║ ╚═╝ ██║  ║
  ║   ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝     ╚═╝  ║
  ║                                                                    ║
  ║{C.RESET}{C.WHITE}{C.BOLD}              Deployment Pipeline  ·  Version 3.0                   {C.CYAN}{C.BOLD}║
  ║                                                                    ║
  ╚════════════════════════════════════════════════════════════════════╝{C.RESET}
"""
    print(banner)


def run_command(cmd: List[str], cwd: Optional[Path] = None, stream_output: bool = False) -> bool:
    """Run a command and return success status.
    
    If stream_output=True, show output in real-time (for build commands).
    """
    try:
        if stream_output:
            # Stream output in real-time - don't capture, let it print directly
            result = subprocess.run(
                cmd,
                cwd=cwd,
                check=True
            )
            return True
        else:
            # Capture and print after completion (for clone commands)
            result = subprocess.run(
                cmd,
                cwd=cwd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            print(result.stdout)
            return True
    except subprocess.CalledProcessError as e:
        if hasattr(e, 'stdout') and e.stdout:
            print(f"❌ Error: {e.stdout}")
        return False


def get_repo_info(repo_path: Path) -> dict:
    """Get current branch/tag/commit info for a repository."""
    if not repo_path.exists():
        return {"status": "not_found"}
    
    # Get current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    branch = result.stdout.strip()
    
    # Get commit hash
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    commit = result.stdout.strip()
    
    # Check if it's a tag
    result = subprocess.run(
        ["git", "describe", "--exact-match", "--tags", "HEAD"],
        cwd=repo_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    tag = result.stdout.strip() if result.returncode == 0 else None
    
    return {
        "status": "ok",
        "branch": branch,
        "commit": commit,
        "tag": tag
    }


def display_summary_report(repos: List[str], repos_path: Path):
    """Display summary of repository states after clone/update."""
    header("📊 REPOSITORY SUMMARY REPORT", "step")
    
    for repo_name in sorted(repos):
        repo_path = repos_path / repo_name
        info = get_repo_info(repo_path)
        
        if info["status"] == "not_found":
            print(f"  ❌ {repo_name:<25} - Not found")
            continue
        
        # Determine display info
        if info["branch"] == "HEAD":
            # Detached HEAD
            if info["tag"]:
                status = f"📌 Tag: {info['tag']} @ {info['commit']}"
            else:
                status = f"🔖 Commit: {info['commit']} (detached)"
        else:
            # On a branch
            if info["tag"]:
                # Branch with tag on same commit
                status = f"🌿 Branch: {info['branch']} 📌 Tag: {info['tag']} @ {info['commit']}"
            else:
                status = f"🌿 Branch: {info['branch']} @ {info['commit']}"
        
        print(f"  ✅ {repo_name:<25} {status}")
    
    print()


def clone_repo(repo_name: str, repos_path: Path, ref: Optional[str] = None, ref_type: Optional[str] = None) -> bool:
    """Clone and setup a repository."""
    repo_config = config.GIT_REPOS[repo_name]
    repo_path = repos_path / repo_name
    
    header(f"📦 Processing {repo_name}", "step")
    
    # Clone if doesn't exist
    if not repo_path.exists():
        print(f"  ⬇️  Cloning...")
        cmd = ["git", "clone", "-b", repo_config["branch"], repo_config["url"], str(repo_path)]
        if not run_command(cmd, cwd=repos_path):
            return False
    else:
        print(f"  ✓ Already exists")
    
    # Fetch updates
    print(f"  🔄 Fetching updates...")
    if not run_command(["git", "fetch", "--all"], cwd=repo_path):
        return False
    
    # Checkout specific ref if requested
    if ref:
        print(f"  🔀 Checking out {ref_type} '{ref}'...")
        
        # Reset any local changes
        if not run_command(["git", "reset", "--hard"], cwd=repo_path):
            return False
        
        # Checkout the ref
        if not run_command(["git", "checkout", ref], cwd=repo_path):
            return False
        
        # If it's a branch, pull latest (commits and tags don't need pull)
        if ref_type == "branch":
            print(f"  ⬆️  Pulling latest...")
            if not run_command(["git", "pull", "origin", ref], cwd=repo_path):
                return False
        elif ref_type == "commit":
            print(f"  ✓ Detached HEAD at commit {ref}")
        elif ref_type == "tag":
            print(f"  ✓ Tag {ref} checked out")
    
    print(f"  ✅ {repo_name} ready")
    print("-" * 60)
    return True


def select_repos() -> List[str]:
    """Interactive repository selection."""
    choices = [
        questionary.Choice("🌟 All repositories", value="all"),
        questionary.Separator("─── By Server Type ───"),
        questionary.Choice("📦 Main Server (8 services)", value="main_server"),
        questionary.Choice("📊 Analytics Server (3 services)", value="analytics_server"),
        questionary.Separator("─── Individual Repositories ───"),
    ]
    
    for repo_name in sorted(config.GIT_REPOS.keys()):
        choices.append(questionary.Choice(f"  {repo_name}", value=repo_name))
    
    choices.extend([
        questionary.Separator(),
        questionary.Choice("⬅️  Back", value="back"),
    ])
    
    result = questionary.select(
        "Which repositories do you want to clone/update?",
        choices=choices,
        style=custom_style
    ).ask()
    
    if result is None or result == "back":
        return []
    
    if result == "all":
        return list(config.GIT_REPOS.keys())
    elif result == "main_server":
        # Main Server repositories
        return ['auth-service', 'archive', 'execution_server', 'execution-monitor-service', 
                'core_server', 'dict_service', 'ui']
    elif result == "analytics_server":
        # Analytics Server repositories
        return ['search_server', 'report_server', 'data_sync_service']
    else:
        return [result]


def build_tag_from_version(major: int, minor: int, patch: Optional[int] = None, rc_num: Optional[int] = None) -> str:
    """Build tag string from version numbers.
    
    Format: r{major}_{minor}[_{patch}][-rc{num}]
    Examples: r14_3_1, r14_3_1-rc1, r15_0-rc1
    """
    base_tag = f"r{major}_{minor}"
    if patch is not None:
        base_tag = f"{base_tag}_{patch}"
    if rc_num:
        return f"{base_tag}-rc{rc_num}"
    return base_tag


def get_available_tags(repos_path: Path, repo_name: str) -> List[str]:
    """Get list of available tags from a repository."""
    repo_path = repos_path / repo_name
    
    if not repo_path.exists():
        return []
    
    # Fetch latest tags
    subprocess.run(
        ["git", "fetch", "--tags"],
        cwd=repo_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    
    # Get all tags
    result = subprocess.run(
        ["git", "tag", "--sort=-version:refname"],
        cwd=repo_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    if result.returncode == 0:
        tags = [t.strip() for t in result.stdout.split('\n') if t.strip()]
        return tags
    
    return []


def select_from_available_tags(repos_path: Path, repos: List[str]) -> Optional[str]:
    """Select from available tags in repositories."""
    # Pick first repo to get tags from
    if not repos:
        print("❌ No repositories selected")
        return None
    
    repo_name = repos[0]
    
    print(f"\n📥 Fetching tags from {repo_name}...\n")
    tags = get_available_tags(repos_path, repo_name)
    
    if not tags:
        print(f"❌ No tags found in {repo_name}")
        print("   Try building a tag or entering manually\n")
        return None
    
    # Show most recent tags (limit to 20)
    display_tags = tags[:20]
    
    if len(tags) > 20:
        print(f"ℹ️  Showing 20 most recent tags (total: {len(tags)})\n")
    
    choices = [questionary.Choice(f"📌 {tag}", value=tag) for tag in display_tags]
    choices.extend([
        questionary.Separator(),
        questionary.Choice("⬅️  Back", value="back"),
    ])
    
    selected_tag = questionary.select(
        "Select a tag:",
        choices=choices,
        style=custom_style
    ).ask()
    
    if selected_tag == "back":
        return None
    
    if selected_tag:
        print(f"\n✓ Selected: {selected_tag}\n")
    
    return selected_tag


def select_tag_interactive() -> Optional[str]:
    """Interactive tag builder for Ingenium tag format."""
    print("\n📋 Ingenium Tag Format: r{major}_{minor}[_{patch}][-rc{num}]")
    print("   Examples: r14_3_1, r14_3_1-rc1, r15_0-rc1\n")
    
    # Ask for version numbers
    major = questionary.text(
        "Enter major version:",
        validate=lambda val: val.isdigit() or "Please enter a number",
        style=custom_style
    ).ask()
    
    if major is None:
        return None
    
    minor = questionary.text(
        "Enter minor version:",
        validate=lambda val: val.isdigit() or "Please enter a number",
        style=custom_style
    ).ask()
    
    if minor is None:
        return None
    
    patch = questionary.text(
        "Enter patch version (leave empty to skip):",
        validate=lambda val: val == "" or val.isdigit() or "Please enter a number or leave empty",
        style=custom_style
    ).ask()
    
    if patch is None:
        return None
    
    # Ask if RC or final release
    release_type = questionary.select(
        "Release type:",
        choices=[
            questionary.Choice("🚀 Final Release", value="final"),
            questionary.Choice("🧪 Release Candidate (RC)", value="rc"),
            questionary.Separator(),
            questionary.Choice("⬅️  Back", value="back"),
        ],
        style=custom_style
    ).ask()
    
    if release_type == "back":
        return None
    
    if release_type is None:
        return None
    
    rc_num = None
    if release_type == "rc":
        rc_input = questionary.text(
            "Enter RC number:",
            validate=lambda val: val.isdigit() or "Please enter a number",
            style=custom_style
        ).ask()
        
        if rc_input is None:
            return None
        rc_num = int(rc_input)
    
    tag = build_tag_from_version(int(major), int(minor), int(patch) if patch else None, rc_num)
    print(f"\n✓ Tag: {tag}\n")
    return tag


def select_ref(repos_path: Optional[Path] = None, repos: Optional[List[str]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Select branch, tag, or commit."""
    choices = [
        questionary.Choice("📌 Build tag (interactive - recommended)", value="tag_builder"),
    ]
    
    # Add option to select from available tags if repos are provided
    if repos_path and repos:
        choices.append(questionary.Choice("📋 Select from available tags", value="tag_list"))
    
    choices.extend([
        questionary.Choice("📝 Enter tag manually", value="tag"),
        questionary.Choice("🌿 Specific branch", value="branch"),
        questionary.Choice("🔖 Specific commit (hash)", value="commit"),
        questionary.Choice("⏭️  Use default branch (latest)", value="default"),
    ])
    
    choices.extend([
        questionary.Separator(),
        questionary.Choice("⬅️  Back", value="back"),
    ])
    
    ref_choice = questionary.select(
        "What do you want to checkout?",
        choices=choices,
        style=custom_style
    ).ask()
    
    if ref_choice is None or ref_choice == "back":
        return None, None
    
    if ref_choice == "tag_builder":
        ref = select_tag_interactive()
        if ref is None:
            return None, None
        return ref, "tag"
    
    if ref_choice == "tag_list":
        ref = select_from_available_tags(repos_path, repos)
        if ref is None:
            return None, None
        return ref, "tag"
    
    if ref_choice == "default":
        # Ask which default branch
        default_branch = questionary.select(
            "Which default branch?",
            choices=[
                questionary.Choice("devel (default)", value="devel"),
                questionary.Choice("main", value="main"),
                questionary.Choice("master", value="master"),
                questionary.Separator(),
                questionary.Choice("⬅️  Back", value="back"),
            ],
            style=custom_style
        ).ask()
        
        if default_branch == "back":
            return None, None
        
        if default_branch is None:
            return None, None
        
        return default_branch, "branch"
    
    if ref_choice == "commit":
        ref = questionary.text(
            "Enter commit hash (full or short):",
            style=custom_style
        ).ask()
    else:
        ref = questionary.text(
            f"Enter {ref_choice} name:",
            style=custom_style
        ).ask()
    
    if ref is None:
        return None, None
    
    return ref, ref_choice


def select_repos_path() -> Path:
    """Select or confirm repos directory."""
    default_path = Path.cwd() / "git_repos"
    
    use_default = questionary.confirm(
        f"Use default repos directory: {default_path}?",
        default=True,
        style=custom_style
    ).ask()
    
    if use_default is None:
        sys.exit(0)
    
    if use_default:
        return default_path
    
    custom_path = questionary.path(
        "Enter custom repos directory path:",
        default=str(default_path),
        style=custom_style
    ).ask()
    
    if custom_path is None:
        sys.exit(0)
    
    return Path(custom_path)


def clone_workflow():
    """Interactive clone workflow."""
    header("CLONE & CHECKOUT REPOSITORIES")
    
    # Select repos
    repos = select_repos()
    if not repos:
        print("❌ Operation cancelled")
        return
    
    print(f"\n✓ Selected {len(repos)} repository(ies)")
    
    # Select repos path first (needed to fetch tags)
    repos_path = select_repos_path()
    print(f"✓ Repos directory: {repos_path}")
    
    # Select ref (can now show available tags)
    ref, ref_type = select_ref(repos_path, repos)
    if ref:
        print(f"✓ Will checkout {ref_type}: {ref}")
    
    # Confirm
    header("SUMMARY", "step")
    print(f"  Repositories: {len(repos)}")
    for repo in repos:
        print(f"    • {repo}")
    
    if ref:
        print(f"  Checkout: {ref} ({ref_type})")
    print(f"  Location: {repos_path}")
    print()
    
    confirm = questionary.confirm(
        "Proceed with clone/update?",
        default=True,
        style=custom_style
    ).ask()
    
    if not confirm:
        print("❌ Operation cancelled")
        return
    
    # Create repos directory
    repos_path.mkdir(parents=True, exist_ok=True)
    
    # Process repos
    print("\n🚀 Starting clone/update process...\n")
    success_count = 0
    
    for repo_name in repos:
        if clone_repo(repo_name, repos_path, ref, ref_type):
            success_count += 1
    
    # Summary
    if success_count == len(repos):
        header(f"🎉 SUCCESS: All {success_count} repositories ready!", "success")
    else:
        header(f"⚠️  PARTIAL: {success_count}/{len(repos)} repositories processed", "warn")
    
    # Display detailed report of what each repo is on
    display_summary_report(repos, repos_path)


def status_workflow():
    """Show status of cloned repositories."""
    repos_path = select_repos_path()
    
    if not repos_path.exists():
        print(f"\n📁 Repos directory: {repos_path}")
        print("   ⚠️  Directory does not exist yet\n")
        return
    
    print(f"\n📁 Repos directory: {repos_path}")
    header("📊 REPOSITORY STATUS", "step")
    
    cloned = []
    not_cloned = []
    
    for repo_name in config.GIT_REPOS.keys():
        repo_path = repos_path / repo_name
        
        if repo_path.exists():
            info = get_repo_info(repo_path)
            
            # Determine display info
            if info["branch"] == "HEAD":
                # Detached HEAD
                if info["tag"]:
                    status = f"📌 Tag: {info['tag']} @ {info['commit']}"
                else:
                    status = f"🔖 Commit: {info['commit']} (detached)"
            else:
                # On a branch
                if info["tag"]:
                    status = f"🌿 Branch: {info['branch']} 📌 Tag: {info['tag']} @ {info['commit']}"
                else:
                    status = f"🌿 Branch: {info['branch']} @ {info['commit']}"
            
            cloned.append((repo_name, status))
        else:
            not_cloned.append(repo_name)
    
    if cloned:
        print(f"✅ Cloned repositories ({len(cloned)}/{len(config.GIT_REPOS)}):\n")
        for repo_name, status in sorted(cloned):
            print(f"  {repo_name:<25} {status}")
    
    if not_cloned:
        print(f"\n❌ Not cloned ({len(not_cloned)}):\n")
        for repo_name in sorted(not_cloned):
            print(f"  {repo_name}")
    
    print()


def build_workflow():
    """Interactive build images workflow."""
    header("BUILD DOCKER IMAGES")
    
    # Select repos path (create if doesn't exist)
    repos_path = select_repos_path()
    repos_path.mkdir(parents=True, exist_ok=True)
    
    print(f"✓ Repos directory: {repos_path}")
    
    # Select repos to build
    repos = select_repos()
    if not repos:
        print("❌ Operation cancelled")
        return
    
    print(f"\n✓ Selected {len(repos)} repository(ies)")
    
    # Determine repo for build command ("all" or single repo)
    if len(repos) == len(config.GIT_REPOS):
        build_repo = "all"
    elif len(repos) == 1:
        build_repo = repos[0]
    else:
        # Multiple but not all - build one at a time
        build_repo = None
    
    # Select version/ref to checkout and build
    print("\n⚠️  Code will be checked out before building")
    ref, ref_type = select_ref(repos_path, repos)
    
    if not ref:
        print("❌ Operation cancelled")
        return
    
    print(f"✓ Will checkout and build: {ref} ({ref_type})")
    
    # Image tag will match the code version
    if ref_type == "tag":
        image_tag = ref
        branch = None
    elif ref_type == "branch":
        image_tag = None
        branch = ref
    else:  # commit
        image_tag = None
        branch = None  # Will use commit hash
    
    # Additional options
    # Note: Default is to clear cache for clean builds
    no_cache = questionary.confirm(
        "Clear cache and rebuild everything? (Recommended)",
        default=True,
        style=custom_style
    ).ask()
    
    if no_cache is None:
        print("❌ Operation cancelled")
        return
    
    # Note: We don't use registry pushing in standard workflow
    registry = None
    
    # Confirm
    header("BUILD SUMMARY", "step")
    print(f"  Repositories: {len(repos)}")
    for repo in repos:
        print(f"    • {repo}")
    
    print(f"  Code version: {ref} ({ref_type})")
    if image_tag:
        print(f"  Image tag: {image_tag}")
    else:
        print(f"  Image tag: <branch>-<hash>")
        if branch:
            print(f"  Branch: {branch}")
    
    print(f"  Repos path: {repos_path}")
    print(f"  Build mode: {'Clean build (no cache)' if no_cache else 'Using cache'}")
    print(f"  Storage: Local VM (no registry push)")
    print()
    print("  📋 Will: Clone missing repos → Fetch latest → Checkout → Build")
    print()
    
    confirm = questionary.confirm(
        "Proceed with checkout + build?",
        default=True,
        style=custom_style
    ).ask()
    
    if not confirm:
        print("❌ Operation cancelled")
        return
    
    # Step 1: Clone/Fetch/Checkout code
    header("STEP 1: PREPARE CODE", "step")
    
    clone_script = Path(__file__).parent / "clone_repos.py"
    
    for repo in repos:
        repo_path = repos_path / repo
        
        if not repo_path.exists():
            # Clone if doesn't exist
            print(f"📦 Cloning {repo}...")
            repo_url = config.GIT_REPOS[repo]["url"]
            clone_cmd = ["git", "clone", repo_url, str(repo_path)]
            success = run_command(clone_cmd, cwd=repos_path)
            if not success:
                print(f"❌ Failed to clone {repo}")
                return
        else:
            # Fetch latest if exists
            print(f"📥 Fetching latest for {repo}...")
            fetch_cmd = ["git", "fetch", "--all", "--tags", "--prune"]
            success = run_command(fetch_cmd, cwd=repo_path)
            if not success:
                print(f"⚠️  Warning: Failed to fetch latest for {repo}")
        
        # Checkout the ref
        cmd = [sys.executable, str(clone_script), "--repo", repo, "--repos-path", str(repos_path)]
        
        if ref_type == "tag":
            cmd.extend(["--tag", ref])
        elif ref_type == "branch":
            cmd.extend(["--branch", ref])
        else:  # commit
            cmd.extend(["--commit", ref])
        
        print(f"🔄 Checking out {repo} @ {ref}...")
        success = run_command(cmd)
        
        if not success:
            print(f"❌ Failed to checkout {repo}")
            return
    
    print("\n✅ Code preparation complete!\n")
    
    # Build images
    print("\n🚀 Starting image build process...\n")
    
    # Find build_images.py script
    script_dir = Path(__file__).parent
    build_script = script_dir / "build_images.py"
    
    if not build_script.exists():
        print(f"❌ Error: build_images.py not found at {build_script}")
        return
    
    # Build command
    if build_repo:
        # Build all at once or single repo
        repos_to_build = [build_repo]
    else:
        # Build each repo individually
        repos_to_build = repos
    
    success_count = 0
    
    for repo in repos_to_build:
        cmd = [sys.executable, str(build_script), "--repo", repo, "--repos-path", str(repos_path)]
        
        if image_tag:
            cmd.extend(["--tag", image_tag])
        elif branch:
            cmd.extend(["--branch", branch])
        
        if no_cache:
            cmd.append("--no-cache")
        
        header(f"Building: {repo}", "step")
        
        # Stream output in real-time for build commands
        success = run_command(cmd, stream_output=True)
        
        if success:
            success_count += 1
    
    # Summary
    if success_count == len(repos_to_build):
        header(f"🎉 SUCCESS: All {success_count} builds completed!", "success")
    else:
        header(f"⚠️  PARTIAL: {success_count}/{len(repos_to_build)} builds completed", "warn")


def get_instances():
    """Get list of deployment instances.
    
    Returns:
        List of instance directory names that have ing_envs.sh
    """
    deployments_path = Path.cwd()
    instances = []
    
    # Directories to exclude from instance search
    excluded_dirs = [
        'git_repos', 'project_instance_template', 'docs', 'venv', '__pycache__'
    ]
    
    for item in deployments_path.iterdir():
        if item.is_dir() and not item.name.startswith('.') and item.name not in excluded_dirs:
            env_file = item / "ing_envs.sh"
            if env_file.exists():
                instances.append(item.name)
    
    return sorted(instances)


def setup_status_workflow():
    """Check setup status for deployment instances."""
    deployments_path = Path.cwd()
    
    # Find existing instances
    instances = get_instances()
    
    if not instances:
        print("\n❌ No deployment instances found!")
        print("   Create one using: '⚙️  Setup Instance'\n")
        return
    
    # Let user select instance
    header("🔍 CHECK SETUP STATUS")
    
    instance_choices = list(instances) + [questionary.Separator(), questionary.Choice("⬅️  Back", value="back")]
    instance_name = questionary.select(
        "Select instance to check:",
        choices=instance_choices,
        style=custom_style
    ).ask()
    
    if instance_name == "back":
        return
    
    if not instance_name:
        return
    
    instance_path = deployments_path / instance_name
    
    # Ask which machine this check is running from
    print("Which server VM are you checking?\n")
    machine_type = questionary.select(
        "Server type:",
        choices=[
            questionary.Choice("📦 Main Server VM", value="main"),
            questionary.Choice("📊 Analytics Server VM", value="analytics"),
            questionary.Separator(),
            questionary.Choice("⬅️  Back", value="back"),
        ],
        style=custom_style
    ).ask()
    
    if machine_type == "back":
        return
    
    if not machine_type:
        return
    
    # Read RTAG from ing_envs.sh
    env_file = instance_path / "ing_envs.sh"
    rtag = None
    if env_file.exists():
        content = env_file.read_text()
        for line in content.split('\n'):
            if line.startswith('export RTAG='):
                rtag = line.split('=')[1].strip()
                break
    
    machine_label = {
        'main': 'Main Server VM',
        'analytics': 'Analytics Server VM'
    }
    
    header(f"Instance: {instance_name}", "step")
    if rtag:
        print(f"  RTAG: {rtag}")
    print(f"  Location: {instance_path}")
    print(f"  Machine: {machine_label[machine_type]}\n")
    
    # Track completion
    checks = {
        'config': False,
        'secrets': False,
        'ssl_main': False,
        'ssl_analytics': False,
        'data_dirs': False,
        'images': False
    }
    
    # 1. Check configuration files
    print("📄 Configuration Files:")
    if env_file.exists():
        print("  ✓ ing_envs.sh exists")
        checks['config'] = True
    else:
        print("  ❌ ing_envs.sh missing")
    
    secrets_file = instance_path / "ing_secrets.sh"
    if secrets_file.exists():
        # Check if secrets are filled in (not just template)
        content = secrets_file.read_text()
        if 'export PRIVATE_PEM=' in content and len(content) > 500:
            print("  ✓ ing_secrets.sh exists and appears configured")
            checks['secrets'] = True
        else:
            print("  ⚠️  ing_secrets.sh exists but may be empty template")
            print("  ⚠️  WARNING: Both ing_envs.sh and ing_secrets.sh must be IDENTICAL on Main and Analytics servers!")
    else:
        print("  ❌ ing_secrets.sh missing")
    
    # Important note about configuration consistency
    print("\n  ⚠️  IMPORTANT: ing_envs.sh and ing_secrets.sh must be identical on both servers")
    
    # 2. Check SSL certificates (based on server type)
    print("\n🔐 SSL Certificates:")
    if machine_type == 'main':
        ssl_main_crt = instance_path / "ssl" / "ing_https.crt"
        ssl_main_key = instance_path / "ssl" / "ing_https.key"
        if ssl_main_crt.exists() and ssl_main_key.exists():
            print("  ✓ Main Server SSL (crt + key)")
            checks['ssl_main'] = True
        else:
            print("  ❌ Main Server SSL missing")
            if not ssl_main_crt.exists():
                print("     Missing: ssl/ing_https.crt")
            if not ssl_main_key.exists():
                print("     Missing: ssl/ing_https.key")
        # Mark analytics SSL as not applicable for main server
        checks['ssl_analytics'] = True  # N/A for main server
    elif machine_type == 'analytics':
        ssl_analytics_crt = instance_path / "ssl_analytics" / "ing_https.crt"
        ssl_analytics_key = instance_path / "ssl_analytics" / "ing_https.key"
        if ssl_analytics_crt.exists() and ssl_analytics_key.exists():
            print("  ✓ Analytics Server SSL (crt + key)")
            checks['ssl_analytics'] = True
        else:
            print("  ❌ Analytics Server SSL missing")
            if not ssl_analytics_crt.exists():
                print("     Missing: ssl_analytics/ing_https.crt")
            if not ssl_analytics_key.exists():
                print("     Missing: ssl_analytics/ing_https.key")
        # Mark main SSL as not applicable for analytics server
        checks['ssl_main'] = True  # N/A for analytics server
    
    # 3. Check Docker images (based on server type)
    print("\n🐳 Docker Images:")
    if rtag:
        try:
            result = subprocess.run(
                ['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )
            images = result.stdout.strip().split('\n')
            
            # Define required images per server type
            if machine_type == 'main':
                required_images = [
                    f'ingenium/auth_service:{rtag}',
                    f'ingenium/archive_ing:{rtag}',
                    f'ingenium/exec_server:{rtag}',
                    f'ingenium/execution_monitor:{rtag}',
                    f'ingenium/core_server:{rtag}',
                    f'ingenium/dict_service:{rtag}',
                    f'ingenium/ui:{rtag}',
                    f'ingenium/ui_nginx:{rtag}',
                ]
                print("  Checking Main Server images...")
            else:  # analytics
                required_images = [
                    f'ingenium/search_server:{rtag}',
                    f'ingenium/report_server:{rtag}',
                    f'ingenium/data_sync_service:{rtag}',
                ]
                print("  Checking Analytics Server images...")
            
            found = [img for img in required_images if img in images]
            missing = [img for img in required_images if img not in images]
            
            print(f"  Found: {len(found)}/{len(required_images)} required images")
            if len(found) == len(required_images):
                print(f"  ✓ All required images built for {machine_label[machine_type]}")
                checks['images'] = True
            elif missing:
                print(f"  ⚠️  Missing {len(missing)} images:")
                for img in missing[:5]:
                    print(f"     - {img}")
                if len(missing) > 5:
                    print(f"     ... and {len(missing) - 5} more")
        except Exception as e:
            print(f"  ❌ Could not check Docker images: {e}")
    else:
        print("  ⚠️  Cannot check images (RTAG not found)")
    
    # 4. Data directories (check based on machine type)
    print("\n📂 Data Directories:")
    if machine_type == 'main':
        print("  Checking Main Server directories...")
        required_dirs = {
            '/data/auth': Path('/data/auth').exists(),
            '/data/arangodb': Path('/data/arangodb').exists(),
            '/data/arangodb_dict_service': Path('/data/arangodb_dict_service').exists(),
            '/data/file_server': Path('/data/file_server').exists(),
        }
        all_exist = all(required_dirs.values())
        for dir_path, exists in required_dirs.items():
            status = "✓" if exists else "❌"
            print(f"  {status} {dir_path}")
        
        if all_exist:
            print("  ✓ All Main Server directories exist")
            checks['data_dirs'] = True
        else:
            missing = [d for d, e in required_dirs.items() if not e]
            print(f"  ⚠️  Missing {len(missing)} directories")
    elif machine_type == 'analytics':
        print("  Checking Analytics Server directories...")
        required_dirs = {
            '/data/arangodb': Path('/data/arangodb').exists(),
            '/data/elasticsearch': Path('/data/elasticsearch').exists(),
            '/data/elasticsearch/data': Path('/data/elasticsearch/data').exists(),
        }
        all_exist = all(required_dirs.values())
        for dir_path, exists in required_dirs.items():
            status = "✓" if exists else "❌"
            print(f"  {status} {dir_path}")
        
        if all_exist:
            print("  ✓ All Analytics Server directories exist")
            checks['data_dirs'] = True
        else:
            missing = [d for d, e in required_dirs.items() if not e]
            print(f"  ⚠️  Missing {len(missing)} directories")
    
    # Summary
    header("📊 SETUP COMPLETION SUMMARY", "step")
    
    total_checks = len([v for v in checks.values() if v])
    total_required = len(checks)
    percentage = (total_checks / total_required) * 100
    
    status_icon = "✅" if total_checks == total_required else "⚠️"
    print(f"\n{status_icon} Overall: {total_checks}/{total_required} checks passed ({percentage:.0f}%)\n")
    
    print("Checklist:")
    print(f"  [{'✓' if checks['config'] else ' '}] Configuration files")
    print(f"  [{'✓' if checks['secrets'] else ' '}] Secrets configured")
    if machine_type == 'main':
        print(f"  [{'✓' if checks['ssl_main'] else ' '}] SSL certificates (Main Server)")
    elif machine_type == 'analytics':
        print(f"  [{'✓' if checks['ssl_analytics'] else ' '}] SSL certificates (Analytics Server)")
    print(f"  [{'✓' if checks['data_dirs'] else ' '}] Data directories ({machine_label[machine_type]})")
    print(f"  [{'✓' if checks['images'] else ' '}] Docker images built")
    
    # Next steps
    if total_checks < total_required:
        header("📋 NEXT STEPS", "step")
        
        if not checks['secrets']:
            print("1. Review/edit secrets file:")
            print(f"   $ nano {instance_path}/ing_secrets.sh")
            print(f"\n   ⚠️  CRITICAL: After editing, copy BOTH files to the other server:")
            print(f"   Both ing_envs.sh and ing_secrets.sh must be IDENTICAL on Main and Analytics VMs")
            print(f"   $ scp {instance_path}/ing_envs.sh <other-server>:{instance_path}/")
            print(f"   $ scp {instance_path}/ing_secrets.sh <other-server>:{instance_path}/")
        
        if (machine_type == 'main' and not checks['ssl_main']) or (machine_type == 'analytics' and not checks['ssl_analytics']):
            print("2. Add SSL certificates:")
            print(f"   Get from your organization's certificate authority")
            if machine_type == 'main' and not checks['ssl_main']:
                print(f"   Place in: {instance_path}/ssl/")
            elif machine_type == 'analytics' and not checks['ssl_analytics']:
                print(f"   Place in: {instance_path}/ssl_analytics/")
        
        if not checks['data_dirs']:
            print("3. Create missing data directories:")
            if machine_type == 'main':
                print(f"   $ mkdir -p /data && cd /data")
                print(f"   $ mkdir auth && chmod 777 auth")
                print(f"   $ mkdir arangodb && chmod 777 arangodb")
                print(f"   $ mkdir arangodb_dict_service && chmod 777 arangodb_dict_service")
                print(f"   $ mkdir file_server && chmod 777 file_server")
            elif machine_type == 'analytics':
                print(f"   $ mkdir -p /data && cd /data")
                print(f"   $ mkdir arangodb && chmod 777 arangodb")
                print(f"   $ mkdir -p elasticsearch/data && chmod 777 elasticsearch elasticsearch/data")
        
        if not checks['images']:
            print("4. Build Docker images:")
            print(f"   Option 1 - Use wizard:")
            print(f"   $ ./run.sh")
            print(f"   Select: '🔨 Build Docker Images'")
            if machine_type == 'main':
                print(f"   Choose: '📦 Main Server (8 services)'")
            else:
                print(f"   Choose: '📊 Analytics Server (3 services)'")
            print(f"\n   Option 2 - Command line:")
            print(f"   $ ./build_images.py --repo all --tag {rtag}")
    else:
        print(f"\n🎉 Instance '{instance_name}' is ready for deployment!")
    
    print()


def deploy_workflow():
    """Deploy Ingenium services workflow."""
    header("🚀 DEPLOY INGENIUM SERVICES")
    
    # Get list of instances
    instances = get_instances()
    if not instances:
        print("\n❌ No instances found.")
        print("   Create an instance first using 'Setup Instance' option.\n")
        return
    
    # Select instance
    deploy_instance_choices = [questionary.Choice(f"  {name}", value=name) for name in sorted(instances)]
    deploy_instance_choices.extend([questionary.Separator(), questionary.Choice("⬅️  Back", value="back")])
    instance_name = questionary.select(
        "Select instance to deploy:",
        choices=deploy_instance_choices,
        style=custom_style
    ).ask()
    
    if instance_name == "back":
        return
    
    if not instance_name:
        return
    
    instance_path = Path.cwd() / instance_name
    print(f"\n✓ Instance: {instance_name}")
    print(f"  Location: {instance_path}")
    
    # Check for running containers
    header("CHECKING FOR RUNNING SERVICES", "step")
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'label=io.ingenium.deployment=true', '--format', 'table {{.Names}}\t{{.Status}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )
        
        running_output = result.stdout.strip()
        if running_output and len(running_output.split('\n')) > 1:
            print("\n⚠️  WARNING: Ingenium containers are already running!")
            print("\n" + running_output + "\n")
            
            header("⚠️  DEPLOYMENT CONFLICT WARNING", "warn")
            print("  Running containers detected. Deploying now may cause:")
            print("    • Container name conflicts")
            print("    • Port conflicts")
            print("  • Deployment failures")
            info("RECOMMENDED: Use '🔄 Restart Services' to cleanly restart")
            info("OR use '🛑 Stop/Cleanup Services' before deploying")
            
            proceed = questionary.confirm(
                "\nDo you want to proceed with deployment anyway? (Not recommended)",
                default=False,
                style=custom_style
            ).ask()
            
            if not proceed:
                print("\n✓ Deployment cancelled. Use Restart or Stop/Cleanup first.\n")
                return
            
            print("\n⚠️  Proceeding with deployment (may encounter errors)...\n")
        else:
            print("\n✓ No running containers detected - safe to deploy")
    except subprocess.CalledProcessError:
        print("\n⚠️  Could not check for running containers")
    
    # Determine server type
    header("SERVER CONFIGURATION", "step")
    server_type = questionary.select(
        "Which server are you deploying on?",
        choices=[
            questionary.Choice("📦 Main Server", value="main"),
            questionary.Choice("📊 Analytics Server", value="analytics"),
            questionary.Separator(),
            questionary.Choice("⬅️  Back", value="back"),
        ],
        style=custom_style
    ).ask()
    
    if not server_type or server_type == "back":
        return
    
    # Select log driver
    log_driver = questionary.select(
        "Select log driver:",
        choices=[
            questionary.Choice("📝 Splunk (production)", value="splunk"),
            questionary.Choice("💾 Local (development)", value="local"),
            questionary.Separator(),
            questionary.Choice("⬅️  Back", value="back"),
        ],
        style=custom_style
    ).ask()
    
    if not log_driver or log_driver == "back":
        return
    
    # Define services per server type
    if server_type == "main":
        available_services = [
            "auth_service",
            "archive_ing",
            "exec_server",
            "execution_monitor",
            "core_server",
            "dict_service",
            "ui",
            "ui_nginx"
        ]
        default_service = "ui_nginx"
    else:  # analytics
        available_services = [
            "search_server",
            "report_server",
            "data_sync_service",
            "analytics_nginx"
        ]
        default_service = "analytics_nginx"
    
    # Ask which services to deploy
    service_choices = [
        questionary.Choice("🌟 All services", value="all"),
        questionary.Separator("─── Individual Services ───"),
    ]
    for service in available_services:
        service_choices.append(questionary.Choice(f"  {service}", value=service))
    service_choices.extend([questionary.Separator(), questionary.Choice("⬅️  Back", value="back")])
    
    service_selection = questionary.select(
        "Which service(s) to deploy?",
        choices=service_choices,
        style=custom_style
    ).ask()
    
    if not service_selection or service_selection == "back":
        return
    
    # Determine services to deploy
    if service_selection == "all":
        # Deploy nginx only - dependencies will pull in all other services
        if server_type == "main":
            services_to_deploy = "ui_nginx"
        else:  # analytics
            services_to_deploy = "analytics_nginx"
    else:
        services_to_deploy = service_selection
    
    # Show deployment summary
    header("DEPLOYMENT SUMMARY", "step")
    print(f"  Instance:    {instance_name}")
    print(f"  Server:      {'Main Server' if server_type == 'main' else 'Analytics Server'}")
    print(f"  Log Driver:  {log_driver}")
    if service_selection == "all":
        print(f"  Service:     {services_to_deploy} (starts all services via dependencies)")
    else:
        print(f"  Service:     {service_selection}")
    print()
    
    # Confirm deployment
    confirm = questionary.confirm(
        "\nProceed with deployment?",
        default=True,
        style=custom_style
    ).ask()
    
    if not confirm:
        print("\n❌ Deployment cancelled.\n")
        return
    
    # Build command
    if server_type == "main":
        script = "./run_ing.sh"
    else:
        script = "./run_ing_analytics.sh"
    
    cmd = f"{script} -i {instance_name} -l {log_driver} {services_to_deploy}"
    
    header("DEPLOYING SERVICES", "step")
    print(f"\nRunning: {cmd}\n")
    
    # Execute deployment
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=Path.cwd(),
            check=False
        )
        
        if result.returncode == 0:
            header("🎉 DEPLOYMENT SUCCESSFUL!", "success")
            print(f"  Services are now running for instance '{instance_name}'")
            print(f"\n  To check status:")
            print(f"    $ docker ps")
            print(f"\n  To view logs:")
            print(f"    $ docker logs <service_name>\n")
        else:
            header("⚠️  DEPLOYMENT COMPLETED WITH WARNINGS", "warn")
            print(f"  Check the output above for any errors.")
            print(f"\n  To check status:")
            print(f"    $ docker ps\n")
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}\n")


def stop_cleanup_workflow():
    """Stop and cleanup Ingenium services workflow."""
    header("🛑 STOP AND CLEANUP SERVICES")
    
    # Show currently running containers
    print("\n📊 Currently Running Containers:\n")
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'label=io.ingenium.deployment=true', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Image}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )
        
        running_output = result.stdout.strip()
        if running_output and len(running_output.split('\n')) > 1:
            print(running_output)
            running_containers = running_output.split('\n')[1:]  # Skip header
            container_count = len(running_containers)
            print(f"\n✓ Found {container_count} running Ingenium container(s)")
        else:
            print("  No Ingenium containers currently running.")
            print("\n✓ Nothing to clean up!\n")
            return
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Could not check running containers: {e}")
        return
    
    # Show stopped containers
    print("\n📦 Stopped Ingenium Containers:\n")
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--filter', 'label=io.ingenium.deployment=true', '--filter', 'status=exited', '--format', 'table {{.Names}}\t{{.Status}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )
        
        stopped_output = result.stdout.strip()
        if stopped_output and len(stopped_output.split('\n')) > 1:
            print(stopped_output)
            stopped_containers = stopped_output.split('\n')[1:]  # Skip header
            stopped_count = len(stopped_containers)
            print(f"\n✓ Found {stopped_count} stopped Ingenium container(s)")
        else:
            print("  No stopped Ingenium containers found.")
    except subprocess.CalledProcessError:
        print("  Could not check stopped containers.")
    
    # Show what will be cleaned
    header("🧹 CLEANUP ACTION", "step")
    print("  This will:")
    print("    • Stop all running Ingenium containers")
    print("    • Remove all Ingenium containers (running and stopped)")
    warn("This will stop ALL Ingenium services on this server!")
    
    # Confirm cleanup
    confirm = questionary.confirm(
        "\nProceed with cleanup?",
        default=False,
        style=custom_style
    ).ask()
    
    if not confirm:
        print("\n❌ Cleanup cancelled.\n")
        return
    
    # Perform cleanup - single command approach
    header("CLEANING UP", "step")
    
    cleanup_cmd = 'docker stop $(docker ps -a -q --filter label=io.ingenium.deployment=true) && docker rm -f $(docker ps -a -q --filter label=io.ingenium.deployment=true)'
    
    print(f"\nRunning: {cleanup_cmd}\n")
    
    try:
        result = subprocess.run(
            cleanup_cmd,
            shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=120
        )
        
        if result.returncode == 0:
            header("🎉 CLEANUP COMPLETE!", "success")
            print("  All Ingenium services have been stopped and removed.")
        else:
            header("⚠️  CLEANUP COMPLETED WITH WARNINGS", "warn")
            if result.stderr:
                print(f"\nWarnings:\n{result.stderr}")
    except subprocess.TimeoutExpired:
        print("\n❌ Cleanup timed out after 120 seconds")
    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")
    
    print(f"\n  To verify:")
    print(f"    $ docker ps")
    print(f"    $ docker ps -a")
    print(f"\n  To redeploy:")
    info("Use '🚀 Deploy Services' from main menu\n")


def restart_services_workflow():
    """Restart Ingenium services workflow (stop/cleanup + redeploy)."""
    header("🔄 RESTART INGENIUM SERVICES")
    print(f"{C.GRAY}")
    print(f"    {'1':>3}. Stop and remove all running Ingenium containers")
    print(f"    {'2':>3}. Redeploy services with your selected configuration")
    print(f"{C.RESET}")
    
    # Show currently running containers
    print("\n📊 Currently Running Containers:\n")
    has_running = False
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'label=io.ingenium.deployment=true', '--format', 'table {{.Names}}\t{{.Status}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )
        
        running_output = result.stdout.strip()
        if running_output and len(running_output.split('\n')) > 1:
            print(running_output)
            has_running = True
        else:
            print("  No Ingenium containers currently running.")
    except subprocess.CalledProcessError:
        print("  Could not check running containers.")
    
    # Get list of instances
    instances = get_instances()
    if not instances:
        print("\n❌ No instances found.")
        print("   Create an instance first using 'Setup Instance' option.\n")
        return
    
    # Select instance
    restart_instance_choices = [questionary.Choice(f"  {name}", value=name) for name in sorted(instances)]
    restart_instance_choices.extend([questionary.Separator(), questionary.Choice("⬅️  Back", value="back")])
    instance_name = questionary.select(
        "Select instance to restart:",
        choices=restart_instance_choices,
        style=custom_style
    ).ask()
    
    if not instance_name or instance_name == "back":
        return
    
    instance_path = Path.cwd() / instance_name
    print(f"\n✓ Instance: {instance_name}")
    
    # Determine server type
    server_type = questionary.select(
        "Which server are you restarting?",
        choices=[
            questionary.Choice("📦 Main Server", value="main"),
            questionary.Choice("📊 Analytics Server", value="analytics"),
            questionary.Separator(),
            questionary.Choice("⬅️  Back", value="back"),
        ],
        style=custom_style
    ).ask()
    
    if not server_type or server_type == "back":
        return
    
    # Select log driver
    log_driver = questionary.select(
        "Select log driver:",
        choices=[
            questionary.Choice("📝 Splunk (production)", value="splunk"),
            questionary.Choice("💾 Local (development)", value="local"),
            questionary.Separator(),
            questionary.Choice("⬅️  Back", value="back"),
        ],
        style=custom_style
    ).ask()
    
    if not log_driver or log_driver == "back":
        return
    
    # Define services per server type
    if server_type == "main":
        available_services = [
            "auth_service",
            "archive_ing",
            "exec_server",
            "execution_monitor",
            "core_server",
            "dict_service",
            "ui",
            "ui_nginx"
        ]
        default_service = "ui_nginx"
    else:  # analytics
        available_services = [
            "search_server",
            "report_server",
            "data_sync_service",
            "analytics_nginx"
        ]
        default_service = "analytics_nginx"
    
    # Ask which services to restart
    service_choices = [
        questionary.Choice("🌟 All services", value="all"),
        questionary.Separator("─── Individual Services ───"),
    ]
    for service in available_services:
        service_choices.append(questionary.Choice(f"  {service}", value=service))
    service_choices.extend([questionary.Separator(), questionary.Choice("⬅️  Back", value="back")])
    
    service_selection = questionary.select(
        "Which service(s) to restart?",
        choices=service_choices,
        style=custom_style
    ).ask()
    
    if not service_selection or service_selection == "back":
        return
    
    # Determine services to deploy
    if service_selection == "all":
        # Deploy nginx only - dependencies will pull in all other services
        if server_type == "main":
            services_to_deploy = "ui_nginx"
        else:  # analytics
            services_to_deploy = "analytics_nginx"
    else:
        services_to_deploy = service_selection
    
    # Confirm restart
    header("RESTART SUMMARY", "step")
    print(f"  Instance:    {instance_name}")
    print(f"  Server:      {'Main Server' if server_type == 'main' else 'Analytics Server'}")
    print(f"  Log Driver:  {log_driver}")
    if service_selection == "all":
        print(f"  Service:     {services_to_deploy} (starts all services via dependencies)")
        if has_running:
            print(f"\n  ⚠️  Will stop and remove all running containers before redeploying")
    else:
        print(f"  Service:     {service_selection}")
        print(f"\n  ℹ️  Will restart only this service (others remain running)")
    print()
    
    confirm = questionary.confirm(
        "\nProceed with restart?",
        default=True,
        style=custom_style
    ).ask()
    
    if not confirm:
        print("\n❌ Restart cancelled.\n")
        return
    
    # Step 1: Cleanup (only if restarting ALL services)
    if service_selection == "all" and has_running:
        header("STEP 1: CLEANING UP ALL CONTAINERS", "step")
        
        cleanup_cmd = 'docker stop $(docker ps -a -q --filter label=io.ingenium.deployment=true) && docker rm -f $(docker ps -a -q --filter label=io.ingenium.deployment=true)'
        
        print(f"\nRunning: {cleanup_cmd}\n")
        
        try:
            result = subprocess.run(
                cleanup_cmd,
                shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print("✓ Cleanup complete")
            else:
                print("⚠️  Cleanup completed with warnings")
                if result.stderr:
                    print(f"Warnings: {result.stderr}")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
            print("Continuing with deployment...")
        
        step_label = "STEP 2: DEPLOYING SERVICES..."
    else:
        step_label = "RESTARTING SERVICE..."
    
    # Step 2: Deploy (or just restart individual service)
    header(step_label, "step")
    
    # Build command
    if server_type == "main":
        script = "./run_ing.sh"
    else:
        script = "./run_ing_analytics.sh"
    
    cmd = f"{script} -i {instance_name} -l {log_driver} {services_to_deploy}"
    
    print(f"\nRunning: {cmd}\n")
    
    # Execute deployment
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=Path.cwd(),
            check=False
        )
        
        if result.returncode == 0:
            header("🎉 RESTART SUCCESSFUL!", "success")
            print(f"  Services have been restarted for instance '{instance_name}'")
            print(f"\n  To check status:")
            print(f"    $ docker ps")
            print(f"\n  To view logs:")
            print(f"    $ docker logs <service_name>\n")
        else:
            header("⚠️  RESTART COMPLETED WITH WARNINGS", "warn")
            print(f"  Check the output above for any errors.")
            print(f"\n  To check status:")
            print(f"    $ docker ps\n")
    except Exception as e:
        print(f"\n❌ Restart failed: {e}\n")


def main_menu():
    """Main menu."""
    repo_count = len(config.GIT_REPOS)
    dim(f"Configured repositories: {repo_count}")
    print()
    print(f"{C.CYAN}  ┌───────────────────────────────────────────────────────────────────┐")
    print(f"  │                                                                   │")
    print(f"  │   📥 Clone  ───►  🔨 Build  ───►  ⚙️  Configure  ───►  🚀 Deploy   │")
    print(f"  │                                                                   │")
    print(f"  └───────────────────────────────────────────────────────────────────┘{C.RESET}")
    print()
    while True:
        choice = questionary.select(
            "Select an option:",
            choices=[
                questionary.Separator(" "),
                questionary.Separator("─── BUILD & DEPLOY ──────────────────────────────────────"),
                questionary.Separator(" "),
                questionary.Choice("📥 Clone/Update Repositories  — fetch code & tags", value="clone"),
                questionary.Choice("🔨 Build Docker Images        — build from source", value="build"),
                questionary.Choice("⚙️  Configure Instance         — new instance or update RTAG", value="setup"),
                questionary.Choice("🚀 Deploy Services            — start containers", value="deploy"),
                questionary.Separator(" "),
                questionary.Separator("─── INSTANCE SETUP (one-time) ───────────────────────────"),
                questionary.Separator(" "),
                questionary.Choice("📂 Create Data Directories    — /data dirs on server VMs", value="data_dirs"),
                questionary.Choice("🔍 Check Setup Status         — verify instance config", value="setup_status"),
                questionary.Separator(" "),
                questionary.Separator("─── OPERATIONS ─────────────────────────────────────────"),
                questionary.Separator(" "),
                questionary.Choice("🔄 Restart Services           — stop + redeploy", value="restart"),
                questionary.Choice("🛑 Stop/Cleanup Services      — remove containers", value="stop"),
                questionary.Choice("📊 Show Repository Status     — branches & tags info", value="status"),
                questionary.Separator(" "),
                questionary.Separator("────────────────────────────────────────────────────────"),
                questionary.Choice("❌ Exit", value="exit"),
            ],
            style=custom_style
        ).ask()
        
        if choice is None or choice == "exit":
            print(f"\n{C.CYAN}  👋 Goodbye!{C.RESET}\n")
            break
        
        if choice == "clone":
            clone_workflow()
            
            # Ask if want to continue
            continue_choice = questionary.confirm(
                "\nReturn to main menu?",
                default=True,
                style=custom_style
            ).ask()
            
            if not continue_choice:
                print(f"\n{C.CYAN}  👋 Goodbye!{C.RESET}\n")
                break
        elif choice == "build":
            build_workflow()
            
            # Ask if want to continue
            continue_choice = questionary.confirm(
                "\nReturn to main menu?",
                default=True,
                style=custom_style
            ).ask()
            
            if not continue_choice:
                print(f"\n{C.CYAN}  👋 Goodbye!{C.RESET}\n")
                break
        elif choice == "setup":
            # Run setup wizard
            setup_script = Path.cwd() / "setup_instance.py"
            if setup_script.exists():
                run_command([sys.executable, str(setup_script)], stream_output=True)
            else:
                print("❌ Error: setup_instance.py not found")
            
            # Ask if want to continue
            continue_choice = questionary.confirm(
                "\nReturn to main menu?",
                default=True,
                style=custom_style
            ).ask()
            
            if not continue_choice:
                print(f"\n{C.CYAN}  👋 Goodbye!{C.RESET}\n")
                break
        elif choice == "data_dirs":
            # Show data directory creation instructions
            header("📂 DATA DIRECTORY SETUP")
            print("\nThese directories must be created on your target server VMs.")
            print("Choose which server you're setting up:\n")
            
            server_type = questionary.select(
                "Which server?",
                choices=[
                    questionary.Choice("📦 Main Server", value="main"),
                    questionary.Choice("📊 Analytics Server", value="analytics"),
                    questionary.Choice("🔄 Both (show all)", value="both"),
                    questionary.Separator(),
                    questionary.Choice("⬅️  Back", value="back"),
                ],
                style=custom_style
            ).ask()
            
            if server_type == "back" or server_type is None:
                continue
            
            if server_type in ["main", "both"]:
                header("📦 MAIN SERVER - Create these directories", "step")
                print("\nSSH into your Main Server VM and run:")
                print("\n$ mkdir -p /data && cd /data")
                print("$ mkdir auth && chmod 777 auth")
                print("$ mkdir arangodb && chmod 777 arangodb")
                print("$ mkdir arangodb_dict_service && chmod 777 arangodb_dict_service")
                print("$ mkdir file_server && chmod 777 file_server")
                print("\nVerify:")
                print("$ ls -ld auth arangodb arangodb_dict_service file_server")
                print("All should show 'drwxrwxrwx' (777 permissions)")
            
            if server_type in ["analytics", "both"]:
                header("📊 ANALYTICS SERVER - Create these directories", "step")
                print("\nSSH into your Analytics Server VM and run:")
                print("\n$ mkdir -p /data && cd /data")
                print("$ mkdir arangodb && chmod 777 arangodb")
                print("$ mkdir -p elasticsearch/data && chmod 777 elasticsearch elasticsearch/data")
                print("\nVerify:")
                print("$ ls -ld arangodb elasticsearch elasticsearch/data")
                print("All should show 'drwxrwxrwx' (777 permissions)")
            
            header("ℹ️  Notes", "step")
            print("  - Both servers need /data/arangodb (Main=archive, Analytics=replica)")
            print("  - Elasticsearch needs nested data/ subdirectory")
            print("  - All directories require 777 permissions for Docker\n")
            
            # Only offer automatic creation if specific server type selected (not "both")
            if server_type in ["main", "analytics"]:
                create_now = questionary.confirm(
                    "Do you want to create these directories now on this server?",
                    default=False,
                    style=custom_style
                ).ask()
                
                if create_now:
                    header("Creating directories", "step")
                    
                    if server_type == "main":
                        dirs_to_create = [
                            '/data/auth',
                            '/data/arangodb',
                            '/data/arangodb_dict_service',
                            '/data/file_server'
                        ]
                    else:  # analytics
                        dirs_to_create = [
                            '/data/arangodb',
                            '/data/elasticsearch',
                            '/data/elasticsearch/data'
                        ]
                    
                    for dir_path in dirs_to_create:
                        try:
                            # Create directory
                            result = subprocess.run(
                                ['sudo', 'mkdir', '-p', dir_path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True,
                                check=True
                            )
                            # Set permissions
                            result = subprocess.run(
                                ['sudo', 'chmod', '777', dir_path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True,
                                check=True
                            )
                            print(f"  ✓ Created: {dir_path}")
                        except subprocess.CalledProcessError as e:
                            print(f"  ❌ Failed to create {dir_path}: {e}")
                            if e.stderr:
                                print(f"     Error: {e.stderr.strip()}")
                    
                    header("🎉 Directory creation complete!", "success")
            
            # Automatically return to main menu
        elif choice == "setup_status":
            # Check setup status for instances
            setup_status_workflow()
            # Automatically return to main menu
        elif choice == "deploy":
            # Deploy services workflow
            deploy_workflow()
            # Automatically return to main menu
        elif choice == "restart":
            # Restart services workflow
            restart_services_workflow()
            # Automatically return to main menu
        elif choice == "stop":
            # Stop and cleanup services workflow
            stop_cleanup_workflow()
            # Automatically return to main menu
        elif choice == "status":
            status_workflow()
            # Automatically return to main menu after showing status


def main():
    """Main entry point."""
    try:
        print_banner()
        main_menu()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
