"""
Searches a database of AI-alignment-related documents for something like your question
"""

from __future__ import annotations
import re
from dataclasses import dataclass
import zipfile
import requests
from io import BytesIO
from lxml import etree
from structlog import get_logger
from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage

# this is the URL to Alignment Newsletter's google sheets database.
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PwWbWZ6FPqAgZWOoOcXM8N_tUCuxpEyMbN1NYYC02aM/export?format=zip"

# weight factor to put on an item if it is a highlight
HIGHLIGHT_WEIGHT = 1.5

# maximum number of items to return in the response
MAX_NUM_ITEMS = 5

# regex for pulling the first markdown link, with its title and url.
RE_MARKDOWN_LINK = re.compile(rb"""\[(?P<title>[^\]]+)\]\((?P<url>[^\)]+)\)""")


@dataclass
class Item:
    """Class to hold a single row from the google sheets database.

    Most of the attributes are just the columns from the database.
    self.score will show much the item matches a query.
    """

    category: str
    is_highlight: bool
    url: str
    title: str
    authors: str
    summary: str
    opinion: str
    score: float = 0.0

    @classmethod
    def parse(cls, row) -> Item | None:
        """Parse a row from the google sheets database into an Item object.

        Parameters
        ----------
        row : some kind of lxml etree object
            see AlignmentNewsletterSearch.load_items() for where row comes from

        Returns
        -------
        Item | None
            If the row is valid, return an Item object.
            If the row is invalid, return None.
        """
        # TODO - Any kind of error checking and handling

        # column 1 is the category
        category = row[1].text or ""

        # column 2 contains "highlight" if the item is a highlight
        is_highlight = bool(row[2].text)

        # column 3 is the title, which is also a link to the paper/post
        # so we fill 2 fields from this 1 column
        title_field_text = etree.tostring(row[3], method="text", encoding="UTF-8")
        if not title_field_text:
            return None

        # ../ means it doesn't have to be the immediate child
        atag = row[3].find(".//a")
        if atag is not None:
            title = atag.text or ""
            url = atag.attrib["href"] or ""
        else:
            # no A tag, maybe a markdown link?
            match_object = RE_MARKDOWN_LINK.match(title_field_text)
            if match_object:
                title = match_object["title"].decode("utf-8") or ""
                url = match_object["url"].decode("utf-8") or ""
            else:
                return None

        authors = (
            etree.tostring(row[4], method="text", encoding="UTF-8").decode("utf-8")
            or ""
        )
        summary = (
            etree.tostring(row[9], method="text", encoding="UTF-8").decode("utf-8")
            or ""
        )
        opinion = (
            etree.tostring(row[10], method="text", encoding="UTF-8").decode("utf-8")
            or ""
        )
        return cls(category, is_highlight, url, title, authors, summary, opinion)

    def __repr__(self):
        return f'Item(score={self.score}, title="{self.title}", summary_length={len(self.summary)})'

    def __str__(self):
        return self.__repr__()


class AlignmentNewsletterSearch(Module):
    """
    A module that searches the Alignment Newsletter database for relevant papers/articles etc.
    """

    def process_message(self, message: ServiceMessage) -> Response:
        """Process a message and return a response if this module can handle it."""
        text = self.is_at_me(message)

        if text is False:
            return Response()

        # create regex for determining if message should be answered by this module.
        # examples that match:
        # What paper is that blah blah blah
        # in which blog post blah blah blah
        # newsletter search: blah blah blah
        noun = r"([Pp]aper|[Aa]rticle|([Bb]log)? ?[Pp]ost|[Nn]ewsletter)s?"
        question1 = r"(([Ww]hich|[Ww]hat) " + noun + " (is|was) (it|that))"
        question2 = (
            r"([Ii]n )?([Ww]hich|[Ww]hat)('?s| is| was| are| were)? ?(it|that|the|they|those)? ?"
            + noun
            + " ?(where|in which|which)?"
        )
        question3 = noun + " [Ss]earch"

        pattern = (
            "("
            + question1
            + "|"
            + question2
            + "|"
            + question3
            + ")"
            + r".? (?P<query>.+)"
        )

        match = re.match(pattern, text)

        if not match:
            return Response()

        query = match.group("query")
        return Response(
            confidence=9, callback=self.process_search_request, args=[query]
        )

    async def process_search_request(self, query) -> Response:
        """Search for relevant items for the query.

        First we load all items from the Alignment Newsletter database.
        Then we sort the items by relevance to the query.
        Finally we return the most relevant items, if any.
        """
        self.log.info(self.class_name, newsletter_query=query)

        items = self.load_items()
        items_sorted = self.sort_by_relevance(items, query, reverse=True)

        self.log.info(self.class_name, search_results=items_sorted[:MAX_NUM_ITEMS])

        most_relevant_items = self.get_most_relevant_items(items_sorted)

        if most_relevant_items:
            self.log.info(self.class_name, newsletter_query_result=most_relevant_items)
            return Response(
                confidence=10,
                text=self.convert_items_to_string(most_relevant_items),
                why="I looked in the Alignment Newsletter Database and that's what I could find",
            )
        else:
            return Response(
                confidence=8,
                text="No matches found in the Alignment Newsletter Database",
                why="I couldn't find anything relevant in the Alignment Newsletter",
            )

    def load_items(self) -> list[Item]:
        """
        Loads and parses the google sheets database into a list of Item objects.

        The database is a google sheets spreadsheet, which can be exported as a zip file.
        The zip file contains a single html file, which contains the table of data.
        We then extract the table from the html.
        Finally, we parse the table one row at a time into a list of Item objects.

        Returns
        --------------
        items : list[Item]
            Each item is a parsed row from the google sheets database.
        """
        # download the sheet as zipped html from the google sheets API.
        response = requests.get(SPREADSHEET_URL)

        # we have to use BytesIO to unzip in memory
        bytes = BytesIO(response.content)
        zip_file = zipfile.ZipFile(bytes)
        with zip_file.open("Database.html") as html_file:
            # pull out the main body of the table
            html_data = html_file.read().decode("utf-8")
            table = etree.HTML(html_data).find("body/div/table/tbody")

        rows = iter(table)

        # first two rows are headers and freeze bar, chuck them out
        headers = next(rows)
        bar = next(rows)

        items: list[Item] = []
        for row in rows:
            item = Item.parse(row)
            if item is not None:
                items.append(item)

        return items

    @staticmethod
    def extract_keywords(query: str) -> list[str]:
        """Splits the query into keywords, removing boring words and punctuation."""
        boring_words = """
            a about all also am an and any as at back be because but 
            by can come could do does did for from get go have he her 
            him his how i if in is into it its just like make me my no 
            not now of on one only or our out over say see she so some 
            take than that the their them then there these they this 
            time to up us use was we what when which who will with would 
            your know find where something name remember video talk talked 
            paper article blog blogpost book
            talking talks rob robert""".split()
        boring_words = [w.strip() for w in boring_words]

        keywords = query.lower().split()
        keywords = [w.strip("\"'?.,!") for w in keywords if w not in boring_words]
        return keywords

    def sort_by_relevance(
        self, items: list[Item], query: str, reverse: bool = False
    ) -> list[Item]:
        """Sort items by calculating how relevant each item is to the query.

        Parameters
        ----------
        items : list[Item]
            The list of items to sort.
        query : str
            The query from user.
        reverse : bool, optional
            Whether to sort in descending order, by default False

        Returns
        -------
        list[Item]
            The sorted list of items, with relevance scores stored
            in the `score` attribute of each item.
        """
        # TODO: Semantic search or something else less brain dead
        keywords = self.extract_keywords(query)
        self.log.info(self.class_name, keywords=keywords)

        for item in items:
            for keyword in keywords:
                item.score += item.title.lower().count(keyword) / (len(item.title) + 1)
                item.score += item.authors.lower().count(keyword) / (
                    len(item.authors) + 1
                )
                item.score += item.summary.lower().count(keyword) / (
                    len(item.summary) + 1
                )

            if item.is_highlight:
                item.score *= HIGHLIGHT_WEIGHT

        return sorted(items, key=(lambda item: item.score), reverse=reverse)

    def get_most_relevant_items(self, items_sorted: list[Item]) -> list[Item]:
        """Get the most relevant items.

        Parameters
        ----------
        items_sorted : list[Item]

        Returns
        -------
        list[Item]
            The most relevant items.
            At most MAX_NUM_ITEMS items will be returned.
            If none of the items are relevant, an empty list is returned.
        """
        best_score = items_sorted[0].score
        if best_score == 0:
            return []

        most_relevant_items = [items_sorted[0]]

        for r in items_sorted[1:MAX_NUM_ITEMS]:
            if r.score > 0:
                self.log.info(self.class_name, search_r_score=r)
            if r.score > (best_score * 0.2):
                most_relevant_items.append(r)
        return most_relevant_items

    @staticmethod
    def convert_items_to_string(items: list[Item]) -> str:
        """Convert a list of items to a string that can be sent as a reply."""
        item = items[0]
        item_description = f"*{item.title}*\n{item.url}\n> {item.summary[:1500]}"

        reply = "This seems relevant:\n" + item_description

        if len(items) > 1:
            reply += "\n\nIt could also be:\n"
            for item in items[1:MAX_NUM_ITEMS]:
                reply += f"- *{item.title}*:\n  (<{item.url}>)\n"

        if len(reply) >= 2000:
            reply = reply[:1995] + "...`"

        return reply

    def __str__(self):
        return "Alignment Newsletter Search"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                test_message="paper search bugs features",
                expected_regex=r"This seems relevant:\n.?Adversarial Examples Are Not Bugs, They Are Features",
            ),
            self.create_integration_test(
                test_message="blog post search: thisisnotarealword",
                expected_response="No matches found in the Alignment Newsletter Database",
            ),
        ]


if __name__ == "__main__":
    module = AlignmentNewsletterSearch()
    items = module.load_items()
    log = get_logger()
    log.info(module.class_name, an_search_items=items[0])
