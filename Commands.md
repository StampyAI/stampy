# Stampy commands

This file ~~lists~~ *will list (at some point [WIP])* all available commands for Stampy, divided according to which module handles them.

Whenever you add a new feature to Stampy or meaningfully modify some feature in a way that may alter how it acts, please update this file and test manually whether Stampy's behavior follows the specification.

## Questions

## QuestionsSetter

**Permissions:**

- All server members can contribute to AI Safety Questions and [ask for feedback](#review-request).
- Only `@bot dev`s, `@editor`s, and `@reviewer`s can change question status by other commands ([1](#marking-questions-for-deletion-or-as-duplicates) [2](#setting-question-status)).
- Only `@reviewers` can change status of questions to and from  `Live on site` (including [accepting](#review-acceptance) [review requests](#review-request)).

### Review request

On Rob Miles's Discord server, an `@editor` can ask other `@editor`s and `@reviewer`s to give them feedback or review their changes to AI Safety Info questions. You just put one or more links to appropriate GDocs and mention one of: `@reviewer`, `@feedback`, or `@feedback-sketch`. Stampy will spot this and update their statuses in the [coda table with answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a) appropriately.

- `@reviewer` -> `In review`
- `@feedback` -> `In progress`
- `@feedback-sketch` -> `Bulletpoint sketch`

![](images/command-review-request.png)

Some remarks:

- Optimally, review requesting and approval should be mostly confined to the `#editing` forum-channel.
- You don't need to call Stampy explicitly to make him update question status. All that matters is that you include one or more valid links to GDocs with AI Safety Info questions and an appropriate at-mention.

### Review acceptance

A `@reviewer` can **accept** a question by (1) responding to a [review request](#review-request) with a keyword (listed below) or (2) posting one or more valid links to GDocs with AI Safety Info questions with a keyword. Stampy then reacts by changing status to `Live on site`.

The keywords are (case-insensitive):

- accepted
- approved
- lgtm
  - stands for "looks good to me"

![](images/command-review-acceptance.png)

### Marking questions for deletion or as duplicates

Use `s, <del/dup>` (or `stampy, <del/dup>`) to change status of questions to `Marked for deletion` or `Duplicate`

![](images/command-del-dup.png)

### Setting question status

Question status can be changed more flexibly, using the command: `<set/change> <status/to/status to> <status>`, followed by appropriate GDoc links.

Status name is case-insensitive: there is no difference between `Live on site`, `live on site`, or `LIVE ON SITE`. You can also use acronym aliases, e.g., `los` for `Live on site` or `bs` for `Bulletpoint sketch`.

![](images/command-set-status.png)
