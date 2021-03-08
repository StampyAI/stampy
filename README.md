![stampy banner image](https://github.com/robertskmiles/stampy/blob/readme/images/readme-header.png)

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
    * Ask Sudonym for a "`DISCORD_TOKEN`" and "`DISCORD_GUILD`". You should [set
these environment variables](https://www.schrodinger.com/kb/1842) in your [bashrc or zshrc](https://devconnected.com/set-environment-variable-bash-how-to/#:~:text=In%20order%20to%20set%20a,to%20have%20this%20environment%20variable.).
    * Set "`DATABASE_PATH`" path equal to the full path of the database file
from the repo, or another database file that you will use to hold
relevant data while you are testing code e.g. mine is
`/Users/christophercanal/PycharmProjects/stampy/database/database.py`
because I cloned the stampy repo to
`/Users/christophercanal/PycharmProjects`
6. Verify that your setup is working
    * Run conda activate stampy
    * Then run `python3 stam.py` from the base directory of the repository.
If everything is working correctly you should be able to talk to
stampy from the test discord server and see the messages in your terminal.
      

# How to Contribute

Checkout the [Trello](https://trello.com/b/LBmYgkes/stampy). It's a great place to start. Make sure to attach your name to the card you're going to work on and then move it into the progress lane. Currently, there are still many setup and organizational tasks. In the future, we would mostly want Stampy contributions to be in the form of adding new modules.

If you make a change to source code, please create a new branch first, then commit your changes there. Open a pull request on github and ask for other developers to review your code before merging.