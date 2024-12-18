# GroupLang-secretary-bot

GroupLang-secretary-bot is a Telegram bot that transcribes voice messages, summarizes the content, and allows users to tip for the service. It uses AWS services for transcription and a custom API for summarization. The bot is designed to be deployed as an AWS Lambda function..

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [API Reference](#api-reference)
- [Contributing](#contributing)

## Features

- Transcribe voice messages using AWS Transcribe
- Summarize transcribed text using a custom API
- Allow users to tip for the service
- Secure handling of API keys and tokens
- Deployable as an AWS Lambda function

## Prerequisites

- Poetry for dependency management
- AWS account with Transcribe access
- Telegram Bot Token
- MarketRouter API Key

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/GroupLang-secretary-bot.git
   cd GroupLang-secretary-bot
   ```

2. Install Poetry if you haven't already:
   ```
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Install dependencies using Poetry:
   ```
   poetry install
   ```

## Getting Started

To quickly get started with the GroupLang-secretary-bot, follow these steps:

1. Clone the repository and navigate into the project directory.
2. Install Poetry and the project dependencies.
3. Set up the necessary environment variables as described in the Configuration section.
4. Start the bot using the provided command.
5. Interact with the bot on Telegram by sending voice messages.

1. Set up environment variables:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token
   - `AWS_ACCESS_KEY_ID`: Your AWS Access Key ID
   - `AWS_SECRET_ACCESS_KEY`: Your AWS Secret Access Key
   - `MARKETROUTER_API_KEY`: Your MarketRouter API Key

2. Configure AWS credentials:
   - Either set up the AWS CLI or use environment variables as mentioned above

## Configuration

1. Set up environment variables:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token
   - `AWS_ACCESS_KEY_ID`: Your AWS Access Key ID
   - `AWS_SECRET_ACCESS_KEY`: Your AWS Secret Access Key
   - `MARKETROUTER_API_KEY`: Your MarketRouter API Key

2. Configure AWS credentials:
   - Either set up the AWS CLI with `aws configure` or use environment variables as mentioned above.
   - Ensure that your AWS IAM user has the necessary permissions for AWS Transcribe.

1. Activate the Poetry virtual environment:
   ```
   poetry shell
   ```

2. Start the bot:
   ```
   uvicorn main:app --reload
   ```

3. In Telegram, start a conversation with the bot or add it to a group

4. Send a voice message to the bot

5. The bot will transcribe the audio, summarize the content, and send the result back

6. Users can tip using the inline button provided with the response

## Usage

1. Activate the Poetry virtual environment:
   ```
   poetry shell
   ```

2. Start the bot:
   ```
   uvicorn main:app --reload
   ```

3. In Telegram, start a conversation with the bot or add it to a group.

4. Send a voice message to the bot.

5. The bot will transcribe the audio, summarize the content, and send the result back.

6. Users can tip using the inline button provided with the response.

## Contributing

We welcome contributions to the GroupLang-secretary-bot! If you have suggestions for improvements or new features, feel free to open an issue or submit a pull request. Please ensure that your contributions align with the project's coding standards and include appropriate tests.

To add a new package:
```
poetry add package_name
```

To update all packages:
```
poetry update
```

To update a specific package:
```
poetry update package_name
```

## API Reference

The bot uses the following external APIs:

- AWS Transcribe: For audio transcription
- MarketRouter API: For text summarization and reward submission

Refer to the respective documentation for more details on these APIs.
