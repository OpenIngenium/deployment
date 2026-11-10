#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Ingenium Deployment Manager Setup ===${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import questionary" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --upgrade pip 2>/dev/null
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi

# Make scripts executable if not already
if [ ! -x "ingenium.py" ] || [ ! -x "clone_repos.py" ] || [ ! -x "build_images.py" ] || [ ! -x "setup_instance.py" ]; then
    echo "Making scripts executable..."
    chmod +x ingenium.py clone_repos.py build_images.py setup_instance.py
    echo -e "${GREEN}✓ Scripts are executable${NC}"
fi

# Run the deployment manager
echo -e "\n${GREEN}=== Starting Deployment Manager ===${NC}\n"
./ingenium.py
