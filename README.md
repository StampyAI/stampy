![stampy banner image](https://github.com/StampyAI/stampy/blob/master/images/readme-header.png)

<!-- The best dimensions for the banner is **1280x650px**. -->

# stam.py

This repository contains the code for Stampy The Safety Bot (@Stampy). Stampy’s primary purpose is to share questions from Rob Miles YouTube comments section and responses from Rob Miles AI Discord. Questions from YouTube that are interesting spark conversations on discord. Responses to the YouTube question on Discord can then be posted by Stampy as a reply to the YouTube comment.

You can also directly interact with Stampy on Discord (see invite link below). Ask it a question by messaging `Stampy <YOUR QUESTION>` on any channel.

# Discord

Discussion and planning is primarily done on Discord. You are welcome to join via [this invite](https://discord.com/invite/7wjJbFJnSN).
# Developer Set-up

1. Install Requirements:
    * [Install git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
    * [Install Anaconda](https://docs.anaconda.com/anaconda/install/)
1. Fork and then clone the repo
    * To fork, click the fork button on top of this page and accept default settings.
    * To clone run `git clone https://github.com/<USERNAME>/stampy.git`
1. Create stampy [python conda environment](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)
    * Change directory to where you downloaded the stampy github
repository: `cd stampy`
    * Run `conda env create -f environment.yml` This will create an anaconda python kernel with all the dependencies required to run the current version of stampy.
1. Get access to appropriate channels in Discord. In the `#stampy-dev` channel, ask to be given access to:
    * `#stampy-dev-priv` channel to access the `.env` information
    * Stampy's Test Server
1. Set Environment Variables
    * if running your own Stampy instance:
       * Create `.env` in the root of the stampy repository (so [dotenv](https://pypi.org/project/python-dotenv/) can find it)
       * In `.env`, set at least the following variables:
         - `ENVIRONMENT_TYPE` to "development" or "production".
         - `DISCORD_TOKEN` to your bot token
         - `DISCORD_GUILD` to your server ID
         - `DATABASE_PATH` to the path to the Q&A database (normally in `./database/stampy.db`).
         - `STAMPY_MODULES` to a space-separated list of your desired modules, or leave unset to load all modules in the `./modules/` directory.
         - All other environment variables can be found in `./config.py`. Though they are not required, you will not be able to do some functions, i.e. rebooting stampy with Discord messages, in-Discord logging, etc
    * if working on our Stampy instance:
        * In the `#stampy-dev-priv` channel, go to pinned messages, and copy the message that starts with `DISCORD_TOKEN`
        * Create `.env` in the root of the stampy repository (so [dotenv](https://pypi.org/project/python-dotenv/) can find it)
        * Paste the message into `.env`
        * Add coda api token to `.env`: first create a [coda account](https://coda.io/), then create a token in [account settings](https://coda.io/account), then add `CODA_API_TOKEN="your-token-here"` to `.env`
1. Verify that your setup is working
    * Run `conda activate stampy`
    * Then run `python3 stam.py` or `python stam.py` from the base directory of the repository.
      * Alternatively, if you prefer to restart stampy on any file save (and if you have NodeJS installed), you can run `npx nodemon stamp.py`.
    * Go to Stampy's Test Server, then `#stampy-dev-priv` channel.
    * You should see a message from Stampy saying `I just (re)started from git branch master by <your name>!`
    * If you ask Stampy a question (e.g. `Stampy, what is AI`), you should see messages in your terminal processing this question.

# How to Contribute

Check out the currently open github issues and pull requests, if you see something open you can help out with add a comment. Most coordinations is done through live voice calls in the discord.

If you make a change to source code, please create a new branch first, then commit your changes there. Open a pull request on github and ask for other developers to review your code before merging.

See [TUTORIAL.md](https://github.com/StampyAI/stampy/blob/master/TUTORIAL.md) for a step-by-step tutorial detailing how to add features.
