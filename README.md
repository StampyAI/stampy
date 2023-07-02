![stampy banner image](https://github.com/StampyAI/stampy/blob/master/images/readme-header.png)

<!-- The best dimensions for the banner is **1280x650px**. -->

# stam.py

This repository contains the code for Stampy The Safety Bot (@Stampy). Stampy’s primary purpose is to share questions from Rob Miles YouTube comments section and responses from Rob Miles AI Discord. Questions from YouTube that are interesting spark conversations on discord. Responses to the YouTube question on Discord can then be posted by Stampy as a reply to the YouTube comment.

You can also directly interact with Stampy on Discord (see invite link below). Ask it a question by messaging `Stampy <YOUR QUESTION>` on any channel.

# Discord

Discussion and planning is primarily done on Discord. You are welcome to join via [this invite](https://discord.com/invite/7wjJbFJnSN).
# Developer Set-up

1. Install Requirements:
    * If installing locally:
        - [Install git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
        - [Install Anaconda](https://docs.anaconda.com/anaconda/install/)
    * If using Docker, see the Docker section below
1. If you want to contribute changes, fork and then clone the repo
    * To fork, click the fork button on top of this page and accept default settings.
    * To clone run `git clone https://github.com/<USERNAME>/stampy.git`
1. Create stampy [python conda environment](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)
    * Change directory to where you downloaded the stampy github repository: `cd stampy`
    * Run `conda env create -f environment.yml` This will create an anaconda python kernel with all the dependencies required to run the current version of stampy.
1. If you want to contribute to Stampy dev, you may want access to the shared Stampy test server. In the `#stampy-dev` channel, ask to be given access to:
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
        - `STAMPY_MODULES`: list of your desired modules, or leave unset to load all modules in the `./modules/` directory. You probably don't want all, as some of them aren't applicable to servers other than Rob's.
         - Details about other variables can be found in the `.env` section below.
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

## Environment variables

All lists are space-separated. To find more specifics of what each variable affects, you can `grep` for the lower-case version of the name.

You'll need at least these:

- `ENVIRONMENT_TYPE`: "development" or "production".
- `DISCORD_TOKEN`: your bot token
- `DISCORD_GUILD`: your server ID
- `DATABASE_PATH`: the path to the Q&A database (normally in `./database/stampy.db`).
- `STAMPY_MODULES`: list of your desired modules, or leave unset to load all modules in the `./modules/` directory. You probably don't want all, as some of them aren't applicable to servers other than Rob's.

Not required:

- `BOT_VIP_IDS`: list of user IDs. VIPs have full access and some special permissions.
- `BOT_DEV_ROLES`: list of roles representing bot devs.
- `BOT_DEV_IDS`: list of user ids of bot devs. You may want to include `BOT_VIP_IDS` here.
- `BOT_CONTROL_CHANNEL_IDS`: list of channels where control commands are accepted.
- `BOT_PRIVATE_CHANNEL_ID`: single channel where private Stampy status updates are sent
- `CODA_API_TOKEN`: token to access Coda. Without it, modules `Questions` and `QuestionSetter` will not be available and `StampyControls` will have limited functionality.
- `BOT_REBOOT`: how Stampy reboots himself. Unset, he only quits, expecting an external `while true` loop (like in `runstampy`/Dockerfile). Set to `exec` he will try to relaunch himself from his own CLI arguments.
- `STOP_ON_ERROR`: Dockerfile/`runstampy` only, unset `BOT_REBOOT` only. If defined, will only restart Stampy when he gets told to reboot, returning exit code 42. Any other exit code will cause the script to just stop.
- `BE_SHY`: Stamp won't respond when the message isn't specifically to him.
- `CHANNEL_WHITELIST`: channels Stampy is allowed to respond to messages in
- `IS_ROB_SERVER`: If defined, Rob Miles server-specific stuff is enabled. Servers other than Rob Miles Discord Server and Stampy Test Server should not enable it, Otherwise some errors are likely to occur.

Specific modules (excluding LLM stuff):

- `FACTOID_DATABASE_PATH`: SQLite database of factoids for Factoid.py. Dockerfile sets this to be in the ./local directory.
- `WOLFRAM_TOKEN`: Your API token for the Wolfram module.

LLM stuff:

- `OPENAI_API_KEY`: Your OpenAI secret key
- `PAID_SERVICE_ALL_CHANNELS`: If set, Stampy is not limited in what channels he can call on paid services.
- `PAID_SERVICE_CHANNEL_IDS`: if the above is unset, this is a list of channels where Stampy is allowed to call paid services.
- `PAID_SERVICE_FOR_ALL`: if set, Stampy can use paid services to respond to anyone.
- `PAID_SERVICE_WHITELIST_ROLE_IDS`: if the above is unset, Stampy responds with paid services only for users with these roles.
- `GPT4`: if set, allow using GPT4 instead of GPT3.5-TURBO. (Slow!)
- `GPT4_FOR_ALL`: if set, don't restrict who gets GPT4 responses.
- `GPT4_WHITELIST_ROLE_IDS`: if the above is unset, Stampy responds with GPT4 only for users with these roles.
- `USE_HELICONE`: if set, GPT prompts call the helicone API rather than OpenAI.
- `LLM_PROMPT`: What prompt is the language model being fed? This describes the personality and behavior of the bot.

## Docker

The repo contains both a Dockerfile and a docker-compose. Stampy can be configured through the `.env` file. The docker-compose file will bind-mount the directory `./local` into `/stampydata` in the container. It changes `FACTOID_DATABASE_PATH` to `/stampydata/Factoids.db` so it will stay across reboots.

The Stampy Docker-compose server can be brought up with:

``` sh
sudo docker compose build && sudo docker compose up
```

It can be shut down with double `Ctrl-C`. To make Stampy a daemon, add `-d` to the `up` command.

The Dockerfile can also execute Stampy's tests by adding `STAMPY_RUN_TESTS="TRUE"` to the `.env` file.

# How to Contribute

Check out the currently open github issues and pull requests, if you see something open you can help out with add a comment. Most coordinations is done through live voice calls in the discord.

If you make a change to source code, please create a new branch first, then commit your changes there. Open a pull request on github and ask for other developers to review your code before merging.

See [TUTORIAL.md](https://github.com/StampyAI/stampy/blob/master/TUTORIAL.md) for a step-by-step tutorial detailing how to add features.
