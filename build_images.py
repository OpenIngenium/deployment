#!/usr/bin/env python3
"""
Build Docker images for Ingenium services locally on VM

NOTE: This does NOT require a CI server or any image registry!
      - All builds happen locally using docker-compose
      - Images are stored locally on the VM (no pushing)
      - No external dependencies required
"""

import argparse
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import config


# Mapping from repository names to Docker Compose service names
REPO_SERVICE_MAPPING = {
    "archive": ["archive_ing"],
    "auth-service": ["auth_service"],
    "core_server": ["core_server"],
    "dict_service": ["dict_service"],
    "execution_server": ["exec_server"],
    "execution-monitor-service": ["execution_monitor"],
    "ui": ["ui", "ui_nginx"],
    "report_server": ["report_server"],
    "data_sync_service": ["data_sync_service"],
    "search_server": ["search_server"]
}

# Mapping from service names to image names
SERVICE_IMAGE_MAPPING = {
    "archive_ing": "archive_ing",
    "auth_service": "auth_service",
    "core_server": "core_server",
    "dict_service": "dict_service",
    "exec_server": "exec_server",
    "execution_monitor": "execution_monitor",
    "ui": "ui",
    "ui_nginx": "ui_nginx",
    "report_server": "report_server",
    "data_sync_service": "data_sync_service",
    "search_server": "search_server"
}


def run_command(cmd: List[str], cwd: Optional[Path] = None, env: Optional[Dict] = None, stream_output: bool = False) -> Tuple[bool, str]:
    """Run a command and return success status and output.
    
    If stream_output=True, print output in real-time as it happens.
    """
    try:
        if stream_output:
            # Stream output in real-time (unbuffered)
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=0  # Unbuffered
            )
            
            output_lines = []
            for line in process.stdout:
                print(line, end='', flush=True)  # Print in real-time with flush
                sys.stdout.flush()  # Force flush
                output_lines.append(line)
            
            process.wait()
            return (process.returncode == 0, ''.join(output_lines))
        else:
            # Capture output without streaming
            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stdout
    except Exception as e:
        return False, str(e)


def get_git_short_hash(repo_path: Path) -> Optional[str]:
    """Get short git commit hash for a repository."""
    if not repo_path.exists():
        return None
    
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_git_branch(repo_path: Path) -> Optional[str]:
    """Get current git branch for a repository."""
    if not repo_path.exists():
        return None
    
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    if result.returncode == 0:
        branch = result.stdout.strip()
        # Return None if detached HEAD
        return None if branch == "HEAD" else branch
    return None


def build_image_tag(repo_name: str, repos_path: Path, tag: Optional[str] = None, 
                   branch: Optional[str] = None, namespace: Optional[str] = None) -> str:
    """
    Build the Docker image tag for a repository.
    
    If tag is provided, use it directly.
    Otherwise, use pattern: {branch}-{short-hash}
    """
    repo_path = repos_path / repo_name
    
    if tag:
        # Use provided tag
        docker_tag = tag
    else:
        # Build tag from branch and hash
        current_branch = branch or get_git_branch(repo_path) or "unknown"
        short_hash = get_git_short_hash(repo_path) or "latest"
        docker_tag = f"{current_branch}-{short_hash}"
    
    # Add namespace if provided
    if namespace:
        docker_tag = f"{namespace}-{docker_tag}"
    
    return docker_tag


def get_target_services(repo: str) -> List[str]:
    """Get list of service names to build for a given repo."""
    if repo == "all":
        # Return all services
        services = []
        for service_list in REPO_SERVICE_MAPPING.values():
            services.extend(service_list)
        return services
    else:
        return REPO_SERVICE_MAPPING.get(repo, [])


def patch_ui_dockerfiles_for_arm64(ui_repo_path: Path) -> None:
    """
    Patch UI Dockerfiles to add node-sass build dependencies for ARM64.
    
    This is needed because node-sass 4.13.1 doesn't have prebuilt binaries for linux/arm64,
    so it must be compiled from source which requires python2, make, and g++.
    
    This function modifies the Dockerfiles in-place. Changes will show as git modifications
    but won't be committed (git_repos/ is typically gitignored or left as local changes).
    """
    dockerfiles = [
        ui_repo_path / "Dockerfile",
        ui_repo_path / "Dockerfile-nginx-https"
    ]
    
    for dockerfile in dockerfiles:
        if not dockerfile.exists():
            continue
        
        content = dockerfile.read_text()
        
        # Check if already patched
        if "apk add --no-cache python2 make g++" in content:
            continue
        
        # Patch: Add build dependencies after the Node FROM line
        # Pattern: FROM ...node:8.11.1-alpine as node\n\nRUN mkdir /src;
        # Replace with: FROM ...node:8.11.1-alpine as node\n\nRUN apk add --no-cache python2 make g++\n\nRUN mkdir /src;
        
        pattern = r'(FROM [^\n]*node:8\.11\.1-alpine as node\n)(\nRUN mkdir /src;)'
        replacement = r'\1\nRUN apk add --no-cache python2 make g++\2'
        
        patched_content = re.sub(pattern, replacement, content)
        
        if patched_content != content:
            dockerfile.write_text(patched_content)


def build_images(
    repo: str,
    repos_path: Path,
    compose_dir: Path,
    tag: Optional[str] = None,
    branch: Optional[str] = None,
    namespace: Optional[str] = None,
    no_cache: bool = False,
    registry: Optional[str] = None
) -> bool:
    """
    Build Docker images for specified repository(ies).
    
    IMPORTANT: The 'tag' and 'branch' parameters only affect Docker image naming!
               They do NOT checkout code. Build uses whatever is currently in repos_path.
               Use clone_repos.py first to checkout the correct git ref.
    
    Args:
        repo: Repository name or "all"
        repos_path: Path to cloned repositories
        compose_dir: Path to directory with docker-compose files
        tag: Tag for Docker image naming (does NOT checkout git tag)
        branch: Branch for Docker image naming if tag not provided
        namespace: Optional namespace prefix for tags
        no_cache: Force rebuild without cache
        registry: Optional registry URL for pushing images
    
    Returns:
        True if build successful, False otherwise
    """
    # Determine which repos to build
    if repo == "all":
        repos_to_build = list(REPO_SERVICE_MAPPING.keys())
    else:
        repos_to_build = [repo]
    
    print("\n" + "="*60)
    print(f"🔨 BUILD CONFIGURATION")
    print("="*60)
    print(f"  Repositories: {', '.join(repos_to_build)}")
    print(f"  Repos path: {repos_path}")
    print(f"  Compose dir: {compose_dir}")
    if tag:
        print(f"  Docker image tag: {tag}")
    if branch:
        print(f"  Branch (for image tag): {branch}")
    if namespace:
        print(f"  Namespace: {namespace}")
    if registry:
        print(f"  Registry: {registry}")
    print(f"  Build mode: {'Clean build (no cache)' if no_cache else 'Using cache'}")
    print()
    print(f"  ⚠️  NOTE: Building from current code in {repos_path.name}/")
    print(f"           Tag/branch only affects Docker image naming, NOT code version")
    print("="*60 + "\n")
    
    # Get all target services
    services = get_target_services(repo)
    
    if not services:
        print(f"❌ Error: No services found for repo '{repo}'")
        return False
    
    print(f"📦 Services to build: {', '.join(services)}\n")
    
    # M1/ARM64 compatibility: Patch UI Dockerfiles to add node-sass build dependencies
    if "ui" in services and platform.machine() in ['arm64', 'aarch64']:
        print("🔧 Detected ARM64 architecture - patching UI Dockerfiles for node-sass compatibility...")
        patch_ui_dockerfiles_for_arm64(repos_path / "ui")
        print("✅ Dockerfiles patched\n")
    
    # Set up environment variables
    env = os.environ.copy()
    env['REPOS_PATH'] = str(repos_path.absolute())
    
    # Set UI nginx dockerfile (for production builds)
    env['UI_NGINX_BUILD_DOCKERFILE'] = 'Dockerfile-nginx-https'
    
    # Disable BuildKit for compatibility with the container registry
    env['DOCKER_BUILDKIT'] = '0'
    env['COMPOSE_DOCKER_CLI_BUILD'] = '0'
    
    
    # Build docker-compose command
    # Only use the build file - docker-compose.yml has runtime configs we don't need
    compose_files = [
        compose_dir / "docker-compose-build.yml"
    ]
    
    # Verify compose files exist
    for compose_file in compose_files:
        if not compose_file.exists():
            print(f"❌ Error: Compose file not found: {compose_file}")
            return False
    
    # Build command
    cmd = ["docker", "compose"]
    for compose_file in compose_files:
        cmd.extend(["-f", str(compose_file)])
    
    cmd.append("build")
    
    if no_cache:
        cmd.append("--no-cache")
    
    # Add service names
    cmd.extend(services)
    
    print(f"🚀 Running: {' '.join(cmd)}\n")
    print("="*60)
    
    # Run build with real-time output streaming
    success, output = run_command(cmd, cwd=compose_dir, env=env, stream_output=True)
    
    if not success:
        print("\n❌ Build failed!")
        return False
    
    print("\n✅ Build completed successfully!")
    
    # Tag images
    print("\n" + "="*60)
    print("🏷️  TAGGING IMAGES")
    print("="*60)
    
    # Docker Compose uses project name as prefix (directory name)
    project_name = compose_dir.name
    
    for repo_name in repos_to_build:
        image_tag = build_image_tag(repo_name, repos_path, tag, branch, namespace)
        repo_services = REPO_SERVICE_MAPPING[repo_name]
        
        for service in repo_services:
            image_name = SERVICE_IMAGE_MAPPING[service]
            
            # Source tag (from build) - Docker Compose creates: {project_name}-{service}
            source_tag = f"{project_name}-{service}:latest"
            
            # Destination tag
            if registry:
                dest_tag = f"{registry}/ingenium/{image_name}:{image_tag}"
            else:
                dest_tag = f"ingenium/{image_name}:{image_tag}"
            
            print(f"  {source_tag} → {dest_tag}")
            
            # Tag the image
            tag_cmd = ["docker", "tag", source_tag, dest_tag]
            success, output = run_command(tag_cmd)
            
            if not success:
                print(f"    ⚠️  Warning: Failed to tag {source_tag}")
                print(f"    {output}")
            else:
                print(f"    ✓ Tagged")
            
            # Push to registry if specified
            if registry and success:
                print(f"  📤 Pushing to registry...")
                push_cmd = ["docker", "push", dest_tag]
                success, output = run_command(push_cmd)
                
                if not success:
                    print(f"    ⚠️  Warning: Failed to push {dest_tag}")
                    print(f"    {output}")
                else:
                    print(f"    ✓ Pushed")
    
    # Clean up intermediate docker-compose "latest" tags
    print("\n" + "="*60)
    print("🧹 CLEANING UP INTERMEDIATE TAGS")
    print("="*60)
    
    for repo_name in repos_to_build:
        repo_services = REPO_SERVICE_MAPPING[repo_name]
        
        for service in repo_services:
            # Remove the intermediate {project_name}-{service}:latest tag
            source_tag = f"{project_name}-{service}:latest"
            
            print(f"  Removing {source_tag}")
            rmi_cmd = ["docker", "rmi", source_tag]
            success, output = run_command(rmi_cmd)
            
            if not success:
                # It's ok if this fails - image might be in use or already removed
                print(f"    ⚠️  Could not remove (may be in use)")
            else:
                print(f"    ✓ Removed")
    
    print("="*60)
    print("\n✅ Image building complete!")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Build Docker images for Ingenium services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build all repositories with release tag (default: clears cache)
  %(prog)s --repo all --tag r14_3_1
  
  # Build single repository with branch-hash pattern
  %(prog)s --repo ui --branch devel
  
  # Build using cache (faster, but not recommended for releases)
  %(prog)s --repo ui --branch devel --use-cache
  
  # Build with custom repos path
  %(prog)s --repo core_server --tag r14_3_1 --repos-path /path/to/repos
  
  # Build with namespace prefix
  %(prog)s --repo all --tag r14_3_1 --namespace feature-xyz
  
Note: By default, builds clear cache (--no-cache) for clean, reproducible builds.
      Use --use-cache only for development to speed up builds.
"""
    )
    
    parser.add_argument(
        "-r", "--repo",
        required=True,
        choices=["all"] + list(REPO_SERVICE_MAPPING.keys()),
        help="Repository to build (or 'all' for all repos)"
    )
    
    parser.add_argument(
        "-t", "--tag",
        help="Git tag to use for image tagging (e.g., r14_3_1)"
    )
    
    parser.add_argument(
        "-b", "--branch",
        help="Git branch name (used for tagging if --tag not provided)"
    )
    
    parser.add_argument(
        "--namespace",
        help="Namespace prefix for image tags (e.g., feature-xyz)"
    )
    
    parser.add_argument(
        "--repos-path",
        type=Path,
        default=Path.cwd() / "git_repos",
        help="Path to cloned repositories (default: ./git_repos)"
    )
    
    parser.add_argument(
        "--compose-dir",
        type=Path,
        help="Path to directory with docker-compose files (default: auto-detect)"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=True,
        help="Clear cache and rebuild everything (default: True for clean builds)"
    )
    
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use Docker cache (overrides default --no-cache behavior)"
    )
    
    parser.add_argument(
        "--registry",
        help="(Optional) Registry URL to push images - NOT used in standard workflow"
    )
    
    args = parser.parse_args()
    
    # Handle cache flags - default is no-cache unless --use-cache specified
    if args.use_cache:
        args.no_cache = False
    
    # Validate repos path exists
    if not args.repos_path.exists():
        print(f"❌ Error: Repos path does not exist: {args.repos_path}")
        print(f"   Run clone_repos.py first to clone repositories")
        sys.exit(1)
    
    # Auto-detect compose directory if not provided
    if not args.compose_dir:
        # Use opensource_deployment3 directory (self-contained)
        script_dir = Path(__file__).resolve().parent
        args.compose_dir = script_dir
    else:
        # Resolve to absolute so the docker compose project name is correct
        args.compose_dir = args.compose_dir.resolve()
    
    if not args.compose_dir.exists():
        print(f"❌ Error: Compose directory does not exist: {args.compose_dir}")
        sys.exit(1)
    
    # Build images
    success = build_images(
        repo=args.repo,
        repos_path=args.repos_path,
        compose_dir=args.compose_dir,
        tag=args.tag,
        branch=args.branch,
        namespace=args.namespace,
        no_cache=args.no_cache,
        registry=args.registry
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
