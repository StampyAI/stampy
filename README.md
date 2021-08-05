![stampy banner image](https://github.com/robertskmiles/stampy/blob/master/images/readme-header.png)

<!-- The best dimensions for the banner is **1280x650px**. -->

# stam.py

This repository contains the code for Stampy The Safety Bot (@Stampy). Stampy’s primary purpose is to share questions from Rob Miles YouTube comments section and responses from Rob Miles AI Discord. Questions from YouTube that are interesting spark conversations on discord. Responses to the YouTube question on Discord can then be posted by Stampy as a reply to the YouTube comment.

# Demo

[![Stampy Dev Demo](https://img.youtube.com/vi/LPz7tuGrih8/0.jpg)](https://www.youtube.com/watch?v=LPz7tuGrih8)

# Development

1. Ask to gain access to the github repo from Rob Miles on Discord
2. Install Requirements:
    * [Install git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
    * [Install Anaconda](https://docs.anaconda.com/anaconda/install/)
3. Clone the [Repo](https://github.com/robertskmiles/stampy.git)
    * Run `git clone https://github.com/robertskmiles/stampy.git`
4. Create stampy [python conda environment](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)
    * Change directory to where you downloaded the stampy github
repository: `cd stampy`
    * Run `conda env create -f environment.yml` This will create an anaconda
python kernel with all the dependencies required to run the
current version of stampy.
5. Set Environment Variables
    * Get `.env` file contents from #bot-dev-priv on discord
    * Put `.env` into the root of the stampy repository so [dotenv](https://pypi.org/project/python-dotenv/) can find it
6. Verify that your setup is working
    * Run conda activate stampy
    * Then run `python3 stam.py` from the base directory of the repository.
If everything is working correctly you should be able to talk to
stampy from the test discord server and see the messages in your terminal.
      

# How to Contribute

Checkout the [Trello](https://trello.com/b/LBmYgkes/stampy). It's a great place to start. Make sure to attach your name to the card you're going to work on and then move it into the progress lane. Currently, there are still many setup and organizational tasks. In the future, we would mostly want Stampy contributions to be in the form of adding new modules.

If you make a change to source code, please create a new branch first, then commit your changes there. Open a pull request on github and ask for other developers to review your code before merging.

See [TUTORIAL.md](https://github.com/robertskmiles/stampy/blob/master/TUTORIAL.md) for a step-by-step tutorial detailing how to add features.
