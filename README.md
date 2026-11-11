# Tails Monitor Bot

A lightweight, secure and fully automated Telegram bot written in Python. This BOT monitors the official Tails website RSS feed and instantly reports when a new version of the operating system is released.

## Features
- **24/7 Monitoring:** Runs continuously on the cloud (Render).
- **Custom Intervals:** Choose check frequency from 5 minutes to 24 hours.
- **Interactive UI:** Fully controllable via inline buttons (no need to type commands manually).
- **Owner-only Access:** The bot automatically locks to the first user who starts it, ensuring privacy.
- **Smart Formatting:** Automatically converts minutes to hours for better readability (e.g., "6 hours" instead of "360 min").
- **Web Server Health Check:** Includes a built-in Flask server to prevent the free hosting tier from putting the bot to sleep.

## Tech Stack
- **Language:** Python
- **Telegram API:** python-telegram-bot (v20+ with job-queue)
- **Data Parsing:** feedparser
- **Web Server:** Flask
- **Hosting:** Render (Web Service)
- **Monitoring:** UptimeRobot (to prevent sleep mode)

## Note on Architecture
Because free cloud hosting (Render) tends to "sleep" after periods of inactivity, this bot runs a lightweight Flask web server in the main thread. A background thread handles the Telegram bot polling. To keep the bot awake, an external uptime monitor (UptimeRobot) sends a ping to the Flask server every 5 minutes.
