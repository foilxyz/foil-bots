#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Setting up FOIL Bots monorepo with Poetry...${NC}"

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Poetry not found. Installing Poetry...${NC}"
    curl -sSL https://install.python-poetry.org | python3 -
fi

# Install dependencies at the root level only
echo -e "${GREEN}Installing dependencies...${NC}"
poetry lock
poetry install

# Set up environment files if they don't exist
if [ ! -f "loom_bot/.env" ]; then
    echo -e "${YELLOW}Creating loom_bot .env file from template...${NC}"
    cp loom_bot/.env.example loom_bot/.env
    echo -e "${RED}Don't forget to edit loom_bot/.env with your configuration!${NC}"
fi

if [ ! -f "garb_bot/.env" ]; then
    echo -e "${YELLOW}Creating garb_bot .env file from template...${NC}"
    cp garb_bot/.env.example garb_bot/.env
    echo -e "${RED}Don't forget to edit garb_bot/.env with your configuration!${NC}"
fi

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${YELLOW}To run loom-bot:${NC} poetry run loom-bot"
echo -e "${YELLOW}To run garb-bot:${NC} poetry run garb-bot" 