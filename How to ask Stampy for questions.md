# How to ask Stampy for questions

Remember that you need to prefix your message with "stampy, " or "s, ".

## Posting questions to Discord

You ask stampy for some number of questions (default is 1), optionally matching status and/or one  tag. Stampy will return that many questions matching your query or, if you asked for more than there  are, all the questions he found.

You can use status shorthands (e.g. "los" for "Live on site") when querying for status.

- next N questions (with status X) (tagged Y) <-- most general pattern
- next 2 questions with status Live on site tagged decision theory
- Can you give us another question?
- Do you have any more questions for us?
- next 5 questions

Stampy prioritizes questions that were least recently posted. He updates the "Last Asked On Discord" column in the "All Answers" table whenever he posts a question to Discord.

If you ask Stampy for more than 5 questions, he will return you at most 5. This limit is implementedi in order not to pollute the channel with links.

## Counting questions

Stampy can also count questions (optionally) matching status and/or tag. It works the same as asking
him to post questions.

- how many questions tagged decision theory and with status live on site
- count questions with status in review

## Getting info

You can ask stampy for question starting with given id (in coda "All Answers" table) or with title
fuzzy-matching some string you give it. Stampy will print information about it in a code block.

- get question what is logica (matches 'What is "logical decision theory"?')
- get question i-f456 (matches question with id starting with "i-f456")
- get question id i-f456 (^)

Example output:

```py
{'id': 'i-c065eab38f25ca3533c691afe6d6d61076655897fe7375ccfdb1220e4f0caa94',
 'title': 'What is "logical decision theory"?',
 'url': 'https://docs.google.com/document/d/1QKMtIORv0HMFr1LrcugipP33HNzL9-bMWPby66Ify3U/edit?usp=drivesdk',
 'status': 'Bulletpoint sketch',
 'tags': ['Definitions', 'Decision Theory'],
 'last_asked_on_discord': datetime.datetime(2023, 2, 26, 0, 0)}
```

## Setting status

You can tell Stampy to change a question's status like this.

- set it to not started (sets the status of the last question stampy "touched" to "Not started")
- set last to not started (^)
- set i-f456 to in review (sets the status of the question with id matching "i-f456" to "In review")

Caveat: only users with `@reviewer` role can change status to/from "Live on site".

When somebody posts one or several links to GDocs with questions and at-mentions one of the following roles, Stampy sets the status of the question of that GDoc accordingly (even if you don't ask him to do so).

- `@reviewer` -> `In review`
- `@feedback` -> `In progress`
- `@feedback-sketch` -> `Bulletpoint sketch`

If a `@reviewer` replies to it with a message containing "approved", "accepted", or "lgtm" Stampy changes the question's status to "Live on site".

## Stampy remembers last question

Whenever stampy "touches" **one** question, he remembers its id as `last_question_id`. You can use it later in getting info about a question ("s, get last") or setting its status ("s, set it to in review") by mentioning it as either "last" or "it".

Note that Stampy doesn't do remember ids of questions when he touched more than once at the same time, e.g. when he counted them or posted more than one ("s, post 5 questions"). Also, this doesn't work for posting questions yet: you can't ask "s, post last question".
