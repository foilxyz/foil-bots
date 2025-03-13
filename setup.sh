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

# Install root dependencies
echo -e "${GREEN}Installing root dependencies...${NC}"
poetry install

# Install loom-bot dependencies
echo -e "${GREEN}Installing loom-bot dependencies...${NC}"
cd loom-bot
poetry install
cd ..

# Install arbitrage-bot dependencies
echo -e "${GREEN}Installing arbitrage-bot dependencies...${NC}"
cd arbitrage-bot
poetry install
cd ..

# Set up environment files if they don't exist
if [ ! -f "loom-bot/.env" ]; then
    echo -e "${YELLOW}Creating loom-bot .env file from template...${NC}"
    cp loom-bot/.env.example loom-bot/.env
    echo -e "${RED}Don't forget to edit loom-bot/.env with your configuration!${NC}"
fi

if [ ! -f "arbitrage-bot/.env" ]; then
    echo -e "${YELLOW}Creating arbitrage-bot .env file from template...${NC}"
    cp arbitrage-bot/.env.example arbitrage-bot/.env
    echo -e "${RED}Don't forget to edit arbitrage-bot/.env with your configuration!${NC}"
fi

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${YELLOW}To run loom-bot:${NC} poetry run loom-bot"
echo -e "${YELLOW}To run arbitrage-bot:${NC} poetry run arbitrage-bot" 