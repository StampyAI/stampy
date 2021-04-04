![Random GIF](https://media.giphy.com/media/ZVik7pBtu9dNS/giphy.gif)
# Overview

This document details how to implement a new feature for Stampy, by creating a module - Stampy is organized into modules, which inherit from the `Module` class.

To explain how to implement a new Stampy feature, let's work through an example: Choosing between options. The goal is a feature that works like this:

- User: Stampy, choose A or B or C  
- Stampy: B  
- User: Stampy, choose one, two, or three  
- Stampy: one  

# Module Creation Steps
We'll implement this by creating a new module, which we'll call the 'choose' module. Here's how you'd do that!

1. Create a card on the [trello](https://trello.com/b/LBmYgkes/stampy) in the "Ideas" List, that describes the module that you are planning to make.
1. Message the [`#bot-dev` channel on Discord](https://discord.com/channels/677546901339504640/758062805810282526) with the card, to get feedback and buy-in for your potential module. If the general idea seems well liked, move the card into the "Doing" lane and add your name to the card.
1. Create a new branch named similarly to your module. `$ git checkout -b choose-module`
1. Create a new file named after your module inside of [the `modules` folder](https://github.com/robertskmiles/stampy/tree/master/modules). `$ <editor of your choice> choose.py`
1. In this file, create a child class of the `Module` class
    - ```python
        import discord
        from modules.module import Module


        class ChooseModule(Module):
            def __str__(self):
                return "Choose Module"
        ```
1. Implement the required functions from the `Module` parent class
    - [`can_process_message(self, message, client=None)`](https://github.com/robertskmiles/stampy/blob/master/modules/module.py#L17)
        - This takes a message and returns an integer representing how confident the module is that it can handle that message
        - ```python
            def can_process_message(self, message, client=None):
                text = self.is_at_me(message)

                if text and text.startswith("choose ") and " or " in text:
                    return 8, ""  # We're 8/10 confident
                
                return 0, ""
            ```
        - `self.is_at_me(message)` checks if the message is directly addressed to Stampy, for example by starting or ending with "stampy". If so, it returns the text of the message stripped of the address, otherwise it returns None. Checking this is usually a good idea, since we generally don't want Stampy to butt in on existing conversations.
            - Examples of `self.is_at_me(message)`:
              -  `"Hello"` -> `None`
              -  `"Hello stampy"` -> `"Hello"`
              -  `"What do you mean, stampy?"` -> `"What do you mean?"`
        - For legacy reasons, we currently return a pair consisting of the confidence level and an empty string. For more information about which confidence level to use, consult [the docstring for `can_process_message` in the `Module` class](https://github.com/robertskmiles/stampy/blob/master/modules/module.py#L27-L39). In this case, if the message isn't addressed to stampy or doesn't look like we're being asked to make a choice, we return 0 ("This message isn't meant for this module, I have no idea what to do with it"). If it does look like a choice question addressed to stampy, we return 8 ("This is a valid command specifically for this module, and the module is medium importance functionality")
        - Multiple modules might think that they could respond to a message. The system will take whichever module reports the highest confidence with `can_process_message`, and call that module's `process_message` method to get the reponse.
    - [`process_message(self, message, client=None)`](https://github.com/robertskmiles/stampy/blob/master/modules/module.py#L46)
        - This async method takes a message and processes it, optionally returning a reply for Stampy to say, and an integer representing its confidence that the reply is good and should be posted.
        - ```python
            import re
            import random

            async def process_message(self, message, client=None):
                text = self.is_at_me(message)

                choices_string = text.partition(" ")[2].strip("?")
                options = [option.strip() for option in re.split(" or |,", choices_string) if option.strip()]
                return 8, random.choice(options)
            ```
        - Note that we return a confidence rating for this method as well. This allows for flows like:
            - `can_process_message`: This looks like the kind of question I could look up in database X. Confidence 8, since, if I get a hit, that would be a good response.
            - `process_message`: I looked it up, but got no hits. Say "I couldn't find that in database X", but use confidence 1, to let other modules have a go at this message
    - The final module file might look like this:
    ```python
        import discord
        from modules.module import Module
        import re
        import random


        class ChooseModule(Module):
            def can_process_message(self, message, client=None):
                text = self.is_at_me(message)

                if text and text.startswith("choose ") and " or " in text:
                    return 8, ""  # We're 8/10 confident
                
                return 0, ""
                
            async def process_message(self, message, client=None):
                text = self.is_at_me(message)

                choices_string = text.partition(" ")[2].strip("?")
                options = [option.strip() for option in re.split(" or |,", choices_string) if option.strip()]
                return 8, random.choice(options)
                

            def __str__(self):
                return "Choose Module"
                
        ```
1. Add your module into `stam.py`, so it's loaded in.
    - Import it at the top of the file: `from modules.choose import ChooseModule`
    - Add it to the modules dictionary at the end of the file:
    ```python
    utils.modules_dict = {
        "StampsModule": StampsModule(),
        "QQManager": QQManager(),
        ...
        "ChooseModule": ChooseModule()
        }
    ```
1. Once your feature is implemented, test your changes on the [test discord server](https://discord.com/channels/783123903382814720/783123903382814723)
1. Add and commit your changes
    - `git add modules/choose.py stam.py`
    - `git commit -m "Created a new stampy module that randomly choose between options given by the user"`
1. [Open a pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request) on [github](https://github.com/robertskmiles/stampy/pulls)
1. Post a link to your pull request in the [`#bot-dev` Discord channel](https://discord.com/channels/677546901339504640/758062805810282526)

Good job, thanks for helping make Stampy better!
