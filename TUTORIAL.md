![Random GIF](https://media.giphy.com/media/ZVik7pBtu9dNS/giphy.gif)
# Overview

This document details how to implement a new feature for Stampy, by creating a module - Stampy is organized into modules, which inherit from the `Module` class.

To explain how to implement a new Stampy feature, let's work through an example: Choosing between options. The goal is a feature that works like this:

- User: Stampy, choose A or B or C  
- Stampy: B  
- User: Stampy, choose one, two, or three  
- Stampy: one  

We'll implement this by creating a new module, which we'll call the 'choose' module.

1. Create a card on the [trello](https://trello.com/b/LBmYgkes/stampy) in the "Ideas" List, that describes the module that you are planning to make.
1. Message the [Discord (in `#bot-dev`)](https://discord.com/channels/677546901339504640/758062805810282526) with the card, to get feedback and buy-in for your potential module. If the general idea seems well liked, move the card into the "Doing" lane and add your name to the card.
1. Create a new branch named similarly to your module `git checkout -b choose-module`
1. Create a new file named after your module inside of [the `modules` folder](https://github.com/robertskmiles/stampy/tree/master/modules)
1. In this file, create a child class of the `Module` class
1. Implement the required functions from the `Module` parent class
    - [`def can_process_message(self, message, client=None)`](https://github.com/robertskmiles/stampy/blob/master/modules/module.py#L17)
        - This takes a message and returns an integer representing how confident the module is that it can handle that message
    - [`def process_message(self, message, client=None)`](https://github.com/robertskmiles/stampy/blob/master/modules/module.py#L46)
        - which takes a message and processes it, optionally returning a reply for Stampy to say, and an integer representing its confidence that the reply is good and should be posted.
1. Test your changes on the [test discord server](https://discord.com/channels/783123903382814720/783123903382814723)
1. Add and commit your changes
1. Open a pull request on [github](https://github.com/robertskmiles/stampy/pulls)
1. Post a link to your pull request on the [Discord (in `#bot-dev`)](https://discord.com/channels/677546901339504640/758062805810282526)

Good job, thanks for helping make Stampy better! Hopefully your contribution helps us propagate AI Safety information to more humans before the stamps take over.









The two most important methods to implement are:

`can_process_message()`, which takes a message and returns an integer representing how confident the module is that it can handle that message

and

`process_message()`, which takes a message and processes it, optionally returning a reply for Stampy to say, and an integer representing its confidence that the reply is good and should be posted.