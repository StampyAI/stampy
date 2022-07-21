import re
import random
import requests
import traceback
from enum import Enum
from structlog import get_logger
from api.persistence import Persistence

log = get_logger()


class QuestionSource(Enum):
    YOUTUBE = 1
    WIKI = 2


###########################################################################
#   Lightweight wrapper to the Semantic wiki API calls we need to store questions/answers there
###########################################################################
class SemanticWiki(Persistence):
    # until we want to switch focus all by default questions will be all wiki
    default_wiki_question_percent_bias: float = 1.00  # 1 == 100%, 0 == 0%

    def __init__(self, uri, user, api_key):
        super().__init__(uri, user, api_key)
        self.class_name = self.__class__.__name__
        # Should we just log in on init? Or separate it out?
        # TODO: Auto-renew token
        self._session = requests.Session()

        # Retrieve login token first
        response = self.post({"action": "query", "meta": "tokens", "type": "login", "format": "json"})

        # Now log in to the Stampy bot account with the provided login token
        body = {
            "action": "login",
            "lgname": self._user,
            "lgpassword": self._api_key,
            "lgtoken": response["query"]["tokens"]["logintoken"],
            "format": "json",
        }
        self.post(body)

        response = self.post({"action": "query", "meta": "tokens", "format": "json"})
        self._token = response["query"]["tokens"]["csrftoken"]  # store this token

        log.info(self.class_name, status="Logged in to Wiki!")
        return

    ########################################
    # BASE SEMANTICWIKI DIRECT CALLS
    # these calls offer the most freedom, they let you talk to the mediawiki API directly,
    # but they return large dictionaries that need to be navigated through to get relevant data
    ########################################

    def post(self, body):
        """Most basic way to comunicate with the Mediawiki API. body must be a dictionary of things that make sense
        in the context of the API."""
        data = self._session.post(self._uri, data=body)
        response = data.json()
        return response

    def get_page(self, title):
        """Gets a page by the title (page titles are unique).
        Returns a lot of information on revisions and their contents.
        If you only care about the content use get_page_content"""
        body = {
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "timestamp|content",
            "rvslots": "main",
            "formatversion": "2",
            "format": "json",
        }
        return self.post(body)

    def ask(self, query):
        """Ask is query language that lets you gather properties from pages matching a set of criteria.
        See https://www.semantic-mediawiki.org/wiki/Ask for info.
        If all you need is to extract a property from a page you have the title to, use get_page_properties"""
        body = {"action": "ask", "format": "json", "query": query, "api_version": "2"}

        # convert empty results from [] to {}, to always return consistent type
        return self.post(body).get("query", {}).get("results") or {}

    def edit(self, title, content, summary=None):
        """available fields can be found here: https://www.mediawiki.org/wiki/API:Edit
        This edits the page of the given title with the new content
        If a page with name `title` does not already exists, one will be created.
        """
        body = {
            "action": "edit",
            "title": title,
            "token": self._token,
            "format": "json",
            "text": content,
        }
        if summary:
            body["summary"] = summary
        return self.post(body)

    def page_forms_auto_edit(self, title, form, parameter, value):
        """A system to make small changes to already existing pages.
        To be editable with this method, a page must be an instance of a Form
        (a Question, Answer or Video are examples of forms)
        https://www.mediawiki.org/wiki/Extension:Page_Forms/Linking_to_forms#Modifying_pages_automatically for more info
        """
        body = {
            "action": "pfautoedit",
            "form": form,
            "target": title,
            "format": "json",
            "query": f"{form}[{parameter}]={value}",
        }
        return self.post(body)

    def move(self, title: str, new_title: str, reason: str = ""):
        body = {
            "action": "move",
            "format": "json",
            "token": self._token,
            "from": title,
            "to": new_title,
            "reason": reason,
            "movetalk": "1",
        }
        return self.post(body)

    ########################################
    # SYNTACTIC SUGAR FOR SEMANTICWIKI CALLS
    # these functions are wrappers around the base API calls that return only the important information
    # they will not always be usable, but they should be prefered over base api call when possible
    # Be ready to handle a None return if the api call fails
    ########################################

    def get_page_content(self, title):
        """Retrieves the source text for a page with name `title`.
        If no such page exists (or there are other API errors) returns None"""
        content = self.get_page(title)
        try:
            return content["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
        except (KeyError, IndexError):
            return None

    def get_page_properties(self, pagename, *properties):
        """Returns an array containing
        All the values of that property in the page with the specified `pagename`. These arrays may be empty if the
        property is not set.

        if more than one property is given , returns a dictionary containing all of the property names as keys.
        In this case each value is an array as equivalent to the one returned if this function had been called with just
        that one property.

        If no properties are given, throws an error

        In the cases where the page does not exist or the wiki query fails, returns None
        NOTE: it may make more sense to return an empty dict. Keep an eye out for future changes on this"""
        if len(properties) > 1:
            try:
                properties_string = "|?".join(properties)
                return self.ask(f"[[{pagename}]]|?{properties_string}")[pagename]["printouts"]
            except (KeyError, IndexError):
                return None
        elif len(properties) == 1:
            try:
                return self.ask(f"[[{pagename}]]|?{properties[0]}")[pagename]["printouts"][properties[0]]
            except (KeyError, IndexError):
                return None
        else:
            raise ValueError("get_page_properties requires at least one property as input")

    ########################################
    # FUNCTIONS WITH VERY SPECIFIC USES
    # these functions perform very unique tasks that are core to the functioning of particular modules
    # most of them handle the saving and updating of questions and answers
    ########################################

    def add_answer(self, answer_title, answer_writer, answer_users, answer_time, answer_text, question_title):
        # add a answer, we need to figure out which question this is an answer to
        if not answer_title:
            log.warning(
                self.class_name,
                status="No title provided, need the answer title for the primary key of the article",
            )
            return
        ftext = f"""Answer
                |answer={answer_text}
                |answerto={question_title}
                |canonical=No
                |nonaisafety=No
                |unstamped=No
                |writtenby={answer_writer}
                |date={answer_time}
                |stamps={', '.join(answer_users)}"""
        ftext = "{{" + ftext + "}}"

        # Post the answer to wiki
        print("Trying to add reply " + answer_title + " to wiki")
        self.edit(answer_title, ftext)
        return

    def add_question(
        self,
        display_title,
        asker,
        asked_time,
        text,
        comment_url="",
        video_title="",
        likes=0,
        asked=False,
        reply_count=0,
    ):

        # Split the url into the comment id and video url
        if not display_title:
            print("No title provided, need the question title for the primary key of the article")
            return
        comment_id = comment_url.split("&lc=")[1] if comment_url else ""
        ftext = self.format_ftext(
            display_title, asker, asked_time, text, comment_url, video_title, likes, asked, reply_count
        )

        # Post the question to wiki
        print("Trying to add question " + display_title + " to wiki")
        self.edit(display_title + " id:" + comment_id, ftext)
        return

    @staticmethod
    def format_ftext(
        display_title,
        asker,
        asked_time,
        text,
        comment_url="",
        video_title="",
        likes=0,
        asked=False,
        reply_count=0,
    ):
        asked = "Yes" if asked else "No"
        formatted_asked_time = re.sub(
            r"(\d{4}-\d{2}-\d{2})T?(\d{2}:\d{2}):\d{2}(\.\d+)?Z?", r"\1T\2", asked_time
        )
        ftext = f"""
                    Question
                    |question={text}
                    |notquestion=No
                    |canonical=No
                    |forrob=No
                    |asked={asked}
                    |asker={asker}
                    |date={formatted_asked_time}
                    |video={video_title}
                    |ytlikes={likes}
                    |commenturl={comment_url}
                    |replycount={reply_count}
                    |titleoverride={display_title}
                    """
        ftext = "{{" + "".join(ftext.split()) + "}}"

        # replace square brackets with extra UTF-8 brackets
        return ftext.replace("[", "\uFF3B").replace("]", "\uFF3D")

    def edit_question(
        self,
        question_title,
        asker,
        asked_time,
        text,
        comment_url=None,
        video_title=None,
        likes=0,
        asked=False,
        reply_count=0,
    ):
        # I think this is probably fine, but maybe it is slightly different? Could check to see if it exists?
        self.add_question(
            question_title,
            asker,
            asked_time,
            text,
            comment_url=comment_url,
            video_title=video_title,
            likes=likes,
            asked=asked,
        )
        return

    def get_unasked_question(self, sort, order, wiki_question_bias=default_wiki_question_percent_bias):
        if random.random() <= wiki_question_bias:
            return self.get_unasked_wiki_question(sort, order)
        else:
            return self.get_unasked_youtube_question(sort, order)

    def get_unasked_wiki_question(self, sort, order):
        query = (
            "[[Category:Unanswered questions]][[AskedOnDiscord::f]][[Origin::Wiki]][[ForRob::!true]]|?Question|"
            + "?asker|?AskDate|?AskedOnDiscord|sort=AskedOnDiscord,{0}|limit=1|order=asc,{1}".format(
                sort, order
            )
        )
        results = self.ask(query)

        question = {}
        if results:
            question["source"] = QuestionSource.WIKI

            question["question_title"] = list(results.keys())[0]
            all_vals = list(results.values())[0]
            relevant_vals = all_vals["printouts"]
            question["url"] = all_vals["fullurl"]

            if relevant_vals["Question"] and relevant_vals["Question"][0] != question["question_title"]:
                question["text"] = relevant_vals["Question"][0]
            else:
                question["text"] = ""
            if relevant_vals["Asker"]:
                question["username"] = relevant_vals["Asker"][0]
            else:
                question["username"] = "Unknown"
        return question

    def get_unasked_youtube_question(self, sort, order):
        query = (
            "[[AnsweredStatus::Unanswered]][[AskedOnDiscord::f]][[Origin::YouTube]][[ForRob::!true]]|?Question|"
            + "?asker|?AskDate|?CommentURL|?AskedOnDiscord|?video|sort={0}|limit=1|order={1}".format(
                sort, order
            )
        )
        results = self.ask(query)

        # url, username, title, text, replies, asked = None, None, None, None, None, None
        question = {}
        if results:
            question["source"] = QuestionSource.YOUTUBE

            question["question_title"] = list(results.keys())[0]
            relevant_vals = list(results.values())[0]["printouts"]

            if relevant_vals["CommentURL"]:
                question["url"] = relevant_vals["CommentURL"][0]
            else:
                question["url"] = "No URL"
            if relevant_vals["Asker"]:
                question["username"] = relevant_vals["Asker"][0]
            else:
                question["username"] = "Unknown"
            if relevant_vals["Video"]:
                question["title"] = relevant_vals["Video"][0]["fulltext"]
            else:
                question["title"] = "No video title"
            if relevant_vals["Question"]:
                question["text"] = relevant_vals["Question"][0]
            else:
                question["text"] = ""
            if relevant_vals["AskedOnDiscord"]:
                question["asked"] = relevant_vals["AskedOnDiscord"][0] == "t"
            else:
                question["asked"] = False

        return question

    def get_latest_question(self, wiki_question_bias=default_wiki_question_percent_bias):
        return self.get_unasked_question("AskDate", "desc", wiki_question_bias=wiki_question_bias)

    def get_random_question(self, wiki_question_bias=default_wiki_question_percent_bias):
        return self.get_unasked_question("AskDate", "rand", wiki_question_bias=wiki_question_bias)

    def get_top_question(self, wiki_question_bias=default_wiki_question_percent_bias):
        return self.get_unasked_question(
            "Reviewed,YouTubeLikes", "desc,desc", wiki_question_bias=wiki_question_bias
        )

    def set_question_property(self, title, parameter, value):
        return self.page_forms_auto_edit(title, "Question", parameter, value)

    def set_question_asked(self, question_title):
        log.info(self.class_name, update="Setting question: " + question_title + " as asked on Discord")
        response = self.set_question_property(question_title, "asked", "Yes")
        log.info(self.class_name, response=response)
        return response

    def get_question_count(self):
        query = "[[Meta:API Queries]]|?UnaskedQuestions"
        results = self.ask(query)

        return results["Meta:API Queries"]["printouts"]["UnaskedQuestions"][0]

    @staticmethod
    def new_title_with_id(old_title: str, new_title: str):
        # e.g. "Balthazard's question on Video Title Unknown id:UgxRUOD Y9jV0N5F0v14AaABAg"
        id_match = re.search(r" id:.+$", old_title)
        if id_match:
            return new_title + id_match.group(0)

        return new_title

    def move_pages_generator(
        self, page: str = None, limit: int = None, offset: int = None, dry_run=True, skip_boring=False
    ):
        """Move wiki pages related to questions that have a modified title. Also update related fields.
        https://stampy.ai/wiki/Property:PageNeedsMovingTo for more info
        """
        page = (page or "+").strip("'\"`")
        limit = int(limit) if limit else 1
        offset = int(offset) if offset else 0
        skip = ' (skipping "Video Title Unknown)"' if skip_boring else ""
        query = f"[[PageNeedsMovingTo::{page}]]|limit={limit}|offset={offset}"
        results = self.ask(query)
        if not results:
            yield f"move_pages_generator: No results for `{query}`."
            return

        if dry_run:
            yield f"move_pages_generator: Dry run for `{query}`{skip}:"
        else:
            yield f"move_pages_generator: Started for `{query}`{skip}:\n *(write `s, stop` to tell stampy to stop)*"

        max_offset = len(results) + offset - 1
        changes_were_made = False
        for index, item in enumerate(results.values()):
            page = item["fulltext"]
            if skip_boring and "Video Title Unknown" in page:
                continue

            message = f"Page offset {index + offset}/{max_offset}: <{item['fullurl']}>\n" f"```js\n"
            try:
                if item["displaytitle"] == "":
                    message += f"  WARNING: page `{page}` doesn't have a display title => skipping```\n"
                    yield message
                    continue
                new_page = self.new_title_with_id(page, item["displaytitle"])
                new_page_already_exists = (
                    page == new_page or "title" in self.get_page(new_page)["query"]["pages"][0].values()
                )
                if new_page_already_exists:
                    message += f"  WARNING: new page already exists `{new_page}` => skipping```\n"
                    yield message
                    continue

                stats_page = f"Stats:{page}"
                pages_to_load_contents = {
                    page: "PageNeedsMovingTo",
                    stats_page: "Stats:x",
                }

                answer_printouts = self.get_page_properties(page, "AnsweredBy")
                for item in answer_printouts:
                    pages_to_load_contents[item["fulltext"]] = "x|?AnsweredBy"
                related_categories = [
                    "NonCanonicallyAnsweredRelatedQuestion",
                    "RelatedQuestion",
                    "FollowUpQuestion",
                    "DuplicateOf",
                ]
                for category in related_categories:
                    related_pages = self.ask(f"[[{category}::{page}]]").keys()
                    for p in related_pages:
                        pages_to_load_contents[p] = f"{category}::x"

                pages_to_iterate = self.get_page("|".join(pages_to_load_contents.keys()))["query"]["pages"]
                pages_to_move = []
                pages_to_edit = []
                for page_dict in pages_to_iterate:
                    if not page_dict.get("pageid"):
                        continue  # when Stats page doesn't exist

                    title = page_dict["title"]
                    new_title = title
                    if page in title:
                        new_title = title.replace(page, new_page)
                        pages_to_move.append((title, new_title))

                    content = page_dict["revisions"][0]["slots"]["main"]["content"]
                    if page in content:
                        new_content = content.replace(page, new_page)
                        pages_to_edit.append((title, new_title, new_content))

                # Move all pages first, then edit the content, so that Properties point to already existing pages
                for title, new_title in pages_to_move:
                    message += (
                        f"  - move `{title}` ({pages_to_load_contents.get(title, '?')})\n"
                        f"      to `{new_title}`\n"
                    )
                    if not dry_run:
                        self.move(title, new_title, reason="Stampy moving PageNeedsMovingTo")
                        changes_were_made = True

                for title, new_title, new_content in pages_to_edit:
                    message += f"  update `{new_title}` ({pages_to_load_contents.get(title, '?')})\n"
                    if not dry_run:
                        self.edit(new_title, new_content, summary="Stampy editing PageNeedsMovingTo")
                        changes_were_made = True

                message += "```"
                yield message
            except Exception as e:
                log.error(self.class_name, exception=repr(e), traceback=traceback.format_exc())
                message += repr(e) + "```"
                yield message

        done = "Done." if changes_were_made else "No changes made."
        yield f"move_pages_generator: {done}"
        return
