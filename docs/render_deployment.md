# Deploying Bots to Render.com

This guide explains how to deploy the bots to Render.com using Poetry for dependency management.

## Prerequisites

1. A [Render.com](https://render.com) account
2. Your project code in a Git repository (e.g., GitHub, GitLab)

## Deployment Steps

### 1. Create a New Web Service

1. Log in to your Render.com dashboard
2. Click "New" and select "Web Service"
3. Connect your Git repository
4. Select the repository containing your bot code

### 2. Configure the Service

Configure the following settings:

- **Name**: Choose a name for your bot (e.g., `loom-bot` or `arbitrage-bot`)
- **Environment**: Select "Python 3"
- **Region**: Choose a region closest to your target markets
- **Branch**: Select your main branch (e.g., `main` or `master`)
- **Build Command**: Use Poetry to install dependencies:
  ```
  pip install poetry && poetry install
  ```
- **Start Command**: Use the appropriate command:

  ```
  # For Loom Bot
  poetry run loom-bot

  # For Arbitrage Bot
  poetry run arbitrage-bot
  ```

### 3. Environment Variables

Add your environment variables under the "Environment" section:

1. Click "Environment" tab
2. Add all variables from your `.env` file:
   - `NETWORK_RPC_URL`
   - `FOIL_ADDRESS`
   - `WALLET_PK`
   - `DISCORD_BOT_TOKEN`
   - etc.

### 4. Advanced Options

If needed, configure these advanced options:

- **Auto-Deploy**: Enable to automatically deploy when you push to the main branch
- **Health Check Path**: Leave blank (not needed for a bot)
- **Plan**: Select an appropriate plan based on your needs

### 5. Deploy

Click "Create Web Service" to deploy your bot. Render will:

1. Clone your repository
2. Install Poetry and dependencies
3. Start your bot using the specified command

## Monitoring

After deployment:

1. View logs in the "Logs" tab
2. Monitor resource usage in the "Metrics" tab
3. Check Discord for bot notifications

## Updating Your Deployment

When you push changes to your repository:

1. If auto-deploy is enabled, Render will automatically redeploy
2. If not, you can manually deploy from the Render dashboard

## Troubleshooting

If your bot fails to deploy:

1. Check build logs for errors
2. Verify that Poetry is correctly configured
3. Ensure all required environment variables are set
4. Verify that the Poetry script entries are correct in `pyproject.toml`
