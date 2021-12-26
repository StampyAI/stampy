import re
import os
from .module import Module, Response
import csv
import requests
from lxml import etree
import zipfile
from io import BytesIO

spreadsheet_url = (
    "https://docs.google.com/spreadsheets/d/1PwWbWZ6FPqAgZWOoOcXM8N_tUCuxpEyMbN1NYYC02aM/export?format=zip"
)


class ANSearch(Module):
    """
    A module that searches the Alignment Newsletter for relevant papers/articles etc.
    """

    def __init__(self):
        super().__init__()
        noun_regex = r"""([Pp]aper|[Aa]rticle|([Bb]log)? ?[Pp]ost|[Nn]ewsletter)s?"""
        self.re_search = re.compile(
            r"""((([Ww]hich|[Ww]hat) """
            + noun_regex
            + """ (is|was) (it|that))|"""
            + """([Ii]n )?([Ww]hich|[Ww]hat)('?s| is| was| are| were)? ?(it|that|the|they|those)? ?"""
            + noun_regex
            + """ ?(where|in which|which)?|"""
            + noun_regex
            + """ [Ss]earch) (?P<query>.+)"""
        )
        self.items = []
        self.load_items()

    class Item:
        def __init__(self):
            self.category = ""
            self.is_highlight = False
            self.url = ""
            self.title = ""
            self.authors = ""
            self.summary = ""
            self.opinion = ""

            self.score = 0

        def __repr__(self):
            return '<Item: %f "%s" %d>' % (self.score, self.title, len(self.summary))

        def __str__(self):
            return self.__repr__()

    def load_items(self):
        # TODO - Any kind of error checking and handling

        # regex for pulling the first markdown link, with its title and url
        re_markdown_link = re.compile(rb"""\[(?P<title>[^\]]+)\]\((?P<url>[^\)]+)\)""")

        # download the sheet as zipped html from the google sheets API.
        response = requests.get(spreadsheet_url)

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

            for row in rows:
                item = self.Item()

                item.category = row[1].text or ""

                # column 2 contains "highlight" if the item is a highlight
                item.is_highlight = bool(row[2].text)

                # column 3 is the title, which is also a link to the paper/post
                # so we fill 2 fields from this 1 column
                title_field_text = etree.tostring(row[3], method="text", encoding="UTF-8")
                if title_field_text:
                    atag = row[3].find(".//a")  # ../ means it doesn't have to be the immediate child
                    if atag is not None:
                        item.title = atag.text or ""
                        item.url = atag.attrib["href"] or ""
                    else:  # no A tag, maybe a markdown link?
                        match_object = re.search(re_markdown_link, title_field_text)
                        if match_object:
                            item.title = match_object["title"].decode("utf-8") or ""
                            item.url = match_object["url"].decode("utf-8") or ""
                        else:  # no markdown link either...
                            # print("What is even happening here")
                            # print(etree.tostring(row[3]))
                            # print(etree.tostring(row))
                            continue

                    item.authors = (
                        etree.tostring(row[4], method="text", encoding="UTF-8").decode("utf-8") or ""
                    )
                    item.summary = (
                        etree.tostring(row[9], method="text", encoding="UTF-8").decode("utf-8") or ""
                    )
                    item.opinion = (
                        etree.tostring(row[10], method="text", encoding="UTF-8").decode("utf-8") or ""
                    )

                    self.items.append(item)

    @staticmethod
    def extract_keywords(query):
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

    def sort_by_relevance(self, items, search_string, reverse=False):
        # TODO: Semantic search or something else less braindead
        keywords = self.extract_keywords(search_string)
        print('Keywords:, "%s"' % keywords)

        for item in items:
            item.score = 0
            for keyword in keywords:
                keyword = keyword.lower()
                # print(item.title.lower())
                # print(item.title.lower().count(keyword))
                # print((len(item.title) + 1))

                item.score += 1.0 * item.title.lower().count(keyword) / (len(item.title) + 1)
                item.score += 1.0 * item.authors.lower().count(keyword) / (len(item.authors) + 1)
                item.score += 1.0 * item.summary.lower().count(keyword) / (len(item.summary) + 1)

                if item.is_highlight:
                    item.score *= 1.5

        return sorted(items, key=(lambda v: v.score), reverse=reverse)

    def search(self, query):
        result = self.sort_by_relevance(self.items, query, reverse=True)
        print("Search Result:", result[:5])

        best_score = result[0].score
        if best_score == 0:
            return []

        matches = [result[0]]

        for r in result[1:10]:
            if r.score > 0:
                print(r)
            if r.score > (best_score * 0.2):
                matches.append(r)
        return matches

    def process_message(self, message, client=None):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            m = re.match(self.re_search, text)
            if m:
                query = m.group("query")
                return Response(confidence=9, callback=self.process_search_request, args=[query])

        # This is either not at me, or not something we can handle
        return Response()

    @staticmethod
    def list_relevant_items(result):
        item = result[0]
        item_description = "*%s*\n%s\n> %s" % (item.title, item.url, item.summary[:1500])

        reply = "This seems relevant:\n" + item_description

        if len(result) > 1:
            reply += "\n\nIt could also be:\n"
            for item in result[1:5]:
                reply += "- *%s*:\n  (<%s>)\n" % (item.title, item.url)

        if len(reply) >= 2000:
            reply = reply[:1995] + "...`"

        return reply

    async def process_search_request(self, query):
        print('Newsletter Query is:, "%s"' % query)
        result = self.search(query)
        if result:
            print("Result:", result)
            return Response(
                confidence=10,
                text=self.list_relevant_items(result),
                why="I looked in the Alignment Newsletter Database and that's what I could find",
            )
        else:
            return Response(
                confidence=8,
                text="No matches found",
                why="I couldn't find anything relevant in the Alignment Newsletter",
            )

    def __str__(self):
        return "Alignment Newsletter Search"


if __name__ == "__main__":
    module = ANSearch()
    module.load_items()
    print(module.items[0])
