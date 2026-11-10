#!/usr/bin/env python3
"""
Clone and checkout Ingenium Git repositories
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List
import config


def run_command(cmd: List[str], cwd: Path = None) -> bool:
    """Run a command and return success status."""
    try:
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
        print(f"Error: {e.stdout}")
        return False


def clone_repo(repo_name: str, repos_path: Path):
    """Clone a repository if it doesn't exist."""
    repo_config = config.GIT_REPOS[repo_name]
    repo_path = repos_path / repo_name
    
    if repo_path.exists():
        print(f"Repository {repo_name} already exists at {repo_path}")
        return True
    
    print(f"Cloning {repo_name}...")
    cmd = [
        "git", "clone",
        "-b", repo_config["branch"],
        repo_config["url"],
        str(repo_path)
    ]
    return run_command(cmd, cwd=repos_path)


def fetch_repo(repo_name: str, repos_path: Path):
    """Fetch latest changes from remote."""
    repo_path = repos_path / repo_name
    
    if not repo_path.exists():
        print(f"Error: Repository {repo_name} does not exist")
        return False
    
    print(f"Fetching updates for {repo_name}...")
    return run_command(["git", "fetch", "--all"], cwd=repo_path)


def checkout_ref(repo_name: str, ref: str, repos_path: Path):
    """Checkout a specific branch or tag."""
    repo_path = repos_path / repo_name
    
    if not repo_path.exists():
        print(f"Error: Repository {repo_name} does not exist")
        return False
    
    print(f"Checking out {ref} for {repo_name}...")
    
    # Reset any local changes
    if not run_command(["git", "reset", "--hard"], cwd=repo_path):
        return False
    
    # Checkout the ref
    if not run_command(["git", "checkout", ref], cwd=repo_path):
        return False
    
    # Check if we're on a branch (not detached HEAD)
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    current_ref = result.stdout.strip()
    
    # If it's a branch (not HEAD = detached state), pull latest
    if current_ref == ref and current_ref != "HEAD":
        # It's a branch, pull latest
        print(f"Pulling latest changes for branch {ref}...")
        return run_command(["git", "pull", "origin", ref], cwd=repo_path)
    elif current_ref == "HEAD":
        # Detached HEAD (commit or tag)
        print(f"Checked out at {ref} (detached HEAD)")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Clone and checkout Ingenium Git repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clone all repositories
  %(prog)s --repo all
  
  # Clone single repository
  %(prog)s --repo core_server
  
  # Clone and checkout specific branch
  %(prog)s --repo ui --branch feature-branch
  
  # Clone and checkout specific tag
  %(prog)s --repo all --tag r14_3_1
  
  # Clone and checkout specific commit
  %(prog)s --repo core_server --commit abc123def
  
  # Specify custom repos directory
  %(prog)s --repo all --repos-path /path/to/repos
"""
    )
    
    parser.add_argument(
        "-r", "--repo",
        required=True,
        choices=["all"] + list(config.GIT_REPOS.keys()),
        help="Repository to clone (or 'all' for all repos)"
    )
    
    parser.add_argument(
        "-b", "--branch",
        help="Branch to checkout after cloning"
    )
    
    parser.add_argument(
        "-t", "--tag",
        help="Tag to checkout after cloning"
    )
    
    parser.add_argument(
        "-c", "--commit",
        help="Commit hash to checkout after cloning"
    )
    
    parser.add_argument(
        "--repos-path",
        type=Path,
        default=Path.cwd() / "git_repos",
        help="Path to directory for repositories (default: ./git_repos)"
    )
    
    args = parser.parse_args()
    
    # Validate that only one ref type is specified
    ref_count = sum([bool(args.branch), bool(args.tag), bool(args.commit)])
    if ref_count > 1:
        print("Error: Cannot specify more than one of --branch, --tag, or --commit")
        sys.exit(1)
    
    # Determine which repos to process
    if args.repo == "all":
        repos_to_process = list(config.GIT_REPOS.keys())
    else:
        repos_to_process = [args.repo]
    
    # Create repos directory if it doesn't exist
    args.repos_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Repository path: {args.repos_path}")
    print(f"Processing {len(repos_to_process)} repository(ies)...")
    print("=" * 60)
    
    # Process each repository
    success_count = 0
    for repo_name in repos_to_process:
        print(f"\n{'='*60}")
        print(f"[{repo_name}]")
        print('='*60)
        
        # Clone if doesn't exist
        if not clone_repo(repo_name, args.repos_path):
            print(f"Failed to clone {repo_name}")
            continue
        
        # Fetch updates
        if not fetch_repo(repo_name, args.repos_path):
            print(f"Failed to fetch {repo_name}")
            continue
        
        # Checkout specific ref if requested
        ref = args.tag or args.branch or args.commit
        if ref:
            if not checkout_ref(repo_name, ref, args.repos_path):
                print(f"Failed to checkout {ref} for {repo_name}")
                continue
        
        success_count += 1
        print(f"✓ {repo_name} ready")
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print(f"Completed: {success_count}/{len(repos_to_process)} repositories processed successfully")
    print("=" * 60)
    
    # Display summary report
    if success_count > 0:
        print("\n" + "=" * 60)
        print("📊 REPOSITORY SUMMARY REPORT")
        print("=" * 60)
        
        for repo_name in repos_to_process:
            repo_path = args.repos_path / repo_name
            
            if not repo_path.exists():
                print(f"  ❌ {repo_name:<25} - Not found")
                continue
            
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
            
            # Determine display info
            if branch == "HEAD":
                # Detached HEAD
                if tag:
                    status = f"📌 Tag: {tag} @ {commit}"
                else:
                    status = f"🔖 Commit: {commit} (detached)"
            else:
                # On a branch
                if tag:
                    # Branch with tag on same commit
                    status = f"🌿 Branch: {branch} 📌 Tag: {tag} @ {commit}"
                else:
                    status = f"🌿 Branch: {branch} @ {commit}"
            
            print(f"  ✅ {repo_name:<25} {status}")
        
        print("=" * 60 + "\n")
    
    if success_count < len(repos_to_process):
        sys.exit(1)


if __name__ == "__main__":
    main()
